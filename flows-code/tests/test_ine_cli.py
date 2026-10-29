import contextlib
import io
import os
from pathlib import Path
import tempfile
import types
import unittest
import subprocess
import sys
from unittest.mock import Mock, patch

import pandas as pd

from pistadigital.cli import ine_flows as cli
from pistadigital.flows import ine_0009808_flow as monthly_flow
from pistadigital.flows import ine_0009929_flow as ine
from pistadigital.utils import ine_annual as annual
from pistadigital.utils import ine_api, ine_output


def api_responses(records):
    metadata = Mock()
    metadata.json.return_value = [{
        "Periodic": "Anual",
        "Dimensoes": {"Categoria_Dim": [{
            "categorias": [
                {"dim_num": "1", "categ_cod": "S7A2024", "categ_dsg": "2024"},
                {"dim_num": "2", "categ_cod": "1", "categ_dsg": "Continente"},
                {"dim_num": "2", "categ_cod": "12", "categ_dsg": "Centro"},
                {"dim_num": "2", "categ_cod": "123", "categ_dsg": "Medio Tejo"},
                {"dim_num": "2", "categ_cod": "1231401", "categ_dsg": "Abrantes"},
                {"dim_num": "3", "categ_cod": "01", "categ_dsg": "Hotelaria"},
            ],
        }]},
    }]
    data = Mock()
    data.json.return_value = [{"Dados": {"2024": records}}]
    return [metadata, data]


RECORD = {
    "geocod": "1231401", "geodsg": "Abrantes", "dim_3": "01",
    "valor": "12,5", "anocod": "2024",
}


def monthly_metadata():
    return [{
        "IndicadorCod": "0009808", "Periodic": "Mensal",
        "Dimensoes": {"Categoria_Dim": [{"categories": [
            {"dim_num": dimension, "categ_cod": code, "categ_dsg": label}
            for dimension, labels in {
                "1": {
                    "S3A202403": "Marco de 2024",
                    "S3A202312": "Dezembro de 2023",
                    "S3A202401": "Janeiro de 2024",
                },
                "2": {"PT": "Portugal", "1": "Continente", "11": "Norte"},
                "3": {"T": "Total"},
            }.items()
            for code, label in labels.items()
        ]}]},
    }]


