import unittest

import pandas as pd

from backend import queries
from backend.dashboards import numeros
from fixtures import frames


def with_years_from_2019():
    """Fixture frames plus 2019-2022 for the Alentejo totals and Portugal's months."""
    data = frames()
    acc, regions = data["acc"], data["regions_tipo"]
    # Alentejo NUTS 2024 total nights (Évora + Mora): 2019 = 1000, 2020 = 500,
    # 2021 = 800, 2022 = 1100; 2023 = 1100 and 2024 = 1420 come from the fixture.
    extra_acc, extra_regions = [], []
    for year, scale in ((2019, 1000 / 1100), (2020, 500 / 1100), (2021, 800 / 1100), (2022, 1)):
        rows = acc[(acc["ano"] == 2023) & (acc["tipo_alojamento"] == "Total")].copy()
        rows["ano"] = year
        rows["dormidas"] = rows["dormidas"] * scale
        extra_acc.append(rows)
    # Portugal: 2019 = 480 (like 2023), 2020 = 120, 2021 = 240, 2022 = 456.
    for year, scale in ((2019, 1), (2020, 0.25), (2021, 0.5), (2022, 0.95)):
        rows = regions[regions["ano"] == 2023].copy()
        rows["ano"] = year
        rows[["dormidas", "hospedes"]] = rows[["dormidas", "hospedes"]] * scale
        extra_regions.append(rows)
    data["acc"] = pd.concat([acc, *extra_acc], ignore_index=True)
    data["regions_tipo"] = pd.concat([regions, *extra_regions], ignore_index=True)
    return queries.add_derived_frames(data)


class NumerosV2Tests(unittest.TestCase):
    def test_headlines_come_from_totals_and_monthly_profile(self):
        result = numeros.alentejo_em_numeros(frames(), 2024, "2024")
        h = result["destaques"]
        self.assertEqual(h["dormidas"], 1420)
        self.assertEqual(h["dormidas_portugal"], 480)
        self.assertAlmostEqual(h["uma_em"], 480 / 1420)
        self.assertAlmostEqual(h["quota_residentes"], 60)
        # Évora's monthly nights are 1..12: December is the peak, January the low.
        self.assertEqual(h["pico_vale"], {"pico": 11, "vale": 0, "razao": 12})
        self.assertAlmostEqual(result["densidade"]["alentejo"], 1420 / 15)
        self.assertAlmostEqual(result["densidade"]["portugal"], 480 / 135)

    def test_evolution_index_starts_at_first_annual_year(self):
        evolution = numeros.alentejo_em_numeros(frames(), 2024, "2024")["evolucao"]
        self.assertEqual(evolution["base"], 2023)
        self.assertAlmostEqual(evolution["alentejo"][1], 1420 / 1100 * 100)

    def test_recovery_is_empty_without_2019(self):
        recovery = numeros.alentejo_em_numeros(frames(), 2024, "2024")["recuperacao"]
        self.assertEqual(recovery["anos"], [])
        self.assertIsNone(recovery["recuperou_alentejo"])

    def test_recovery_index_and_first_year_back_at_2019(self):
        recovery = numeros.alentejo_em_numeros(with_years_from_2019(), 2024, "2024")["recuperacao"]
        self.assertEqual(recovery["anos"], [2019, 2020, 2021, 2022, 2023, 2024])
        self.assertAlmostEqual(recovery["alentejo"][1], 50)
        self.assertAlmostEqual(recovery["portugal"][1], 25)
        self.assertEqual(recovery["recuperou_alentejo"], 2022)
        self.assertEqual(recovery["recuperou_portugal"], 2023)

    def test_residents_share_is_none_before_market_series(self):
        data = frames()
        data["markets"] = data["markets"][data["markets"]["ano"] != 2024]
        self.assertIsNone(numeros.alentejo_em_numeros(data, 2024, "2024")["destaques"]["quota_residentes"])


if __name__ == "__main__":
    unittest.main()
