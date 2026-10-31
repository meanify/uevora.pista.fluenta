"""Tests of the Pulso do Alentejo v2 payload, on the synthetic fixture frames."""

import json
import unittest

import pandas as pd

from backend.dashboards import pulso
from fixtures import frames


class PulsoTests(unittest.TestCase):
    def setUp(self):
        self.frames = frames()
        self.nuts2024 = pulso.pulso(self.frames, 2024, "2024")

    def test_kpis_compare_with_portugal(self):
        k = self.nuts2024["kpis"]
        # Portugal = the three Alentejo municipalities plus 10x Évora.
        self.assertAlmostEqual(k["dormidas_pt_var"], (15120 / 11700 - 1) * 100)
        self.assertAlmostEqual(k["quota_nacional"], 1420 / 15120 * 100)
        self.assertAlmostEqual(k["quota_nacional_dif"], 1420 / 15120 * 100 - 1100 / 11700 * 100)
        self.assertAlmostEqual(k["estada_pt"], 15120 / (600 + 50 + 300 + 6000))
        self.assertAlmostEqual(k["mercado_interno"], 60.0)
        self.assertAlmostEqual(k["mercado_interno_pt"], 30.0)

    def test_portugal_revpar_uses_the_alentejo_revpar_year(self):
        k = self.nuts2024["kpis"]
        self.assertEqual(k["revpar"]["ano"], 2023)
        expected = (50 * 1000 + 20 * 100 + 40 * 400 + 50 * 10000) / (1000 + 100 + 400 + 10000)
        self.assertAlmostEqual(k["revpar_pt"], expected)

    def test_tourism_territories_skip_unpublished_members(self):
        by_name = {r["territorio"]: r for r in self.nuts2024["territorios"]}
        unesco = by_name["Património UNESCO"]
        self.assertAlmostEqual(unesco["variacao"], 30.0)
        self.assertEqual(unesco["omitidos"], ["Elvas"])
        self.assertIsNone(by_name["Alqueva"]["variacao"])

    def test_tourism_territories_do_not_depend_on_the_territory(self):
        nuts2013 = pulso.pulso(self.frames, 2024, "2013")
        self.assertEqual(nuts2013["territorios"], self.nuts2024["territorios"])

    def test_rooms_mix_keeps_confidential_types_unassigned(self):
        mix = self.nuts2024["mix"]
        self.assertEqual(mix["ano"], 2024)
        self.assertEqual(mix["tipos"][1], "Alojamento local")
        self.assertIsNone(mix["alentejo"][0])
        self.assertAlmostEqual(mix["alentejo"][1], 300 / 1200 * 100)
        self.assertAlmostEqual(mix["alentejo"][3], 75.0)
        self.assertAlmostEqual(mix["portugal"][1], 2800 / 12600 * 100)

    def test_rooms_mix_falls_back_to_latest_rooms_year(self):
        f = self.frames
        rows = f["acc"][f["acc"]["ano"] == 2024].copy()
        rows["ano"], rows["quartos"] = 2025, float("nan")
        f["acc"] = pd.concat([f["acc"], rows], ignore_index=True)
        self.assertEqual(pulso.pulso(f, 2025, "2024")["mix"]["ano"], 2024)

    def test_index_uses_first_year_without_2019_and_complete_portugal_years(self):
        index = self.nuts2024["indice"]
        self.assertEqual(index["base"], 2023)
        self.assertEqual(index["anos"], [2023, 2024])
        self.assertAlmostEqual(index["alentejo"][1], 1420 / 1100 * 100)
        self.assertEqual(index["portugal"], [100.0, 100.0])
        self.assertEqual(index["centro"], [None, None])

    def test_heatmap_and_portugal_seasonality(self):
        heat = self.nuts2024["heatmap"]
        self.assertEqual(heat["anos"], [2023, 2024])
        self.assertEqual(heat["linhas"][1]["valores"][0], 1.0)
        portugal = self.nuts2024["sazonalidade_portugal"]
        self.assertEqual(portugal["pico_vale"], 1.0)
        self.assertEqual(portugal["gini"], 0.0)
        self.assertAlmostEqual(portugal["quota_jul_set"], 25.0)

    def test_payload_is_json_serialisable(self):
        json.dumps(self.nuts2024, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