class CliTests(unittest.TestCase):
    def test_database_csv_and_both(self):
        for flags in (["--database"], ["--csv"], ["--database", "--csv"]):
            with self.subTest(flags=flags), patch.object(
                ine, "processar_indicador_ine", return_value=pd.DataFrame({"ano": [2024]})
            ) as process:
                self.assertEqual(cli.main(["-i", "9929", "-y", "2024", *flags]), 0)
                process.assert_called_once_with(
                    varcd="0009929", ano=2024, exportar_csv="--csv" in flags,
                    gravar_bd="--database" in flags,
                    caminho_csv=(
                        Path("/tmp") / "ine_0009929_2024_tratado.csv"
                        if "--csv" in flags else None
                    ),
                )

    def test_invalid_arguments_fail_before_extraction(self):
        cases = [
            ["-i", "9929", "-y", "2024"],
            ["-i", "9929", "-y", "2024", "--database", "--output", "out.csv"],
            ["-i", "9929", "-y", "2024", "--csv", "--month", "3"],
            ["-i", "9929", "-y", "2024", "--csv", "--month", "13"],
            ["-i", "1234", "-y", "2024", "--csv"],
            ["-i", "9929", "-y", "0", "--csv"],
            ["-i", "9929", "-y", "invalid", "--csv"],
            ["-i", "../module", "-y", "2024", "--csv"],
        ]
        for args in cases:
            with self.subTest(args=args), \
                    patch.object(ine, "processar_indicador_ine") as process, \
                    contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    cli.main(args)
                self.assertEqual(error.exception.code, 2)
                process.assert_not_called()

    def test_processing_failure_returns_nonzero(self):
        for error in (RuntimeError("database unavailable"), OSError("CSV not writable")):
            with self.subTest(error=type(error).__name__), patch.object(
                ine, "processar_indicador_ine", side_effect=error
            ):
                self.assertEqual(cli.main(["-i", "9929", "-y", "2024", "--csv"]), 1)

    def test_all_years_combines_csv_and_preserves_output_selection(self):
        years = [2023, 2024]
        for flags in (["--csv"], ["--database"], ["--database", "--csv"]):
            with self.subTest(flags=flags), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "all-years.csv"
                frames = [
                    pd.DataFrame({"ano": [year], "valor": [year]})
                    for year in years
                ]
                with patch.object(
                    cli, "fetch_available_annual_years", return_value=years
                ) as discover_years, patch.object(
                    ine, "processar_indicador_ine", side_effect=frames
                ) as process:
                    args = ["-i", "9929", "--all-years", *flags]
                    if "--csv" in flags:
                        args.extend(["--output", str(output)])
                    self.assertEqual(cli.main(args), 0)

                discover_years.assert_called_once_with("0009929")
                self.assertEqual(
                    [call.kwargs for call in process.call_args_list],
                    [
                        {
                            "varcd": "0009929",
                            "ano": year,
                            "exportar_csv": False,
                            "gravar_bd": "--database" in flags,
                        }
                        for year in years
                    ],
                )
                if "--csv" in flags:
                    result = pd.read_csv(output)
                    self.assertEqual(result["ano"].tolist(), years)
                    self.assertEqual(len(process.call_args_list), len(years))
                else:
                    self.assertFalse(output.exists())

    def test_all_years_discovery_failure_returns_nonzero(self):
        with patch.object(
            cli, "fetch_available_annual_years",
            side_effect=RuntimeError("metadata unavailable"),
        ), patch.object(ine, "processar_indicador_ine") as process:
            self.assertEqual(cli.main(["-i", "9929", "--all-years", "--database"]), 1)
        process.assert_not_called()

    def test_all_years_processing_failure_returns_nonzero(self):
        with patch.object(
            cli, "fetch_available_annual_years", return_value=[2023, 2024]
        ), patch.object(
            ine, "processar_indicador_ine",
            side_effect=[pd.DataFrame({"ano": [2023]}), RuntimeError("API failure")],
        ) as process:
            result = cli.main(["-i", "9929", "--all-years", "--database"])
        self.assertEqual(result, 1)
        self.assertEqual(process.call_count, 2)

    def test_year_and_all_years_are_mutually_exclusive(self):
        with patch.object(ine, "processar_indicador_ine") as process, \
                contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                cli.main([
                    "-i", "9929", "-y", "2024", "--all-years", "--database",
                ])
        self.assertEqual(error.exception.code, 2)
        process.assert_not_called()

    def test_csv_only_writes_real_file_without_database_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "indicator.csv"
            with patch.dict(os.environ, {}, clear=True), \
                    patch.object(ine_api.requests, "get", side_effect=api_responses([RECORD])), \
                    patch.object(ine_output, "get_engine",
                                 side_effect=AssertionError("Must not connect")), \
                    patch.object(annual, "replace_period_data",
                                 side_effect=AssertionError("Must not write")):
                result = cli.main([
                    "-i", "0009929", "-y", "2024", "--csv", "--output", str(output),
                ])
            self.assertEqual(result, 0)
            df = pd.read_csv(output)
            self.assertEqual(len(df), 1)
            self.assertEqual(df.iloc[0]["distrito"], "Santarém")
            self.assertEqual(df.iloc[0]["rendimento_medio_por_quarto"], 12.5)

    def test_database_only_does_not_export(self):
        with patch.object(ine_api.requests, "get", side_effect=api_responses([RECORD])), \
                patch.object(annual, "replace_period_data") as replace, \
                patch.object(pd.DataFrame, "to_csv") as export:
            self.assertEqual(cli.main(["-i", "9929", "-y", "2024", "--database"]), 0)
        replace.assert_called_once()
        export.assert_not_called()

    def test_future_monthly_module_receives_month(self):
        module = types.SimpleNamespace(
            MONTHLY=True,
            processar_indicador_ine=Mock(return_value=pd.DataFrame({"ano": [2024]})),
        )
        with patch.dict(cli.INDICATORS, {"1234567": "test.monthly"}), \
                patch.object(cli.importlib, "import_module", return_value=module):
            self.assertEqual(cli.main([
                "-i", "1234567", "-y", "2024", "-m", "3", "--database",
            ]), 0)
            self.assertEqual(module.processar_indicador_ine.call_args.kwargs["mes"], 3)
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    cli.main(["-i", "1234567", "-y", "2024", "--database"])

    def test_command_line_entry_point(self):
        entrypoint = Path(__file__).resolve().parents[1] / "ine_flows.py"
        help_result = subprocess.run(
            [sys.executable, str(entrypoint), "--help"], capture_output=True, text=True
        )
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertIn("--database", help_result.stdout)
        self.assertIn("--csv", help_result.stdout)
        self.assertIn("--all-years", help_result.stdout)
        self.assertIn("--all-months", help_result.stdout)
        self.assertIn("--all-years-months", help_result.stdout)
        invalid = subprocess.run(
            [sys.executable, str(entrypoint), "-i", "9929", "-y", "2024"],
            capture_output=True, text=True,
        )
        self.assertEqual(invalid.returncode, 2)
        self.assertIn("Choose at least one output", invalid.stderr)


