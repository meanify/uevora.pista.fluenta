import contextlib
import importlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import pandas as pd
from sqlalchemy import create_engine, inspect, text

from pistadigital.cli import ine_flows as cli
from pistadigital.utils import ine_annual as annual
from pistadigital.utils import ine_api, ine_output
from pistadigital.utils.ine_transform import filter_detail_rows, metric_value


INDICATORS = {
    "0009930": ("hospedes", {"local_residencia": 64}),
    "0011140": ("estada_media", {"local_residencia": 64}),
    "0009183": ("dormidas", {"local_residencia": 128}),
    "0009876": ("hospedes", {
        "tipo_alojamento": 64, "subtipo_alojamento": 64, "classificacao": 64,
    }),
    "0009877": ("dormidas", {
        "tipo_alojamento": 64, "subtipo_alojamento": 128, "classificacao": 64,
    }),
    "0009880": ("estada_media", {
        "tipo_alojamento": 64, "subtipo_alojamento": 128, "classificacao": 64,
    }),
    "0008350": ("superficie_unidades_territoriais", {
        "distrito": 128, "municipio": 128,
    }),
}
GEOGRAPHY = {
    "PT": "Portugal", "1": "Continente", "11": "Norte",
    "111": "Alto Minho", "1111601": "Arcos de Valdevez",
    "11A": "Área Metropolitana do Porto", "11A1304": "Maia",
    "11A0116": "São João da Madeira",
    "2": "Região Autónoma dos Açores", "20": "Região Autónoma dos Açores",
    "200": "Região Autónoma dos Açores", "2004201": "Lagoa",
}
RESIDENCE = {
    "T": "Total", "PT": "Portugal", "E": "Estrangeiro", "MA": "Marrocos",
}
ACCOMMODATION = {
    "T": "Total", "01": "Hotelaria", "0101": "Hotéis",
    "010115": "5 estrelas", "02": "Alojamento local",
    "03": "Turismo no espaço rural e de habitação",
}


def metadata(year=2025):
    return [{
        "Periodic": "Anual",
        "Dimensoes": {"Categoria_Dim": [{
            "categories": [
                {"dim_num": dim, "categ_cod": code, "categ_dsg": label}
                for dim, labels in {
                    "1": {f"S7A{year}": str(year)},
                    "2": GEOGRAPHY, "3": RESIDENCE,
                }.items()
                for code, label in labels.items()
            ],
        }]},
    }]


def record(**options):
    return {
        "geocod": "1111601", "geodsg": "Arcos de Valdevez",
        "dim_3": "MA", "dim_3_t": "Marrocos", "ind_string": "1", "valor": "1",
        **options,
    }


def accommodation_metadata(year=2025):
    meta = metadata(year)
    categories = meta[0]["Dimensoes"]["Categoria_Dim"][0]["categories"]
    categories[:] = [category for category in categories if category["dim_num"] != "3"]
    categories.extend(
        {"dim_num": "3", "categ_cod": code, "categ_dsg": label}
        for code, label in ACCOMMODATION.items()
    )
    return meta


