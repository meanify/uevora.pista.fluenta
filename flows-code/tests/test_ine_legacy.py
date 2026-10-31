"""Contract tests for legacy indicators migrated to the annual runner."""

import importlib
import inspect
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import pandas as pd
import requests
from sqlalchemy import create_engine, inspect as inspect_database, text
from sqlalchemy.exc import SQLAlchemyError

from pistadigital.cli import ine_flows as cli
from pistadigital.utils import ine_annual as annual
from pistadigital.utils import ine_api, ine_output


LEGACY = {
    "0009873": ("establecimento_de_alojamento_turistico", 2024, 64, "varchar", "date"),
    "0009874": ("quartos", 2025, 64, "varchar", "date"),
    "0009929": ("rendimento_medio_por_quarto", 2024, 128, "varchar", "timestamp"),
}


def metadata(year):
    return [{
        "Periodic": "Anual",
        "Dimensoes": {"Categoria_Dim": [{"categories": [
            {"dim_num": dimension, "categ_cod": code, "categ_dsg": label}
            for dimension, labels in {
                "1": {f"S7A{year}": str(year)},
                "2": {
                    "PT": "Portugal", "1": "Continente", "11": "Norte",
                    "111": "Alto Minho", "1111601": "Arcos de Valdevez",
                    "11A": "Porto", "11A1304": "Maia",
                    "2": "Acores", "20": "Acores NUTS II",
                    "200": "Acores NUTS III", "2004201": "Lagoa",
                },
                "3": {
                    "T": "Total", "01": "Hotelaria", "0101": "Hoteis",
                    "010115": "5 estrelas", "02": "Alojamento local",
                },
            }.items() for code, label in labels.items()
        ]}]},
    }]


def record(value="12,5", **fields):
    return {"geocod": "1111601", "dim_3": "010115", "valor": value, **fields}


