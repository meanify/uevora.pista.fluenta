"""Shared monthly-flow contract tests."""

import importlib
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import pandas as pd
from sqlalchemy import create_engine, text

from pistadigital.cli import ine_flows as cli
from pistadigital.utils import ine_monthly as monthly
from pistadigital.utils.ine_output import replace_period_data


INDICATORS = {
    "0012093": ("hospedes", True),
    "0009812": ("hospedes", True),
    "0010735": ("dormidas", False),
    "0010736": ("hospedes", False),
}


def metadata(code="0012093"):
    accommodation = INDICATORS[code][1]
    geography = (
        {"PT": "Portugal", "1": "Continente", "1D": "Grande Lisboa"}
        if code == "0012093" else
        {"PT": "Portugal", "1": "Continente", "11": "Norte", "11A": "Porto",
         "11A1304": "Maia", "2": "Acores", "20": "Acores",
         "200": "Acores", "2004201": "Lagoa"}
    )
    categories = {"T": "Total", "01": "Hotelaria"}
    categories.update(
        {"0101": "Hoteis"} if accommodation else
        {"02": "Alojamento local", "03": "Turismo no espaco rural"}
    )
    return [{
        "Periodic": "Mensal",
        "Dimensoes": {"Categoria_Dim": [{"categories": [
            {"dim_num": dim, "categ_cod": code, "categ_dsg": label}
            for dim, values in {
                "1": {"S3A202608": "Agosto de 2026"},
                "2": geography,
                "3": categories,
            }.items() for code, label in values.items()
        ]}]},
    }]


def record(**options):
    return {"geocod": "1D", "dim_3": "0101", "valor": "12,5"} | options


