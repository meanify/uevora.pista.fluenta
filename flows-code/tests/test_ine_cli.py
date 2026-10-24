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
from pistadigital.utils import ine_0009929_flow as ine
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
        invalid = subprocess.run(
            [sys.executable, str(entrypoint), "-i", "9929", "-y", "2024"],
            capture_output=True, text=True,
        )
        self.assertEqual(invalid.returncode, 2)
        self.assertIn("Choose at least one output", invalid.stderr)


if __name__ == "__main__":
    unittest.main()