class LegacyFlowTests(unittest.TestCase):
    def test_registered_indicator_labels_are_not_fixed_width(self):
        for code, module_path in cli.INDICATORS.items():
            with self.subTest(code=code):
                module = importlib.import_module(module_path)
                self.assertNotRegex(module.CREATE_TABLE_SQL.lower(), r"\bbpchar\(")
                self.assertNotRegex(module.CREATE_TABLE_SQL.lower(), r"\bchar\((64|128)\)")

    def module(self, code):
        return importlib.import_module(f"pistadigital.flows.ine_{code}_flow")

    def process(self, code, rows, **options):
        year = LEGACY[code][1]
        with patch.object(annual, "fetch_indicator_metadata", return_value=metadata(year)), \
                patch.object(annual, "fetch_annual_indicator_data",
                             return_value=[{"Dados": {str(year): rows}}]):
            return self.module(code).processar_indicador_ine(
                **({"exportar_csv": False} | options)
            )

    def test_schemas_defaults_and_public_signatures_preserved(self):
        for code, (metric, year, subtype_length, string_type, date_type) in LEGACY.items():
            with self.subTest(code=code):
                module = self.module(code)
                signature = inspect.signature(module.processar_indicador_ine)
                self.assertEqual(list(signature.parameters), [
                    "varcd", "ano", "exportar_csv", "gravar_bd", "caminho_csv",
                ])
                self.assertEqual(
                    [parameter.default for parameter in signature.parameters.values()],
                    [code, year, True, False, None],
                )
                self.assertIs(module.process_annual_indicator, annual.process_annual_indicator)
                self.assertEqual(module.TABLE_NAME, f"ine_{code}_ds")
                self.assertEqual(module.VALUE_COLUMN, metric)
                self.assertEqual(module.COLUMN_LENGTHS["subtipo_alojamento"], subtype_length)
                for column, length in module.COLUMN_LENGTHS.items():
                    self.assertIn(f"{column} {string_type}({length}) NOT NULL",
                                  module.CREATE_TABLE_SQL)
                self.assertIn(f"{metric} float4 NULL", module.CREATE_TABLE_SQL)
                self.assertIn(f"create_date {date_type} NULL", module.CREATE_TABLE_SQL)
                self.assertIn(f"update_date {date_type} NULL", module.CREATE_TABLE_SQL)
                self.assertFalse(module.MONTHLY)

    def test_hierarchies_totals_labels_dates_and_metrics(self):
        for code, (metric, year, *_) in LEGACY.items():
            with self.subTest(code=code):
                frame = self.process(code, [
                    record(), record("0", dim_3="T"),
                    record("..", dim_3="01"),
                    record("x", dim_3="0101"),
                    record(None, dim_3="02"),
                    record("1", geocod="11A1304"),
                    record("2", geocod="2004201"),
                    *[record(geocod=geocode, dim_3="T")
                      for geocode in ("PT", "1", "11", "111")],
                ])
                self.assertEqual(frame.columns.tolist(), self.module(code).SCHEMA_COLUMNS)
                self.assertEqual(frame.iloc[0].tolist()[:8], [
                    "Continente", "Norte", "Alto Minho", "Viana do Castelo",
                    "Arcos de Valdevez", "Hotelaria", "Hoteis", "5 estrelas",
                ])
                self.assertEqual(len(frame), 5)
                self.assertEqual(frame.iloc[1].tolist()[5:8], ["Total"] * 3)
                self.assertEqual(frame.iloc[2].tolist()[5:8], [
                    "Alojamento local", "Alojamento Local", "Alojamento Local",
                ])
                self.assertEqual(frame.iloc[0][metric], 12.5)
                self.assertEqual(frame.iloc[1][metric], 0)
                self.assertTrue(pd.isna(frame.iloc[2][metric]))
                self.assertEqual(frame.iloc[3]["nuts_iii"], "Porto")
                self.assertEqual(frame.iloc[4]["distrito"], "São Miguel")
                self.assertTrue(frame.ano.eq(year).all())
                self.assertRegex(frame.iloc[0]["create_date"], r"^\d{4}-\d{2}-\d{2}$")
                self.assertTrue(frame.create_date.eq(frame.update_date).all())
                for marker in ("", "s.r."):
                    self.assertTrue(pd.isna(self.process(code, [record(marker)]).iloc[0][metric]))

    def test_invalid_arguments_before_network(self):
        for code in LEGACY:
            for options in (
                {"ano": 0}, {"ano": True}, {"varcd": "wrong"},
                {"exportar_csv": False, "caminho_csv": "bad.csv"},
            ):
                with self.subTest(code=code, options=options), \
                        patch.object(annual, "fetch_indicator_metadata") as fetch, \
                        self.assertRaises(ValueError):
                    self.module(code).processar_indicador_ine(**options)
                fetch.assert_not_called()

    def test_invalid_metadata_before_data_request(self):
        for code, (_, year, *_) in LEGACY.items():
            for change in ("frequency", "period", "dimension"):
                meta = metadata(year)
                if change == "frequency":
                    meta[0]["Periodic"] = "Mensal"
                else:
                    categories = meta[0]["Dimensoes"]["Categoria_Dim"][0]["categories"]
                    dimension = "1" if change == "period" else "3"
                    categories[:] = [c for c in categories if c["dim_num"] != dimension]
                with self.subTest(code=code, change=change), \
                        patch.object(annual, "fetch_indicator_metadata", return_value=meta), \
                        patch.object(annual, "fetch_annual_indicator_data") as fetch, \
                        self.assertRaisesRegex(RuntimeError, "Invalid INE metadata"):
                    self.module(code).processar_indicador_ine()
                fetch.assert_not_called()

    def test_invalid_payloads_fail_before_any_output(self):
        for code, (_, year, *_) in LEGACY.items():
            invalid = [
                [], {}, [{"Dados": None}], [{"Dados": [record()]}],
                [{"Dados": {str(year - 1): []}}],
                [{"Dados": {str(year): [], str(year - 1): []}}],
            ]
            for rows in (
                [None], [{}], [record(), record()],
                [record(anocod=year - 1)], [record(anocod=True)],
                [record(geocod="unknown")], [record(dim_3="unknown")],
                [record("bad")], [record("NaN")], [record("inf")], [record(True)],
            ):
                invalid.append([{"Dados": {str(year): rows}}])
            for payload in invalid:
                with self.subTest(code=code, payload=payload), \
                        patch.object(annual, "fetch_indicator_metadata", return_value=metadata(year)), \
                        patch.object(annual, "fetch_annual_indicator_data", return_value=payload), \
                        patch.object(annual, "replace_period_data") as database, \
                        patch.object(annual, "write_csv") as csv, \
                        self.assertRaises(RuntimeError):
                    self.module(code).processar_indicador_ine(gravar_bd=True)
                database.assert_not_called()
                csv.assert_not_called()

    def test_oversize_labels_rejected_without_truncation(self):
        for code, (_, year, length, *_) in LEGACY.items():
            meta = metadata(year)
            categories = meta[0]["Dimensoes"]["Categoria_Dim"][0]["categories"]
            next(c for c in categories if c["categ_cod"] == "0101")["categ_dsg"] = "X" * (length + 1)
            with self.subTest(code=code), \
                    patch.object(annual, "fetch_indicator_metadata", return_value=meta), \
                    patch.object(annual, "fetch_annual_indicator_data",
                                 return_value=[{"Dados": {str(year): [record()]}}]), \
                    self.assertRaisesRegex(RuntimeError, "exceed"):
                self.module(code).processar_indicador_ine(exportar_csv=False)

    def test_cli_csv_only_exact_selector_and_no_database(self):
        for code, (_, year, *_) in LEGACY.items():
            responses = [Mock(), Mock()]
            responses[0].json.return_value = metadata(year)
            responses[1].json.return_value = [{"Dados": {str(year): [record()]}}]
            with self.subTest(code=code), tempfile.TemporaryDirectory() as directory, \
                    patch.object(ine_api.requests, "get", side_effect=responses) as get, \
                    patch.object(ine_output, "get_engine", side_effect=AssertionError("DB access")):
                path = Path(directory) / "data.csv"
                self.assertEqual(cli.main([
                    "-i", str(int(code)), "-y", str(year), "--csv", "-o", str(path),
                ]), 0)
                frame = pd.read_csv(path)
                self.assertEqual(frame.columns.tolist(), self.module(code).SCHEMA_COLUMNS)
                self.assertEqual(frame.iloc[0][self.module(code).VALUE_COLUMN], 12.5)
                self.assertEqual(get.call_count, 2)
                self.assertIn(f"varcd={code}", get.call_args_list[0].args[0])
                self.assertIn(f"Dim1=S7A{year}", get.call_args_list[1].args[0])
                for response in responses:
                    response.raise_for_status.assert_called_once_with()

    def test_outputs_database_first_and_default_filenames(self):
        for code, (_, year, *_) in LEGACY.items():
            order = Mock()
            with self.subTest(code=code), \
                    patch.object(annual, "replace_period_data", order.database), \
                    patch.object(annual, "write_csv", order.csv):
                frame = self.process(code, [record()], exportar_csv=True, gravar_bd=True)
            self.assertEqual([call[0] for call in order.mock_calls], ["database", "csv"])
            self.assertIs(order.database.call_args.args[0], frame)
            self.assertEqual(order.database.call_args.args[1:], (
                self.module(code).TABLE_NAME, self.module(code).CREATE_TABLE_SQL, year,
            ))
            self.assertEqual(order.csv.call_args.args[1], f"ine_{code}_{year}_tratado.csv")
            with patch.object(annual, "write_csv") as csv, \
                    patch.object(annual, "replace_period_data") as database:
                self.process(code, [record()], gravar_bd=True)
                database.assert_called_once()
                csv.assert_not_called()

    def test_empty_csv_has_header_and_database_preserves_rows(self):
        for code in LEGACY:
            module = self.module(code)
            engine = create_engine("sqlite://")
            try:
                with patch.object(ine_output, "get_engine", return_value=engine), \
                        patch.object(engine, "dispose"):
                    original = self.process(code, [record()], gravar_bd=True)
                    with tempfile.TemporaryDirectory() as directory:
                        path = Path(directory) / "empty.csv"
                        empty = self.process(
                            code, [], gravar_bd=True, exportar_csv=True, caminho_csv=path,
                        )
                        self.assertTrue(empty.empty)
                        self.assertEqual(path.read_text().strip(), ",".join(module.SCHEMA_COLUMNS))
                    with engine.connect() as connection:
                        count = connection.execute(text(f"SELECT count(*) FROM {module.TABLE_NAME}")).scalar()
                    self.assertEqual(count, len(original))
            finally:
                engine.dispose()

    def test_transactional_replacement_and_other_year_preservation(self):
        for code, (metric, year, *_) in LEGACY.items():
            module = self.module(code)
            engine = create_engine("sqlite://")
            try:
                with patch.object(ine_output, "get_engine", return_value=engine), \
                        patch.object(engine, "dispose"):
                    frame = self.process(code, [record("1")], gravar_bd=True)
                    previous = frame.assign(ano=year - 1)
                    ine_output.replace_period_data(
                        previous, module.TABLE_NAME, module.CREATE_TABLE_SQL, year - 1, engine=engine,
                    )
                    self.process(code, [record("2")], gravar_bd=True)
                    with self.assertRaisesRegex(RuntimeError, "rolled back"):
                        ine_output.replace_period_data(
                            pd.concat([frame, frame]), module.TABLE_NAME,
                            module.CREATE_TABLE_SQL, year, engine=engine,
                        )
                self.assertEqual(
                    inspect_database(engine).get_pk_constraint(module.TABLE_NAME)["constrained_columns"],
                    module.SCHEMA_COLUMNS[:9],
                )
                with engine.connect() as connection:
                    rows = connection.execute(text(
                        f"SELECT ano, {metric} FROM {module.TABLE_NAME} ORDER BY ano"
                    )).all()
                self.assertEqual(rows, [(year - 1, 1), (year, 2)])
            finally:
                engine.dispose()

    def test_api_and_output_failures_propagate(self):
        for code, (_, year, *_) in LEGACY.items():
            for stage in ("replace_period_data", "write_csv"):
                with self.subTest(code=code, stage=stage), \
                        patch.object(annual, stage, side_effect=RuntimeError(stage)):
                    with self.assertRaisesRegex(RuntimeError, stage):
                        self.process(code, [record()], exportar_csv=True, gravar_bd=True)
            with patch.object(annual, "fetch_indicator_metadata", side_effect=RuntimeError("metadata")), \
                    self.assertRaisesRegex(RuntimeError, "metadata"):
                self.module(code).processar_indicador_ine()
            with patch.object(annual, "fetch_indicator_metadata", return_value=metadata(year)), \
                    patch.object(annual, "fetch_annual_indicator_data", side_effect=RuntimeError("data")), \
                    self.assertRaisesRegex(RuntimeError, "data"):
                self.module(code).processar_indicador_ine()
            with patch.object(annual, "write_csv", side_effect=OSError("disk full")), \
                    self.assertRaisesRegex(OSError, "disk full"):
                self.process(code, [record()], exportar_csv=True)
        for error in (requests.Timeout("timeout"), requests.HTTPError("HTTP error"), ValueError("invalid JSON")):
            with patch.object(ine_api.requests, "get", side_effect=error), \
                    patch.object(annual, "write_csv") as csv, \
                    self.assertRaisesRegex(RuntimeError, "API do INE"):
                self.module("0009929").processar_indicador_ine()
            csv.assert_not_called()

    def test_legacy_create_table_wrappers_share_transaction_and_disposal(self):
        for code in ("0009873", "0009929"):
            module = self.module(code)
            engine = create_engine("sqlite://")
            try:
                with patch.object(ine_output, "get_engine", return_value=engine), \
                        patch.object(engine, "dispose") as dispose:
                    module.criar_tabela()
                    dispose.assert_called_once_with()
                self.assertTrue(inspect_database(engine).has_table(module.TABLE_NAME))
            finally:
                engine.dispose()
            engine = Mock()
            engine.begin.side_effect = SQLAlchemyError("cannot create")
            with patch.object(ine_output, "get_engine", return_value=engine), \
                    self.assertRaisesRegex(RuntimeError, module.TABLE_NAME):
                module.criar_tabela()
            engine.dispose.assert_called_once_with()