class MonthlyFlowTests(unittest.TestCase):
    def process(self, code, rows, **options):
        module = importlib.import_module(f"pistadigital.utils.ine_{code}_flow")
        rows = [
            (row | {
                "geocod": ("11" if INDICATORS[code][1] else "11A1304")
                if row.get("geocod") == "1D" else row.get("geocod"),
                "dim_3": "01" if not INDICATORS[code][1] and row.get("dim_3") == "0101"
                else row.get("dim_3"),
            }) if isinstance(row, dict) and code != "0012093" else row
            for row in rows
        ]
        with patch.object(monthly, "fetch_indicator_metadata", return_value=metadata(code)), \
                patch.object(monthly, "fetch_monthly_indicator_data",
                             return_value=[{"Dados": {"Agosto de 2026": rows}}]) as fetch:
            frame = module.processar_indicador_ine(
                **({"ano": 2026, "mes": 8, "exportar_csv": False} | options)
            )
        fetch.assert_called_once_with(code, 2026, 8)
        return frame

    def test_mapping_metrics_schema_and_period(self):
        for code, (metric, accommodation) in INDICATORS.items():
            with self.subTest(code=code):
                module = importlib.import_module(f"pistadigital.utils.ine_{code}_flow")
                frame = self.process(code, [
                    record(), record(geocod="PT", dim_3="T", valor="0"),
                    record(geocod="1", dim_3="01", valor=".."),
                ])
                self.assertEqual(frame.columns.tolist(), module.SCHEMA_COLUMNS)
                self.assertEqual(frame.iloc[0].nuts_i, "Continente")
                self.assertEqual(frame.iloc[0].nuts_ii, "Grande Lisboa" if code == "0012093" else "Norte")
                self.assertEqual(frame.iloc[1].nuts_i, "Portugal")
                self.assertEqual(frame.iloc[1].nuts_ii, "Total")
                self.assertEqual(frame.iloc[0][metric], 12.5)
                self.assertEqual(frame.iloc[1][metric], 0)
                self.assertTrue(pd.isna(frame.iloc[2][metric]))
                self.assertTrue(frame.ano.eq(2026).all())
                self.assertTrue(frame.mes.eq("08").all())
                if accommodation:
                    self.assertEqual(frame.iloc[0].tipo_alojamento, "Hotelaria")
                    self.assertEqual(frame.iloc[0].subtipo_alojamento, "Hoteis")
                else:
                    self.assertEqual(frame.iloc[0].segmento_alojamento, "Hotelaria")
                    self.assertEqual(frame.iloc[0].nuts_iii, "Porto")
                    self.assertEqual(frame.iloc[0].municipio, "Maia")
                    self.assertEqual(frame.iloc[0].distrito, "Porto")
                self.assertIn("mes CHAR(2) NOT NULL", module.CREATE_TABLE_SQL)
                if code == "0009812":
                    self.assertEqual(module.TABLE_NAME, "ine_0009812_monthly")
                self.assertIn(
                    ", ".join([*module.COLUMN_LENGTHS, "ano", "mes"]),
                    " ".join(module.CREATE_TABLE_SQL.split()),
                )

    def test_rejects_bad_rows_and_metadata_before_output(self):
        for code in INDICATORS:
            for rows in (
                [record(), record()], [record(anocod=2025)], [record(mescod="07")],
                [record(geocod="unknown")], [record(dim_3="unknown")],
                [record(valor="NaN")], [record(valor=True)], [None],
            ):
                with self.subTest(code=code, rows=rows), \
                        patch.object(monthly, "write_csv") as csv, \
                        patch.object(monthly, "replace_period_data") as database, \
                        self.assertRaises(RuntimeError):
                    self.process(code, rows, exportar_csv=True, gravar_bd=True)
                csv.assert_not_called()
                database.assert_not_called()
            module = importlib.import_module(f"pistadigital.utils.ine_{code}_flow")
            for options in ({"mes": None}, {"mes": 13}, {"ano": True}, {"varcd": "wrong"}):
                with patch.object(monthly, "fetch_indicator_metadata") as fetch, self.assertRaises(ValueError):
                    module.processar_indicador_ine(**({"ano": 2026, "mes": 8} | options))
                fetch.assert_not_called()
            with patch.object(monthly, "fetch_indicator_metadata", return_value=[{"Periodic": "Anual"}]), \
                    patch.object(monthly, "fetch_monthly_indicator_data") as fetch, self.assertRaises(RuntimeError):
                module.processar_indicador_ine(ano=2026, mes=8)
            fetch.assert_not_called()

    def test_foreign_periods_malformed_payloads_and_unpublished_months(self):
        for code in INDICATORS:
            module = importlib.import_module(f"pistadigital.utils.ine_{code}_flow")
            for payload in (
                [], {}, [{"Dados": []}], [{"Dados": {"Agosto de 2026": {}}}],
                [{"Dados": {"Julho de 2026": []}}],
                [{"Dados": {"Agosto de 2026": [], "Julho de 2026": []}}],
            ):
                with self.subTest(code=code, payload=payload), \
                        patch.object(monthly, "fetch_indicator_metadata", return_value=metadata(code)), \
                        patch.object(monthly, "fetch_monthly_indicator_data", return_value=payload), \
                        patch.object(monthly, "write_csv") as csv, \
                        patch.object(monthly, "replace_period_data") as database, \
                        self.assertRaises(RuntimeError):
                    module.processar_indicador_ine(ano=2026, mes=8, gravar_bd=True)
                csv.assert_not_called()
                database.assert_not_called()
            for dimension in ("1", "2", "3"):
                meta = metadata(code)
                categories = meta[0]["Dimensoes"]["Categoria_Dim"][0]["categories"]
                categories[:] = [c for c in categories if c["dim_num"] != dimension]
                with patch.object(monthly, "fetch_indicator_metadata", return_value=meta), \
                        patch.object(monthly, "fetch_monthly_indicator_data") as fetch, \
                        self.assertRaises(RuntimeError):
                    module.processar_indicador_ine(ano=2026, mes=8)
                fetch.assert_not_called()

    def test_length_validation_and_unknown_ancestor(self):
        for code, (_, accommodation) in INDICATORS.items():
            module = importlib.import_module(f"pistadigital.utils.ine_{code}_flow")
            meta = metadata(code)
            categories = meta[0]["Dimensoes"]["Categoria_Dim"][0]["categories"]
            next(c for c in categories if c["dim_num"] == "3" and c["categ_cod"] == "01")["categ_dsg"] = "X" * 65
            row = record(geocod="PT", dim_3="01")
            with patch.object(monthly, "fetch_indicator_metadata", return_value=meta), \
                    patch.object(monthly, "fetch_monthly_indicator_data",
                                 return_value=[{"Dados": {"Agosto de 2026": [row]}}]), \
                    self.assertRaisesRegex(RuntimeError, "exceed"):
                module.processar_indicador_ine(ano=2026, mes=8, exportar_csv=False)
            if not accommodation:
                frame = self.process(code, [record(geocod="2004201")])
                self.assertEqual(frame.iloc[0].distrito, "São Miguel")
            for marker in (None, "", "s.r.", "x"):
                frame = self.process(code, [record(valor=marker)])
                self.assertTrue(pd.isna(frame.iloc[0][module.VALUE_COLUMN]))

    def test_outputs_csv_empty_and_cli(self):
        for code in INDICATORS:
            module = importlib.import_module(f"pistadigital.utils.ine_{code}_flow")
            order = Mock()
            with patch.object(monthly, "replace_period_data", order.database), \
                    patch.object(monthly, "write_csv", order.csv):
                self.process(code, [record()], exportar_csv=True, gravar_bd=True)
            self.assertEqual([call[0] for call in order.mock_calls], ["database", "csv"])
            self.assertEqual(order.database.call_args.args[-2:], (2026, 8))
            with tempfile.TemporaryDirectory() as directory, \
                    patch.object(monthly, "replace_period_data", side_effect=AssertionError("DB access")):
                path = Path(directory) / "empty.csv"
                empty = self.process(code, [], exportar_csv=True, caminho_csv=path)
                self.assertTrue(empty.empty)
                self.assertEqual(path.read_text().strip(), ",".join(module.SCHEMA_COLUMNS))
            with patch.object(module, "processar_indicador_ine", return_value=pd.DataFrame({"ano": [2026]})) as process:
                self.assertEqual(cli.main(["-i", str(int(code)), "-y", "2026", "-m", "8", "--csv"]), 0)
                self.assertEqual(process.call_args.kwargs["mes"], 8)
                self.assertEqual(process.call_args.kwargs["caminho_csv"],
                                 Path(f"/tmp/ine_{code}_2026_08_tratado.csv"))
                for args in (["-y", "2026"], ["--all-years"], ["-y", "2026", "-m", "13"]):
                    with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                        cli.main(["-i", code, "--csv", *args])

    def test_failures_propagate_without_later_outputs(self):
        for code in INDICATORS:
            module = importlib.import_module(f"pistadigital.utils.ine_{code}_flow")
            with patch.object(monthly, "replace_period_data", side_effect=RuntimeError("DB down")), \
                    patch.object(monthly, "write_csv") as csv, \
                    self.assertRaisesRegex(RuntimeError, "DB down"):
                self.process(code, [record()], gravar_bd=True, exportar_csv=True)
            csv.assert_not_called()
            with patch.object(monthly, "write_csv", side_effect=OSError("disk full")), \
                    self.assertRaisesRegex(OSError, "disk full"):
                self.process(code, [record()], exportar_csv=True)
            with patch.object(monthly, "fetch_indicator_metadata", side_effect=RuntimeError("API down")), \
                    patch.object(monthly, "replace_period_data") as database, \
                    self.assertRaisesRegex(RuntimeError, "API down"):
                module.processar_indicador_ine(ano=2026, mes=8, gravar_bd=True)
            database.assert_not_called()

    def test_database_period_isolation_and_rollback(self):
        for code in INDICATORS:
            module = importlib.import_module(f"pistadigital.utils.ine_{code}_flow")
            frame = self.process(code, [record()])
            engine = create_engine("sqlite://")
            try:
                def write(data, year=2026, month=8):
                    return replace_period_data(
                        data, module.TABLE_NAME, module.CREATE_TABLE_SQL, year, month, engine=engine,
                    )
                write(frame)
                write(frame.assign(mes="07"), month=7)
                write(frame.assign(ano=2025), year=2025)
                write(frame)
                self.assertEqual(write(frame.iloc[:0]), 0)
                with self.assertRaisesRegex(RuntimeError, "rolled back"):
                    write(pd.concat([frame, frame]))
                with engine.connect() as connection:
                    rows = connection.execute(text(
                        f"SELECT ano, mes FROM {module.TABLE_NAME} ORDER BY ano, mes"
                    )).all()
                self.assertEqual(rows, [(2025, "08"), (2026, "07"), (2026, "08")])
            finally:
                engine.dispose()