class MonthlyBatchCliTests(unittest.TestCase):
    def test_batches_select_published_periods_and_preserve_output_modes(self):
        modes = [
            (["-y", "2024", "--all-months"], [(2024, 1), (2024, 3)]),
            (["--all-years-months"], [(2023, 12), (2024, 1), (2024, 3)]),
        ]
        for code in ("9808", "9812", "12093", "10735", "10736"):
            module = cli.importlib.import_module(cli.INDICATORS[code.zfill(7)])
            for selectors, periods in modes:
                for flags in (["--csv"], ["--database"], ["--database", "--csv"]):
                    with self.subTest(code=code, selectors=selectors, flags=flags), \
                            tempfile.TemporaryDirectory() as directory:
                        output = Path(directory) / "batch.csv"
                        frames = [
                            pd.DataFrame({"ano": [year], "mes": [f"{month:02d}"]})
                            for year, month in periods
                        ]
                        with patch.object(
                            cli, "fetch_indicator_metadata", return_value=monthly_metadata()
                        ) as fetch, patch.object(
                            module, "processar_indicador_ine", side_effect=frames
                        ) as process:
                            args = ["-i", code, *selectors, *flags]
                            if "--csv" in flags:
                                args.extend(["--output", str(output)])
                            self.assertEqual(cli.main(args), 0)
                        fetch.assert_called_once_with(code.zfill(7))
                        self.assertEqual(
                            [call.kwargs for call in process.call_args_list],
                            [
                                {
                                    "varcd": code.zfill(7), "ano": year, "mes": month,
                                    "exportar_csv": False, "gravar_bd": "--database" in flags,
                                }
                                for year, month in periods
                            ],
                        )
                        if "--csv" in flags:
                            frame = pd.read_csv(output, dtype={"mes": str})
                            self.assertEqual(
                                list(zip(frame.ano, frame.mes)),
                                [(year, f"{month:02d}") for year, month in periods],
                            )
                        else:
                            self.assertFalse(output.exists())

    def test_default_csv_paths_and_empty_headers(self):
        for selectors, suffix in (
            (["-y", "2024", "--all-months"], "2024_all_months"),
            (["--all-years-months"], "all_years_months"),
        ):
            empty = pd.DataFrame(columns=monthly_flow.SCHEMA_COLUMNS)
            with self.subTest(selectors=selectors), patch.object(
                cli, "fetch_indicator_metadata", return_value=monthly_metadata()
            ), patch.object(
                monthly_flow, "processar_indicador_ine", return_value=empty
            ), patch.object(cli, "write_csv") as write:
                self.assertEqual(cli.main(["-i", "9808", *selectors, "--csv"]), 0)
            write.assert_called_once()
            frame, path = write.call_args.args
            self.assertTrue(frame.empty)
            self.assertEqual(frame.columns.tolist(), monthly_flow.SCHEMA_COLUMNS)
            self.assertEqual(path, Path("/tmp") / f"ine_0009808_{suffix}_tratado.csv")

    def test_invalid_combinations_fail_before_network_or_processing(self):
        cases = [
            ["-i", "9808", "--all-months"],
            ["-i", "9808", "-y", "2024", "--all-months", "-m", "1"],
            ["-i", "9808", "--all-years", "--all-months"],
            ["-i", "9808", "--all-years-months", "--all-months"],
            ["-i", "9808", "--all-years-months", "-y", "2024"],
            ["-i", "9808", "--all-years-months", "--all-years"],
            ["-i", "9808", "--all-years-months", "-m", "1"],
            ["-i", "9808", "--all-years"],
            ["-i", "9929", "-y", "2024", "--all-months"],
            ["-i", "9929", "--all-years-months"],
        ]
        for args in cases:
            with self.subTest(args=args), patch.object(cli, "fetch_indicator_metadata") as fetch, \
                    patch.object(monthly_flow, "processar_indicador_ine") as process, \
                    patch.object(ine, "processar_indicador_ine") as annual_process, \
                    contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    cli.main([*args, "--csv"])
                self.assertEqual(error.exception.code, 2)
                fetch.assert_not_called()
                process.assert_not_called()
                annual_process.assert_not_called()

    def test_discovery_failures_do_not_process_or_export(self):
        for selectors, response in (
            (["--all-years-months"], RuntimeError("metadata unavailable")),
            (["--all-years-months"], [{"Periodic": "Anual"}]),
            (["--all-years-months"], []),
            (["-y", "2025", "--all-months"], monthly_metadata()),
        ):
            with self.subTest(selectors=selectors, response=response), patch.object(
                cli, "fetch_indicator_metadata",
                **({"side_effect": response} if isinstance(response, Exception)
                   else {"return_value": response}),
            ), patch.object(monthly_flow, "processar_indicador_ine") as process, \
                    patch.object(cli, "write_csv") as write, \
                    self.assertLogs(cli.logger, level="ERROR"):
                self.assertEqual(cli.main(["-i", "9808", *selectors, "--csv"]), 1)
            process.assert_not_called()
            write.assert_not_called()

    def test_processing_failure_stops_batch_and_preserves_existing_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "batch.csv"
            output.write_text("existing CSV\n")
            with patch.object(
                cli, "fetch_indicator_metadata", return_value=monthly_metadata()
            ), patch.object(
                monthly_flow, "processar_indicador_ine",
                side_effect=[pd.DataFrame({"ano": [2023]}), RuntimeError("API failure")],
            ) as process, self.assertLogs(cli.logger, level="ERROR"):
                self.assertEqual(cli.main([
                    "-i", "9808", "--all-years-months", "--database", "--csv",
                    "--output", str(output),
                ]), 1)
            self.assertEqual(process.call_count, 2)
            self.assertTrue(all(call.kwargs["gravar_bd"] for call in process.call_args_list))
            self.assertEqual(output.read_text(), "existing CSV\n")

    def test_csv_only_runs_real_monthly_flows_without_database_access(self):
        responses = []
        meta = monthly_metadata()
        discovery = Mock()
        discovery.json.return_value = meta
        responses.append(discovery)
        for label in ("Dezembro de 2023", "Janeiro de 2024", "Marco de 2024"):
            metadata_response, data_response = Mock(), Mock()
            metadata_response.json.return_value = meta
            data_response.json.return_value = [{"Dados": {label: [
                {"geocod": "11", "dim_3": "T", "valor": "0"},
            ]}}]
            responses.extend([metadata_response, data_response])
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "batch.csv"
            with patch.dict(os.environ, {}, clear=True), patch.object(
                ine_api.requests, "get", side_effect=responses
            ) as get, patch.object(
                ine_output, "get_engine", side_effect=AssertionError("Must not connect")
            ):
                self.assertEqual(cli.main([
                    "-i", "9808", "--all-years-months", "--csv", "-o", str(output),
                ]), 0)
            frame = pd.read_csv(output, dtype={"mes": str})
            self.assertEqual(frame.columns.tolist(), monthly_flow.SCHEMA_COLUMNS)
            self.assertEqual(list(zip(frame.ano, frame.mes)), [(2023, "12"), (2024, "01"), (2024, "03")])
            self.assertTrue(frame.dormidas.eq(0).all())
            data_urls = [
                call.args[0] for call in get.call_args_list
                if call.args[0].startswith(ine_api.DATA_URL + "?")
            ]
            self.assertEqual(data_urls, [
                f"{ine_api.DATA_URL}?op=2&varcd=0009808&lang=PT&Dim1=S3A{period}"
                for period in ("202312", "202401", "202403")
            ])


if __name__ == "__main__":
    unittest.main()
