import contextlib
from copy import deepcopy
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import pandas as pd
from sqlalchemy import create_engine, text

from pistadigital.cli import ine_flows as cli
from pistadigital.utils import ine_api as api
from pistadigital.flows import ine_0009808_flow as flow
from pistadigital.utils import ine_monthly as monthly
from pistadigital.utils.ine_output import replace_period_data


def metadata():
    return [{
        "IndicadorCod": "0009808", "Periodic": "Mensal",
        "Dimensoes": {"Categoria_Dim": [{"categories": [
            {"dim_num": dimension, "categ_cod": code, "categ_dsg": label}
            for dimension, labels in {
                "1": {"S3A202607": "Julho de 2026", "S3A202608": "Agosto de 2026"},
                "2": {"PT": "Portugal", "1": "Continente", "11": "Norte"},
                "3": {"T": "Total", "01": "Hotelaria", "0101": "Hotéis"},
            }.items()
            for code, label in labels.items()
        ]}]},
    }]


def payload():
    return [{"Dados": {"Agosto de 2026": [
        {"geocod": "PT", "dim_3": "T", "valor": "0"},
        {"geocod": "1", "dim_3": "01", "valor": ".."},
        {"geocod": "11", "dim_3": "0101", "valor": "12,5"},
        {"geocod": "11", "dim_3": "T", "valor": "x"},
    ]}}]


