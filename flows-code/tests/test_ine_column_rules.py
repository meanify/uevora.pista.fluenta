"""Column-rule contracts across every registered INE flow."""

import importlib
from functools import partial
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd
from sqlalchemy import create_engine, text

from pistadigital.cli.ine_flows import INDICATORS
from pistadigital.utils import ine_annual, ine_monthly, ine_output


RURAL_LABEL = "Turismo no Espaço Rural e de Habitação"
GEOGRAPHY = {
    "PT": "Portugal", "1": "Continente", "11": "Norte",
    "111": "Alto Minho", "1111601": "Arcos de Valdevez",
}
ACCOMMODATION = {
    "T": "Total", "01": "Hotelaria", "0101": "Hotéis",
    "010115": "5 estrelas", "02": "ALOJAMENTO LOCAL",
    "03": "Turismo RURAL", "04": "Turismo de HABITAÇÃO",
}


def metadata(monthly):
    period = "S3A202508" if monthly else "S7A2025"
    label = "Agosto de 2025" if monthly else "2025"
    return [{
        "Periodic": "Mensal" if monthly else "Anual",
        "Dimensoes": {"Categoria_Dim": [{"categories": [
            {"dim_num": dimension, "categ_cod": code, "categ_dsg": name}
            for dimension, labels in {
                "1": {period: label}, "2": GEOGRAPHY, "3": ACCOMMODATION,
            }.items() for code, name in labels.items()
        ]}]},
    }]


