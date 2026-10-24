import unittest
from unittest.mock import Mock, patch

import requests

from pistadigital.utils import ine_api


def metadata_with_periods(years):
    return [{
        "Dimensoes": {
            "Categoria_Dim": [
                {
                    f"Dim_Num1_S7A{year}": [{
                        "dim_num": "1",
                        "categ_cod": f"S7A{year}",
                        "categ_dsg": str(year),
                    }]
                }
                for year in years
            ]
        }
    }]


class IneApiTests(unittest.TestCase):
    def test_available_years_use_explicit_period_categories(self):
        metadata = metadata_with_periods([2025, 2018, 2021])
        metadata[0]["Dimensoes"]["Categoria_Dim"].append({
            "Dim_Num2": [{
                "dim_num": "2",
                "categ_cod": "2024",
                "categ_dsg": "2024",
            }]
        })
        self.assertEqual(ine_api.available_annual_years(metadata), [2018, 2021, 2025])

    def test_available_years_fall_back_to_period_code(self):
        metadata = metadata_with_periods([2024])
        metadata[0]["Dimensoes"]["Categoria_Dim"][0][
            "Dim_Num1_S7A2024"
        ][0]["categ_dsg"] = "Annual"
        self.assertEqual(ine_api.available_annual_years(metadata), [2024])

    def test_missing_annual_periods_are_an_error(self):
        with self.assertRaisesRegex(RuntimeError, "No annual periods"):
            ine_api.available_annual_years([{"Dimensoes": {"Categoria_Dim": []}}])

    def test_fetch_metadata_uses_indicator_parameters(self):
        response = Mock()
        response.json.return_value = metadata_with_periods([2024])
        with patch.object(ine_api.requests, "get", return_value=response) as get:
            metadata = ine_api.fetch_indicator_metadata("0009929")
        self.assertEqual(metadata, response.json.return_value)
        get.assert_called_once_with(
            f"{ine_api.METADATA_URL}?varcd=0009929&lang=PT",
            timeout=120,
        )
        response.raise_for_status.assert_called_once_with()

    def test_fetch_annual_data_uses_indicator_and_period(self):
        response = Mock()
        response.json.return_value = [{"Dados": {"2024": []}}]
        with patch.object(ine_api.requests, "get", return_value=response) as get:
            result = ine_api.fetch_annual_indicator_data("0009873", 2024)
        self.assertEqual(result, response.json.return_value)
        get.assert_called_once_with(
            f"{ine_api.DATA_URL}?op=2&varcd=0009873&lang=PT&Dim1=S7A2024",
            headers={"Content-Type": "application/json"}, timeout=120,
        )
        response.raise_for_status.assert_called_once_with()

    def test_annual_data_failures_are_reported(self):
        for stage, error in (
            ("get", requests.Timeout("timeout")),
            ("status", requests.HTTPError("HTTP error")),
            ("json", ValueError("invalid JSON")),
        ):
            response = Mock()
            if stage == "status":
                response.raise_for_status.side_effect = error
            if stage == "json":
                response.json.side_effect = error
            with self.subTest(stage=stage), patch.object(
                ine_api.requests, "get", return_value=response,
                side_effect=error if stage == "get" else None,
            ), self.assertRaisesRegex(RuntimeError, "0009873, 2024"):
                ine_api.fetch_annual_indicator_data("0009873", 2024)


if __name__ == "__main__":
    unittest.main()