class MonthlyFlowTests(unittest.TestCase):
    def setUp(self):
        self.meta = patch.object(monthly, "fetch_indicator_metadata", return_value=metadata())
        self.data = patch.object(monthly, "fetch_monthly_indicator_data", return_value=payload())
        self.fetch_meta = self.meta.start()
        self.fetch_data = self.data.start()
        self.addCleanup(self.meta.stop)
        self.addCleanup(self.data.stop)

    def process(self, **options):
        return flow.processar_indicador_ine(
            ano=2026, mes=8, exportar_csv=False, **options,
        )

    def test_schema_hierarchy_metrics_and_period(self):
        frame = self.process()
        self.assertEqual(frame.columns.tolist(), flow.COLUMNS)
        self.assertEqual(len(frame), 4)
        self.assertEqual(frame.ano.tolist(), [2026] * 4)
        self.assertEqual(frame.mes.tolist(), ["08"] * 4)
        self.assertEqual(frame.iloc[0].nuts_i, "Portugal")
        self.assertEqual(frame.iloc[0].nuts_ii, "Total")
        self.assertEqual(frame.iloc[2].nuts_i, "Continente")
        self.assertEqual(frame.iloc[2].nuts_ii, "Norte")
        self.assertEqual(frame.iloc[2].tipo_alojamento, "Hotelaria")
        self.assertEqual(frame.iloc[2].subtipo_alojamento, "Hotéis")
        self.assertEqual(frame.iloc[0].dormidas, 0)
        self.assertEqual(frame.iloc[2].dormidas, 12.5)
        self.assertTrue(pd.isna(frame.iloc[1].dormidas))
        self.assertTrue(pd.isna(frame.iloc[3].dormidas))
        self.fetch_data.assert_called_once_with("0009808", 2026, 8)
        self.assertIn("mes CHAR(2) NOT NULL", flow.CREATE_TABLE_SQL)
        self.assertIn(
            "PRIMARY KEY (nuts_i, nuts_ii, tipo_alojamento, subtipo_alojamento, ano, mes)",
            flow.CREATE_TABLE_SQL,
        )

    def test_csv_only_and_database_first(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "month.csv"
            with patch.object(monthly, "replace_period_data") as database:
                frame = flow.processar_indicador_ine(
                    ano=2026, mes=8, caminho_csv=target,
                )
                database.assert_not_called()
            exported = pd.read_csv(target, dtype={"mes": str})
            self.assertEqual(exported.mes.tolist(), ["08"] * 4)
            self.assertEqual(exported.columns.tolist(), flow.COLUMNS)
        order = Mock()
        with patch.object(monthly, "replace_period_data", order.database), patch.object(
            monthly, "write_csv", order.csv,
        ):
            flow.processar_indicador_ine(ano=2026, mes=8, gravar_bd=True)
        self.assertEqual([call[0] for call in order.mock_calls], ["database", "csv"])
        self.assertEqual(order.database.call_args.args[1:],
                         (flow.TABLE_NAME, flow.CREATE_TABLE_SQL, 2026, 8))
        self.assertEqual(len(frame), 4)
        with patch.object(monthly, "replace_period_data", side_effect=RuntimeError("DB down")), patch.object(
            monthly, "write_csv",
        ) as csv:
            with self.assertRaisesRegex(RuntimeError, "DB down"):
                flow.processar_indicador_ine(ano=2026, mes=8, gravar_bd=True)
            csv.assert_not_called()

    def test_invalid_arguments_before_network(self):
        for options in ({"mes": None}, {"mes": 0}, {"mes": True}, {"ano": 0},
                        {"varcd": "0009877"}, {"caminho_csv": "bad.csv"}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                flow.processar_indicador_ine(
                    **({"ano": 2026, "mes": 8, "exportar_csv": False} | options)
                )
        self.fetch_meta.assert_not_called()
        self.fetch_data.assert_not_called()

    def test_invalid_metadata_and_unpublished_period(self):
        for change in ("annual", "unpublished", "missing", "long"):
            meta = metadata()
            if change == "annual":
                meta[0]["Periodic"] = "Anual"
            else:
                categories = meta[0]["Dimensoes"]["Categoria_Dim"][0]["categories"]
                if change == "unpublished":
                    categories[:] = [c for c in categories if c["categ_cod"] != "S3A202608"]
                elif change == "missing":
                    categories[:] = [c for c in categories if c["dim_num"] != "3"]
                else:
                    next(c for c in categories if c["categ_cod"] == "0101")["categ_dsg"] = "a" * 65
            self.fetch_meta.return_value = meta
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                self.process()

    def test_rejects_foreign_malformed_and_duplicate_records(self):
        invalid = [
            [{"Dados": {"Julho de 2026": []}}],
            [{"Dados": {"Agosto de 2026": [], "Julho de 2026": []}}],
            [{"Dados": {"Agosto de 2026": {}}}],
            [{"Dados": []}],
        ]
        for changes in ({"anocod": 2025}, {"mescod": "07"}, {"geocod": "99"},
                        {"dim_3": "9999"}, {"valor": "bad"}, {"valor": True},
                        {"valor": "NaN"}, {"valor": "inf"}):
            data = payload()
            data[0]["Dados"]["Agosto de 2026"][0].update(changes)
            invalid.append(data)
        duplicate = payload()
        duplicate[0]["Dados"]["Agosto de 2026"].append(
            deepcopy(duplicate[0]["Dados"]["Agosto de 2026"][0])
        )
        invalid.append(duplicate)
        for data in invalid:
            self.fetch_data.return_value = data
            with self.subTest(data=data), self.assertRaises(RuntimeError):
                self.process()

    def test_empty_result_and_network_failure(self):
        self.fetch_data.return_value = [{"Dados": {"Agosto de 2026": []}}]
        frame = self.process()
        self.assertTrue(frame.empty)
        self.assertEqual(frame.columns.tolist(), flow.COLUMNS)
        self.fetch_data.side_effect = RuntimeError("API unavailable")
        with patch.object(monthly, "write_csv") as csv, self.assertRaisesRegex(
            RuntimeError, "API unavailable",
        ):
            flow.processar_indicador_ine(ano=2026, mes=8)
        csv.assert_not_called()

    def test_cli_period_flags_and_default_filename(self):
        with patch.object(flow, "processar_indicador_ine", return_value=pd.DataFrame({"ano": [2026]})) as process:
            self.assertEqual(cli.main(["-i", "9808", "-y", "2026", "-m", "8", "--csv"]), 0)
            self.assertEqual(process.call_args.kwargs["mes"], 8)
            self.assertEqual(
                process.call_args.kwargs["caminho_csv"],
                Path("/tmp/ine_0009808_2026_08_tratado.csv"),
            )
            cli.main(["-i", "9808", "-y", "2026", "-m", "7", "--csv", "-o", "/tmp/custom.csv"])
            self.assertEqual(process.call_args.kwargs["caminho_csv"], Path("/tmp/custom.csv"))
            for args in (["-y", "2026"], ["--all-years"], ["-y", "2026", "-m", "13"]):
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    cli.main(["-i", "9808", "--csv", *args])


class MonthlyApiTests(unittest.TestCase):
    def test_exact_selector_and_latest_period(self):
        response = Mock()
        response.json.return_value = payload()
        with patch.object(api.requests, "get", return_value=response) as get:
            self.assertEqual(api.fetch_monthly_indicator_data("0009808", 2026, 8), payload())
        get.assert_called_once_with(
            f"{api.DATA_URL}?op=2&varcd=0009808&lang=PT&Dim1=S3A202608",
            headers={"Content-Type": "application/json"}, timeout=120,
        )
        response.raise_for_status.assert_called_once()
        self.assertEqual(api.available_monthly_periods(metadata()), [(2026, 7), (2026, 8)])
        bad = metadata()
        bad[0]["Dimensoes"]["Categoria_Dim"][0]["categories"][0]["categ_cod"] = "S7A2026"
        with self.assertRaisesRegex(ValueError, "Unsupported monthly period"):
            api.available_monthly_periods(bad)


class MonthlyDatabaseTests(unittest.TestCase):
    def test_padded_month_isolation_empty_preservation_and_rollback(self):
        engine = create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        row = {
            "nuts_i": "Portugal", "nuts_ii": "Total",
            "tipo_alojamento": "Total", "subtipo_alojamento": "Total",
            "ano": 2026, "mes": "08", "dormidas": 1,
            "create_date": None, "update_date": None,
        }

        def replace(rows, year=2026, month=8):
            return replace_period_data(
                pd.DataFrame(rows, columns=flow.COLUMNS),
                flow.TABLE_NAME, flow.CREATE_TABLE_SQL, year, month, engine=engine,
            )

        replace([row])
        replace([row | {"mes": "07", "dormidas": 7}], month=7)
        replace([row | {"ano": 2025, "dormidas": 5}], year=2025)
        replace([row | {"dormidas": 8}])
        self.assertEqual(replace([]), 0)
        with self.assertRaisesRegex(RuntimeError, "rolled back"):
            replace([row, row])
        with engine.connect() as connection:
            rows = connection.execute(text(
                "SELECT ano, mes, dormidas FROM ine_0009808_ds ORDER BY ano, mes"
            )).all()
        self.assertEqual(rows, [(2025, "08", 5), (2026, "07", 7), (2026, "08", 8)])
        with self.assertRaisesRegex(ValueError, "mes=08"):
            replace([row | {"mes": "07"}])
        with self.assertRaisesRegex(ValueError, "ano=2026"):
            replace([row | {"ano": 2025}])
