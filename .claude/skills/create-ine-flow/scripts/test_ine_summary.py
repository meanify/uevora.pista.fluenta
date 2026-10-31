"""Offline checks for the skill's bounded inspection helper."""

from contextlib import redirect_stdout
import argparse
import io
import unittest

import ine_summary as summary


class SummaryTests(unittest.TestCase):
    def summarize(self, payload, year=2025, month=None, period_key=None):
        output = io.StringIO()
        with redirect_stdout(output):
            summary.summarize_data(payload, year, month, period_key)
        return output.getvalue()

    def test_codes_preserve_identity_and_require_ascii_digits(self):
        for value, expected in (("9930", "0009930"), ("9874", "0009874"),
                                ("0009930", "0009930"), ("000930", "0000930")):
            self.assertEqual(summary.indicator_code(value), expected)
        for value in ("", "12345678", "../9930", "９９３０"):
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                summary.indicator_code(value)

    def test_metadata_uses_real_api_name_and_update_fields(self):
        payload = {
            "IndicadorNome": "Guests", "DataUltimaAtualizacao": "2026-07-09",
            "Dimensoes": {"Descricao_Dim": [], "Categoria_Dim": []},
        }
        output = io.StringIO()
        with redirect_stdout(output):
            summary.summarize_meta(payload, None, None)
        self.assertIn("IndicadorNome: Guests", output.getvalue())
        self.assertIn("DataUltimaAtualizacao: 2026-07-09", output.getvalue())

    def test_saved_metadata_aliases_remain_supported(self):
        payload = {
            "IndicadorDsg": "Saved indicator",
            "DataUltimoAtualizacao": "2025-07-15",
            "Dimensoes": {"Descricao_Dim": [], "Categoria_Dim": []},
        }
        output = io.StringIO()
        with redirect_stdout(output):
            summary.summarize_meta(payload, None, None)
        self.assertIn("IndicadorNome: Saved indicator", output.getvalue())
        self.assertIn("DataUltimaAtualizacao: 2025-07-15", output.getvalue())

    def test_annual_data_is_bounded_to_requested_period(self):
        row = {"geocod": "PT", "valor": "0"}
        output = self.summarize([{"Dados": {"2025": [row] * 6}}])
        self.assertIn("records: 6", output)
        self.assertEqual(output.count("sample:"), 3)
        self.assertIn("period validation: passed", output)
        self.assertIn("duplicate ['geocod'] keys: 5", output)
        for periods in ({"2024": []}, {"2025": [], "2024": []}, {"12025": []}):
            with self.subTest(periods=periods), self.assertRaises(ValueError):
                self.summarize({"Dados": periods})

    def test_monthly_period_key_is_exact_not_just_same_year(self):
        output = self.summarize(
            {"Dados": {"March 2025": [{"valor": "1", "mescod": "03"}]}},
            month=3, period_key="March 2025",
        )
        self.assertIn("period validation: passed", output)
        with self.assertRaises(ValueError):
            self.summarize(
                {"Dados": {"April 2025": []}}, month=3, period_key="March 2025",
            )

    def test_list_records_require_period_and_reject_foreign_rows(self):
        self.summarize({"Dados": [{"anocod": "2025", "valor": "1"}]})
        for row in ({}, {"anocod": "2024"}, {"anocod": True}):
            with self.subTest(row=row), self.assertRaises(ValueError):
                self.summarize({"Dados": [row]})
        with self.assertRaises(ValueError):
            self.summarize(
                {"Dados": [{"anocod": "2025", "mescod": "04"}]},
                month=3, period_key="March 2025",
            )

    def test_malformed_payloads_fail(self):
        for payload in ([], [None], [{}, {}], "bad"):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                summary.first(payload)
        for records in (None, {}, [None]):
            with self.subTest(records=records), self.assertRaises(ValueError):
                self.summarize({"Dados": {"2025": records}})


if __name__ == "__main__":
    unittest.main()