class IneColumnRuleTests(unittest.TestCase):
    def process(self, module, rows, **options):
        runner = ine_monthly if module.MONTHLY else ine_annual
        fetch = "fetch_monthly_indicator_data" if module.MONTHLY else "fetch_annual_indicator_data"
        period = "Agosto de 2025" if module.MONTHLY else "2025"
        with patch.object(runner, "fetch_indicator_metadata",
                          return_value=metadata(module.MONTHLY)), \
                patch.object(runner, fetch, return_value=[{"Dados": {period: rows}}]):
            return module.processar_indicador_ine(
                ano=2025, **({"mes": 8} if module.MONTHLY else {}), **options,
            )

    def test_registered_flows_apply_rules_before_both_outputs(self):
        for code, path in INDICATORS.items():
            module = importlib.import_module(path)
            municipal = "municipio" in module.SCHEMA_COLUMNS
            runner = ine_monthly if module.MONTHLY else ine_annual
            rows = [
                {"geocod": geography, "dim_3": "02", "valor": "0"}
                for geography in (GEOGRAPHY if municipal else ("PT", "1", "11"))
            ]
            with self.subTest(code=code), \
                    patch.object(runner, "replace_period_data") as database, \
                    patch.object(runner, "write_csv") as csv:
                frame = self.process(module, rows, gravar_bd=True)
                self.assertEqual(frame.columns.tolist(), module.SCHEMA_COLUMNS)
                self.assertEqual(len(frame), 1)
                self.assertTrue(frame[module.VALUE_COLUMN].eq(0).all())
                self.assertEqual(frame.index.tolist(), list(range(len(frame))))
                if municipal:
                    self.assertEqual(frame.iloc[0]["municipio"], "Arcos de Valdevez")
                else:
                    self.assertEqual(frame.iloc[0]["nuts_ii"], "Norte")
                pd.testing.assert_frame_equal(database.call_args.args[0], frame)
                pd.testing.assert_frame_equal(csv.call_args.args[0], frame)

    def test_all_accommodation_flows_normalize_only_existing_targets(self):
        cases = [
            ("alojamento local", "Alojamento Local", "Alojamento Local"),
            ("ALOJAMENTO LOCAL", "Alojamento Local", "Alojamento Local"),
            ("Turismo RURAL", RURAL_LABEL, RURAL_LABEL),
            ("Turismo rural e de habitação", RURAL_LABEL, RURAL_LABEL),
            ("Turismo de HABITAÇÃO", "Subtype", RURAL_LABEL),
            ("Hotelaria", "Subtype", "Classification"),
            ("Outro alojamento local", "Subtype", "Classification"),
        ]
        for code, path in INDICATORS.items():
            module = importlib.import_module(path)
            if "tipo_alojamento" not in module.SCHEMA_COLUMNS:
                continue
            for label, subtype, classification in cases:
                with self.subTest(code=code, label=label):
                    labels = {"01": label, "0101": "Subtype", "010115": "Classification"}
                    row = {"geocod": "11", "dim_3": "0101" if module.MONTHLY else "010115"}
                    result = module.transform_dimensions(row, {"2": GEOGRAPHY, "3": labels})
                    self.assertEqual(result["tipo_alojamento"], label)
                    self.assertEqual(result["subtipo_alojamento"], subtype)
                    if "classificacao" in module.SCHEMA_COLUMNS:
                        self.assertEqual(result["classificacao"], classification)
                    else:
                        self.assertNotIn("classificacao", result)
                    self.assertEqual(labels["0101"], "Subtype")

    def test_accommodation_outputs_keep_total_and_leaf_codes(self):
        for code, path in INDICATORS.items():
            module = importlib.import_module(path)
            if "tipo_alojamento" not in module.SCHEMA_COLUMNS:
                continue
            runner = ine_monthly if module.MONTHLY else ine_annual
            geography = "11" if module.MONTHLY else "1111601"
            rows = [
                {"geocod": geography, "dim_3": category, "valor": value}
                for category, value in (("T", "9"), ("01", "9"), ("02", "0"), ("03", ".."), ("04", "2,5"))
            ]
            with self.subTest(code=code), \
                    patch.object(runner, "replace_period_data") as database, \
                    patch.object(runner, "write_csv") as csv:
                frame = self.process(module, rows, gravar_bd=True)
                self.assertEqual(frame["subtipo_alojamento"].tolist(),
                                 ["Total", "Alojamento Local", RURAL_LABEL, "Turismo de HABITAÇÃO"])
                if "classificacao" in frame.columns:
                    self.assertEqual(frame["classificacao"].tolist(),
                                     ["Total", "Alojamento Local", RURAL_LABEL, RURAL_LABEL])
                self.assertEqual(frame[module.VALUE_COLUMN].tolist()[:2], [9, 0])
                self.assertTrue(pd.isna(frame.iloc[2][module.VALUE_COLUMN]))
                self.assertEqual(frame.iloc[3][module.VALUE_COLUMN], 2.5)
                pd.testing.assert_frame_equal(database.call_args.args[0], frame)
                pd.testing.assert_frame_equal(csv.call_args.args[0], frame)

    def test_filtered_empty_csv_preserves_headers_without_database_access(self):
        for code, path in INDICATORS.items():
            module = importlib.import_module(path)
            if "municipio" not in module.SCHEMA_COLUMNS:
                continue
            with self.subTest(code=code), tempfile.TemporaryDirectory() as directory, \
                    patch.object(ine_output, "get_engine",
                                 side_effect=AssertionError("DB access")):
                output = Path(directory) / "out.csv"
                frame = self.process(module, [
                    {"geocod": "PT", "dim_3": "T", "valor": "0"},
                ], caminho_csv=output)
                self.assertTrue(frame.empty)
                self.assertEqual(pd.read_csv(output).columns.tolist(), module.SCHEMA_COLUMNS)

    def test_normalization_collisions_fail_without_silent_deduplication(self):
        for code, path in INDICATORS.items():
            module = importlib.import_module(path)
            if "tipo_alojamento" not in module.SCHEMA_COLUMNS:
                continue
            runner = ine_monthly if module.MONTHLY else ine_annual
            meta = metadata(module.MONTHLY)
            meta[0]["Dimensoes"]["Categoria_Dim"][0]["categories"].append(
                {"dim_num": "3", "categ_cod": "0201", "categ_dsg": "Subtype"},
            )
            geography = "11" if module.MONTHLY else "1111601"
            rows = [
                {"geocod": geography, "dim_3": category, "valor": "1"}
                for category in ("02", "0201")
            ]
            period = "Agosto de 2025" if module.MONTHLY else "2025"
            fetch = "fetch_monthly_indicator_data" if module.MONTHLY else "fetch_annual_indicator_data"
            with self.subTest(code=code), \
                    patch.object(runner, "fetch_indicator_metadata", return_value=meta), \
                    patch.object(runner, fetch, return_value=[{"Dados": {period: rows}}]), \
                    patch.object(runner, "write_csv") as csv, \
                    patch.object(runner, "replace_period_data") as database, \
                    self.assertRaisesRegex(RuntimeError, "duplicate primary keys"):
                module.processar_indicador_ine(
                    ano=2025, gravar_bd=True, **({"mes": 8} if module.MONTHLY else {}),
                )
            csv.assert_not_called()
            database.assert_not_called()

    def test_filtered_empty_period_keeps_existing_database_rows(self):
        for code, path in INDICATORS.items():
            module = importlib.import_module(path)
            if "municipio" not in module.SCHEMA_COLUMNS:
                continue
            runner = ine_monthly if module.MONTHLY else ine_annual
            engine = create_engine("sqlite:///:memory:")
            try:
                with self.subTest(code=code), \
                        patch.object(
                            runner, "replace_period_data",
                            side_effect=partial(ine_output.replace_period_data, engine=engine),
                        ):
                    self.process(module, [
                        {"geocod": "1111601", "dim_3": "02", "valor": "2,5"},
                    ], exportar_csv=False, gravar_bd=True)
                    frame = self.process(module, [
                        {"geocod": "PT", "dim_3": "T", "valor": "0"},
                    ], exportar_csv=False, gravar_bd=True)
                    self.assertTrue(frame.empty)
                    with engine.connect() as connection:
                        stored = connection.execute(text(
                            f"SELECT municipio, {module.VALUE_COLUMN} FROM {module.TABLE_NAME}"
                        )).all()
                    self.assertEqual(stored, [("Arcos de Valdevez", 2.5)])
            finally:
                engine.dispose()
