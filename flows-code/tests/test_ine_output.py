import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd
from sqlalchemy import create_engine, text

from pistadigital.utils import ine_output
from pistadigital.utils import database
from pistadigital.utils.ine_output import replace_period_data


ANNUAL_DDL = """
CREATE TABLE IF NOT EXISTS annual_data (
    ano INTEGER NOT NULL, place TEXT NOT NULL, value REAL,
    PRIMARY KEY (ano, place)
)
"""
MONTHLY_DDL = """
CREATE TABLE IF NOT EXISTS monthly_data (
    ano INTEGER NOT NULL, mes INTEGER NOT NULL, place TEXT NOT NULL, value REAL,
    PRIMARY KEY (ano, mes, place)
)
"""


class CsvOutputTests(unittest.TestCase):
    def test_csv_format_overwrite_and_logging(self):
        frame = pd.DataFrame(
            {"ano": [2024, 2025], "value": [12.5, None]},
            index=[7, 8],
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "indicator.csv"
            path.write_text("old contents\n", encoding="utf-8")
            with self.assertLogs(ine_output.logger, level="INFO") as logs:
                ine_output.write_csv(frame, path)
            self.assertEqual(
                path.read_text(encoding="utf-8"),
                "ano,value\n2024,12.5\n2025,\n",
            )
            self.assertIn(f"Exported 2 records to {path}.", logs.output[0])

    def test_empty_csv_keeps_header_and_accepts_string_path(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "empty.csv"
            ine_output.write_csv(pd.DataFrame(columns=["ano", "value"]), str(path))
            self.assertEqual(path.read_text(encoding="utf-8"), "ano,value\n")

    def test_write_error_propagates_without_success_log(self):
        with patch.object(pd.DataFrame, "to_csv", side_effect=OSError("not writable")), \
                patch.object(ine_output.logger, "info") as log:
            with self.assertRaisesRegex(OSError, "not writable"):
                ine_output.write_csv(pd.DataFrame(), "indicator.csv")
            log.assert_not_called()


class PeriodReplacementTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")

    def tearDown(self):
        self.engine.dispose()

    def rows(self, table):
        with self.engine.connect() as connection:
            return list(connection.execute(
                text(f"SELECT * FROM {table} ORDER BY ano, place")
            ))

    def annual_write(self, rows, year):
        return replace_period_data(
            pd.DataFrame(rows, columns=["ano", "place", "value"]),
            "annual_data", ANNUAL_DDL, year, engine=self.engine,
        )

    def test_annual_rerun_replaces_year_and_keeps_other_years(self):
        self.annual_write([(2023, "old", 1)], 2023)
        self.annual_write([(2024, "obsolete", 2), (2024, "same", 3)], 2024)
        self.annual_write([(2024, "new", 4)], 2024)
        self.annual_write([(2024, "new", 4)], 2024)
        self.assertEqual(self.rows("annual_data"), [(2023, "old", 1), (2024, "new", 4)])

    def test_monthly_rerun_keeps_other_months_and_years(self):
        def write(year, month, place, value):
            replace_period_data(
                pd.DataFrame([{"ano": year, "mes": month, "place": place, "value": value}]),
                "monthly_data", MONTHLY_DDL, year, month, engine=self.engine,
            )
        write(2023, 3, "previous-year", 1)
        write(2024, 2, "previous-month", 2)
        write(2024, 3, "obsolete", 3)
        write(2024, 3, "replacement", 4)
        write(2024, 3, "replacement", 4)
        self.assertEqual(self.rows("monthly_data"), [
            (2023, 3, "previous-year", 1),
            (2024, 2, "previous-month", 2),
            (2024, 3, "replacement", 4),
        ])

    def test_insert_failure_rolls_back_delete_and_partial_insert(self):
        self.annual_write([(2024, "original", 1)], 2024)
        with self.assertRaisesRegex(RuntimeError, "rolled back"):
            self.annual_write([(2024, "duplicate", 2), (2024, "duplicate", 3)], 2024)
        self.assertEqual(self.rows("annual_data"), [(2024, "original", 1)])

    def test_empty_frame_keeps_existing_records(self):
        self.annual_write([(2024, "original", 1)], 2024)
        self.assertEqual(self.annual_write([], 2024), 0)
        self.assertEqual(self.rows("annual_data"), [(2024, "original", 1)])

    def test_wrong_or_missing_period_fails_before_database_access(self):
        cases = [
            (pd.DataFrame({"ano": [2023]}), 2024, None),
            (pd.DataFrame({"ano": [2024, 2023]}), 2024, None),
            (pd.DataFrame({"ano": pd.Series([pd.NA], dtype="Int64")}), 2024, None),
            (pd.DataFrame({"ano": [2024], "mes": [2]}), 2024, 3),
            (pd.DataFrame({"ano": [2024], "mes": [3]}), 2024, None),
            (pd.DataFrame({"ano": [2024]}), 2024, 3),
            (pd.DataFrame({"value": [1]}), 2024, None),
            (pd.DataFrame({"ano": [2024]}), 2024, 13),
        ]
        with patch.object(ine_output, "get_engine") as get:
            for df, year, month in cases:
                with self.subTest(year=year, month=month), self.assertRaises(ValueError):
                    replace_period_data(df, "annual_data", ANNUAL_DDL, year, month)
            get.assert_not_called()

    def test_owned_engine_disposed_on_failure(self):
        self.annual_write([(2024, "original", 1)], 2024)
        with patch.object(ine_output, "get_engine", return_value=self.engine), \
                patch.object(self.engine, "dispose") as dispose:
            with self.assertRaises(RuntimeError):
                replace_period_data(
                    pd.DataFrame({"ano": [2024, 2024], "place": ["dup", "dup"]}),
                    "annual_data", ANNUAL_DDL, 2024,
                )
            dispose.assert_called_once_with()
        self.assertEqual(self.rows("annual_data"), [(2024, "original", 1)])

    def test_database_settings_checked_only_when_requested(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "Missing database settings"):
                ine_output.get_engine()

    def test_engine_url_preserves_special_characters_in_credentials(self):
        settings = {
            "PISTA_DB_HOSTNAME": "localhost", "PISTA_DB_PORTNUMBER": "5432",
            "PISTA_DB_NAME": "test", "PISTA_DB_USERNAME": "user@example",
            "PISTA_DB_PASSWORD": "test/@:#password",
        }
        with patch.dict(os.environ, settings, clear=True), \
                patch.object(database, "create_engine") as create:
            ine_output.get_engine()
        url = create.call_args.args[0]
        self.assertEqual(url.password, settings["PISTA_DB_PASSWORD"])
        self.assertEqual(url.username, settings["PISTA_DB_USERNAME"])
        self.assertEqual(url.port, 5432)

    def test_monthly_insert_failure_preserves_original_period(self):
        def write(rows):
            replace_period_data(
                pd.DataFrame(rows, columns=["ano", "mes", "place", "value"]),
                "monthly_data", MONTHLY_DDL, 2024, 3, engine=self.engine,
            )
        write([(2024, 3, "original", 1)])
        with self.assertRaisesRegex(RuntimeError, "rolled back"):
            write([(2024, 3, "duplicate", 2), (2024, 3, "duplicate", 3)])
        self.assertEqual(self.rows("monthly_data"), [(2024, 3, "original", 1)])


if __name__ == "__main__":
    unittest.main()