class AnnualFlowTests(unittest.TestCase):
    def module(self, code):
        return importlib.import_module(f"pistadigital.flows.ine_{code}_flow")

    def process(self, module, records, year=2025, **options):
        meta = metadata(year)
        if "tipo_alojamento" in module.COLUMN_LENGTHS:
            meta = accommodation_metadata(year)
            records = [
                {**row, "dim_3": "010115"}
                if isinstance(row, dict) and row.get("dim_3") == "MA" else row
                for row in records
            ]
        with patch.object(
            annual, "fetch_indicator_metadata", return_value=meta
        ), patch.object(
            annual, "fetch_annual_indicator_data",
            return_value=[{"Dados": {str(year): records}}],
        ):
            return module.processar_indicador_ine(
                ano=year, exportar_csv=False, **options
            )

    def test_exact_schema_and_hierarchy(self):
        for code, (metric, extra_lengths) in INDICATORS.items():
            module = self.module(code)
            with self.subTest(code=code):
                frame = self.process(module, [
                    record(), record(
                        geocod="11A0116", valor=None,
                    ),
                    record(geocod="11A1304", valor="0"),
                    record(geocod="2004201", valor="2,5"),
                ])
                dimensions = {
                    "nuts_i": 64, "nuts_ii": 64, "nuts_iii": 64,
                    "distrito": 64, "municipio": 64, **extra_lengths,
                }
                self.assertEqual(module.COLUMN_LENGTHS, dimensions)
                self.assertEqual(
                    frame.columns.tolist(),
                    [*dimensions, "ano", metric, "create_date", "update_date"],
                )
                self.assertEqual(frame.iloc[0].tolist()[:5], [
                    "Continente", "Norte", "Alto Minho", "Viana do Castelo",
                    "Arcos de Valdevez",
                ])
                if "local_residencia" in extra_lengths:
                    self.assertEqual(frame.iloc[0]["local_residencia"], "Marrocos")
                elif "tipo_alojamento" in extra_lengths:
                    self.assertEqual(frame.iloc[0].tolist()[5:8],
                                     ["Hotelaria", "Hotéis", "5 estrelas"])
                self.assertEqual(
                    frame.iloc[1].tolist()[:5],
                    ["Continente", "Norte", "Área Metropolitana do Porto",
                     "Aveiro", "São João da Madeira"],
                )
                self.assertTrue(pd.isna(frame.iloc[1][metric]))
                self.assertEqual(frame.iloc[2]["nuts_iii"],
                                 "Área Metropolitana do Porto")
                self.assertEqual(frame.iloc[2][metric], 0)
                self.assertEqual(frame.iloc[3]["distrito"], "São Miguel")
                self.assertEqual(frame.iloc[3][metric], 2.5)
                self.assertEqual(frame["ano"].tolist(), [2025] * 4)
                self.assertRegex(frame.iloc[0]["create_date"], r"^\d{4}-\d{2}-\d{2}$")
                self.assertEqual(frame.iloc[0]["create_date"],
                                 frame.iloc[0]["update_date"])
                self.assertFalse(module.MONTHLY)
                self.assertEqual(module.TABLE_NAME, f"ine_{code}_ds")
                self.assertIn(
                    f"CREATE TABLE IF NOT EXISTS {module.TABLE_NAME}",
                    module.CREATE_TABLE_SQL,
                )
                for column, length in dimensions.items():
                    self.assertIn(f"{column} varchar({length}) NOT NULL",
                                  module.CREATE_TABLE_SQL)
                self.assertIn(f"{metric} float4 NULL", module.CREATE_TABLE_SQL)
                self.assertIn("create_date date NULL", module.CREATE_TABLE_SQL)
                self.assertIn("update_date date NULL", module.CREATE_TABLE_SQL)

    def test_9880_powerbi_accommodation_replacements(self):
        module = self.module("0009880")
        rural_label = "Turismo no Espaço Rural e de Habitação"
        cases = [
            ("ALOJAMENTO LOCAL", "Alojamento Local", "Alojamento Local"),
            ("Turismo RURAL", rural_label, rural_label),
            ("Turismo rural e de habitação", rural_label, rural_label),
            ("Turismo de HABITAÇÃO", "Subtype", rural_label),
            ("Hotelaria", "Subtype", "Classification"),
            ("Outro alojamento local", "Subtype", "Classification"),
        ]
        for label, subtype, classification in cases:
            with self.subTest(label=label):
                labels = {
                    "01": label, "0101": "Subtype", "010115": "Classification",
                }
                result = module.transform_dimensions(record(dim_3="010115"), {
                    "2": GEOGRAPHY, "3": labels,
                })
                self.assertEqual(result["tipo_alojamento"], label)
                self.assertEqual(result["subtipo_alojamento"], subtype)
                self.assertEqual(result["classificacao"], classification)
                self.assertEqual(labels["0101"], "Subtype")
                self.assertEqual(labels["010115"], "Classification")

    def test_accommodation_replacements_in_processed_frames(self):
        for code in ("0009876", "0009877", "0009880"):
            with self.subTest(code=code):
                frame = self.process(self.module(code), [
                    record(dim_3="02", valor="0"),
                    record(dim_3="03", valor="2,5"),
                    record(dim_3="T"),
                    record(dim_3="010115"),
                ])
                expected = [
                    "Alojamento Local", "Turismo no Espaço Rural e de Habitação",
                ]
                for column in ("subtipo_alojamento", "classificacao"):
                    self.assertEqual(frame[column].tolist()[:2], expected)
                self.assertEqual(frame["tipo_alojamento"].tolist(), [
                    ACCOMMODATION[key] for key in ("02", "03", "T", "01")
                ])
                self.assertEqual(frame.iloc[2]["subtipo_alojamento"], "Total")
                self.assertEqual(frame.iloc[2]["classificacao"], "Total")
                self.assertEqual(frame.iloc[3]["subtipo_alojamento"], "Hotéis")
                self.assertEqual(frame.iloc[3]["classificacao"], "5 estrelas")
                self.assertEqual(frame.iloc[0][self.module(code).VALUE_COLUMN], 0)
                self.assertEqual(frame.iloc[1][self.module(code).VALUE_COLUMN], 2.5)

    def test_detail_filter_uses_api_codes(self):
        geocodes = ("PT", "1", "11", "111", "1111601")
        records = [{"geocod": geocode, "dim_3": "02"} for geocode in geocodes]
        frame = pd.DataFrame({"municipio": ["Total"] * 4 + ["Arcos"]})
        self.assertEqual(filter_detail_rows(frame, records, {})["municipio"].tolist(),
                         ["Arcos"])
        codes = ("T", "01", "0101", "010115", "02", "03")
        records = [{"geocod": "11", "dim_3": code} for code in codes]
        frame = pd.DataFrame({"tipo_alojamento": codes})
        self.assertEqual(
            filter_detail_rows(frame, records, {"3": ACCOMMODATION})["tipo_alojamento"].tolist(),
            ["T", "010115", "02", "03"],
        )
        regional = pd.DataFrame({"nuts_ii": ["Total", "Total", "Norte", "x", "x"]})
        self.assertEqual(
            filter_detail_rows(regional, [{"geocod": g} for g in geocodes], {})
            ["nuts_ii"].tolist(), ["Norte"],
        )

    def test_geography_filter_is_applied_before_outputs(self):
        rows = [
            record(geocod=geocode)
            for geocode in ("PT", "1", "11", "111", "1111601", "11A1304")
        ]
        for code in INDICATORS:
            with self.subTest(code=code), \
                    patch.object(annual, "replace_period_data") as database, \
                    patch.object(annual, "write_csv") as csv:
                module = self.module(code)
                frame = self.process(module, rows, gravar_bd=True)
                expected_count = 2
                self.assertEqual(len(frame), expected_count)
                self.assertEqual(frame.index.tolist(), list(range(expected_count)))
                self.assertEqual(frame["municipio"].tolist(),
                                 ["Arcos de Valdevez", "Maia"])
                pd.testing.assert_frame_equal(database.call_args.args[0], frame)
                csv.assert_not_called()
        module = self.module("0009880")
        with patch.object(annual, "fetch_indicator_metadata",
                          return_value=accommodation_metadata()), \
                patch.object(annual, "fetch_annual_indicator_data",
                             return_value=[{"Dados": {"2025": [
                                 record(geocod="1111601", dim_3="02"),
                                 record(geocod="PT", dim_3="T"),
                             ]}}]), \
                patch.object(annual, "replace_period_data") as database, \
                patch.object(annual, "write_csv") as csv:
            frame = module.processar_indicador_ine(ano=2025, gravar_bd=True)
            self.assertEqual(len(frame), 1)
            self.assertEqual(frame.iloc[0]["classificacao"], "Alojamento Local")
            pd.testing.assert_frame_equal(database.call_args.args[0], frame)
            pd.testing.assert_frame_equal(csv.call_args.args[0], frame)

    def test_9880_filtered_empty_csv_keeps_schema_without_database_access(self):
        module = self.module("0009880")
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(annual, "fetch_indicator_metadata",
                             return_value=accommodation_metadata()), \
                patch.object(annual, "fetch_annual_indicator_data",
                             return_value=[{"Dados": {"2025": [
                                 record(geocod="PT", dim_3="T"),
                             ]}}]), \
                patch.object(ine_output, "get_engine",
                             side_effect=AssertionError("DB access")):
            output = Path(directory) / "out.csv"
            frame = module.processar_indicador_ine(ano=2025, caminho_csv=output)
            self.assertTrue(frame.empty)
            self.assertEqual(pd.read_csv(output).columns.tolist(),
                             module.SCHEMA_COLUMNS)

    def test_null_markers_zero_and_malformed_metrics(self):
        for marker in (None, "", "..", "s.r.", "x"):
            self.assertIsNone(metric_value(marker))
        self.assertEqual(metric_value("0"), 0)
        for value in ("bad", "nan", "inf", True, [], {}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                metric_value(value)

    def test_8350_published_2022_fixture_has_no_category_dimension(self):
        module = self.module("0008350")
        meta = metadata(2022)
        categories = meta[0]["Dimensoes"]["Categoria_Dim"][0]["categories"]
        categories[:] = [
            category for category in categories if category["dim_num"] != "3"
        ]
        row = {
            "geocod": "11A0116", "geodsg": "São João da Madeira",
            "ind_string": "7,94", "valor": "7.94",
        }
        with patch.object(annual, "fetch_indicator_metadata", return_value=meta), \
                patch.object(
                    annual, "fetch_annual_indicator_data",
                    return_value=[{"Dados": {"2022": [row]}}],
                ):
            frame = module.processar_indicador_ine(
                ano=2022, exportar_csv=False,
            )
        self.assertEqual(frame.columns.tolist(), module.SCHEMA_COLUMNS)
        self.assertEqual(frame.iloc[0]["ano"], 2022)
        self.assertEqual(frame.iloc[0][module.VALUE_COLUMN], 7.94)

    def test_invalid_input_has_no_api_or_output_side_effects(self):
        for code in INDICATORS:
            module = self.module(code)
            with patch.object(annual, "fetch_indicator_metadata") as fetch:
                for options in (
                    {"ano": 0}, {"ano": True}, {"varcd": "wrong"},
                    {"exportar_csv": False, "caminho_csv": "out.csv"},
                ):
                    with self.subTest(code=code, options=options), \
                            self.assertRaises(ValueError):
                        module.processar_indicador_ine(**options)
                fetch.assert_not_called()

    def test_bad_records_fail_before_outputs(self):
        for code in INDICATORS:
            module = self.module(code)
            for rows in (
                [record(anocod="2024")], [record(), record()],
                [record(geocod="unknown")], [record(dim_3="unknown")],
                [record(valor="not-a-number")], [None],
            ):
                if code == "0008350" and rows == [record(dim_3="unknown")]:
                    continue
                with self.subTest(code=code, rows=rows), \
                        patch.object(annual, "replace_period_data") as database, \
                        patch.object(annual, "write_csv") as csv:
                    with self.assertRaises(RuntimeError):
                        self.process(module, rows, gravar_bd=True)
                    database.assert_not_called()
                    csv.assert_not_called()

    def test_lengths_checked_even_without_database_output(self):
        for code, (_, extra_lengths) in INDICATORS.items():
            module = self.module(code)
            accommodation = "tipo_alojamento" in extra_lengths
            meta = accommodation_metadata() if accommodation else metadata()
            if code == "0008350":
                target_dim, target_code, target_column = "2", "1111601", "municipio"
            elif accommodation:
                target_dim, target_code, target_column = "3", "03", "tipo_alojamento"
            else:
                target_dim, target_code, target_column = "3", "MA", "local_residencia"
            for category in meta[0]["Dimensoes"]["Categoria_Dim"][0]["categories"]:
                if category["dim_num"] == target_dim and category["categ_cod"] == target_code:
                    category["categ_dsg"] = "X" * (module.COLUMN_LENGTHS[target_column] + 1)
            with self.subTest(code=code), patch.object(
                annual, "fetch_indicator_metadata", return_value=meta
            ), patch.object(
                annual, "fetch_annual_indicator_data",
                return_value=[{"Dados": {"2025": [
                    record(dim_3="03") if accommodation else record()
                ]}}],
            ), self.assertRaisesRegex(RuntimeError, "exceed"):
                module.processar_indicador_ine(ano=2025, exportar_csv=False)

    def test_csv_only_and_empty_headers_never_connect(self):
        for code in INDICATORS:
            module = self.module(code)
            for rows in ([record()], []):
                with self.subTest(code=code, empty=not rows), \
                        tempfile.TemporaryDirectory() as directory, \
                        patch.object(annual, "fetch_indicator_metadata",
                                     return_value=accommodation_metadata()
                                     if "tipo_alojamento" in module.COLUMN_LENGTHS
                                     else metadata()), \
                        patch.object(annual, "fetch_annual_indicator_data",
                                     return_value=[{"Dados": {"2025": [
                                         {**row, "dim_3": "010115"}
                                         if "tipo_alojamento" in module.COLUMN_LENGTHS
                                         else row for row in rows
                                     ]}}]), \
                        patch.object(ine_output, "get_engine",
                                     side_effect=AssertionError("DB access")):
                    output = Path(directory) / "out.csv"
                    module.processar_indicador_ine(ano=2025, caminho_csv=output)
                    csv = pd.read_csv(output)
                    self.assertEqual(csv.columns.tolist(), module.SCHEMA_COLUMNS)
                    self.assertEqual(len(csv), len(rows))

    def test_output_order_and_failure_propagation(self):
        for code in INDICATORS:
            module = self.module(code)
            calls = Mock()
            calls.attach_mock(Mock(), "database")
            calls.attach_mock(Mock(), "csv")
            with self.subTest(code=code), patch.object(
                annual, "fetch_indicator_metadata",
                return_value=accommodation_metadata()
                if "tipo_alojamento" in module.COLUMN_LENGTHS else metadata()
            ), patch.object(
                annual, "fetch_annual_indicator_data",
                return_value=[{"Dados": {"2025": [
                    record(dim_3="010115")
                    if "tipo_alojamento" in module.COLUMN_LENGTHS else record()
                ]}}],
            ), patch.object(annual, "replace_period_data", calls.database), \
                    patch.object(annual, "write_csv", calls.csv):
                module.processar_indicador_ine(ano=2025, gravar_bd=True)
                self.assertEqual([call[0] for call in calls.mock_calls],
                                 ["database", "csv"])
                calls.reset_mock()
                calls.database.side_effect = RuntimeError("insert failed")
                with self.assertRaisesRegex(RuntimeError, "insert failed"):
                    module.processar_indicador_ine(ano=2025, gravar_bd=True)
                calls.csv.assert_not_called()
                calls.database.side_effect = None
                calls.csv.side_effect = OSError("disk full")
                with self.assertRaisesRegex(OSError, "disk full"):
                    module.processar_indicador_ine(ano=2025)

    def test_reruns_other_years_empty_preservation_and_rollback(self):
        for code in INDICATORS:
            module = self.module(code)
            engine = create_engine("sqlite:///:memory:")
            try:
                with self.subTest(code=code), patch.object(
                    ine_output, "get_engine", return_value=engine
                ), patch.object(engine, "dispose"):
                    self.process(module, [record(valor="1")], year=2024,
                                 gravar_bd=True)
                    self.process(module, [record(valor="2")], gravar_bd=True)
                    self.process(module, [record(valor="3")], gravar_bd=True)
                    self.process(module, [], gravar_bd=True)
                    with engine.connect() as connection:
                        before = list(connection.execute(text(
                            f"SELECT ano, {module.VALUE_COLUMN} "
                            f"FROM {module.TABLE_NAME} ORDER BY ano"
                        )))
                    self.assertEqual(before, [(2024, 1), (2025, 3)])
                    duplicate = self.process(module, [record()])
                    duplicate = pd.concat([duplicate, duplicate])
                    with self.assertRaisesRegex(RuntimeError, "rolled back"):
                        ine_output.replace_period_data(
                            duplicate, module.TABLE_NAME, module.CREATE_TABLE_SQL,
                            2025, engine=engine,
                        )
                    with engine.connect() as connection:
                        after = list(connection.execute(text(
                            f"SELECT ano, {module.VALUE_COLUMN} "
                            f"FROM {module.TABLE_NAME} ORDER BY ano"
                        )))
                    self.assertEqual(after, before)
                    self.assertEqual(
                        inspect(engine).get_pk_constraint(module.TABLE_NAME)[
                            "constrained_columns"
                        ], [*module.COLUMN_LENGTHS, "ano"],
                    )
            finally:
                engine.dispose()

    def test_cli_codes_modes_paths_month_rejection_and_all_years(self):
        for code in INDICATORS:
            module = self.module(code)
            for cli_code in (code, str(int(code))):
                for flags in (["--csv"], ["--database"], ["--database", "--csv"]):
                    with self.subTest(code=cli_code, flags=flags), patch.object(
                        module, "processar_indicador_ine",
                        return_value=pd.DataFrame({"ano": [2025]}),
                    ) as process:
                        self.assertEqual(cli.main([
                            "-i", cli_code, "-y", "2025", *flags,
                        ]), 0)
                        process.assert_called_once_with(
                            varcd=code, ano=2025, exportar_csv="--csv" in flags,
                            gravar_bd="--database" in flags,
                            caminho_csv=Path(f"/tmp/ine_{code}_2025_tratado.csv")
                            if "--csv" in flags else None,
                        )
            with contextlib.redirect_stderr(io.StringIO()), \
                    self.assertRaises(SystemExit) as error:
                cli.main(["-i", code, "-y", "2025", "-m", "1", "--csv"])
            self.assertEqual(error.exception.code, 2)
            with patch.object(cli, "fetch_available_annual_years",
                              return_value=[2024, 2025]), patch.object(
                module, "processar_indicador_ine",
                side_effect=[pd.DataFrame({"ano": [2024]}),
                             pd.DataFrame({"ano": [2025]})],
            ) as process:
                self.assertEqual(cli.main(["-i", code, "--all-years", "--database"]), 0)
                self.assertEqual([c.kwargs["ano"] for c in process.call_args_list],
                                 [2024, 2025])


class AnnualApiValidationTests(unittest.TestCase):
    def test_missing_required_dimensions_fail_before_data_request(self):
        for code in INDICATORS:
            module = importlib.import_module(f"pistadigital.flows.ine_{code}_flow")
            for dimension in (("2",) if code == "0008350" else ("2", "3")):
                meta = metadata()
                categories = meta[0]["Dimensoes"]["Categoria_Dim"][0]["categories"]
                categories[:] = [
                    cat for cat in categories if cat["dim_num"] != dimension
                ]
                with self.subTest(code=code, dimension=dimension), patch.object(
                    annual, "fetch_indicator_metadata", return_value=meta,
                ), patch.object(annual, "fetch_annual_indicator_data") as fetch:
                    with self.assertRaisesRegex(RuntimeError, "missing dimension"):
                        module.processar_indicador_ine(ano=2025, exportar_csv=False)
                    fetch.assert_not_called()

    def test_exact_period_request_and_response_validation(self):
        for code in INDICATORS:
            response = Mock()
            response.json.return_value = [{"Dados": {"2025": []}}]
            with patch.object(ine_api.requests, "get", return_value=response) as get:
                ine_api.fetch_annual_indicator_data(code, 2025)
            self.assertIn(f"varcd={code}", get.call_args.args[0])
            self.assertIn("Dim1=S7A2025", get.call_args.args[0])
            response.raise_for_status.assert_called_once_with()
        for payload in (
            [], {}, [{"Dados": None}], [{"Dados": {"2024": []}}],
            [{"Dados": {"2025": [], "2024": []}}],
            [{"Dados": [record()]}],
            [{"Dados": {"2025": [record(anocod="2024")]}}],
        ):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                ine_api.annual_records(payload, 2025)
        self.assertEqual(ine_api.annual_records(
            [{"Dados": [record(anocod="2025")]}], 2025
        ), [record(anocod="2025")])

    def test_malformed_or_wrong_frequency_metadata(self):
        monthly = metadata()
        monthly[0]["Periodic"] = "Mensal"
        for value in ([], {}, monthly, [{"Periodic": "Anual", "Dimensoes": None}]):
            with self.subTest(metadata=value), self.assertRaises(ValueError):
                ine_api.annual_dimension_labels(value, 2025)
        with self.assertRaisesRegex(ValueError, "not listed"):
            ine_api.annual_dimension_labels(metadata(2024), 2025)

    def test_api_failure_propagates(self):
        for stage in ("fetch_indicator_metadata", "fetch_annual_indicator_data"):
            with patch.object(annual, "fetch_indicator_metadata",
                              return_value=metadata()), patch.object(
                annual, stage, side_effect=RuntimeError("API unavailable"),
            ), patch.object(annual, "write_csv") as csv:
                with self.assertRaisesRegex(RuntimeError, "API unavailable"):
                    importlib.import_module(
                        "pistadigital.flows.ine_0009930_flow"
                    ).processar_indicador_ine()
                csv.assert_not_called()


if __name__ == "__main__":
    unittest.main()
