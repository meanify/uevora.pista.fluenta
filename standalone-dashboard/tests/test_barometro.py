import json
import unittest

import pandas as pd

from backend import queries
from backend.dashboards import barometro
from fixtures import frames


def with_monthly(data, change):
    """Apply change(monthly_seg) and rebuild the derived frames."""
    data["monthly_seg"] = change(data["monthly_seg"].copy())
    return queries.add_derived_frames(data)


class BarometroTests(unittest.TestCase):
    def setUp(self):
        self.frames = frames()

    def test_default_route_uses_latest_month_and_total_segment(self):
        result = barometro.route(self.frames, {})
        self.assertEqual((result["ano"], result["mes"], result["segmento"]), (2024, 12, "Total"))
        json.dumps(result, allow_nan=False)

    def test_month_kpis(self):
        k = barometro.barometro(self.frames, "Évora", "Total", 2024, 12)["kpis"]
        self.assertEqual(k["dormidas"], 12)
        self.assertAlmostEqual(k["dormidas_var"], 0)
        self.assertAlmostEqual(k["alentejo_var"], 0)
        self.assertAlmostEqual(k["estada"], 2)  # 12 nights / 6 guests, recomputed
        self.assertAlmostEqual(k["peso"], 12 / 10 * 100)
        self.assertEqual(k["mes_fraco"]["mes"], 1)
        self.assertAlmostEqual(k["mes_fraco"]["quota"], 1 / 78 * 100)

    def test_profile_and_gaps_against_the_regional_profile(self):
        result = barometro.barometro(self.frames, "Évora", "Hotelaria", 2024, 6)
        own, region, country = (s["valores"] for s in result["perfil"]["series"])
        self.assertEqual(result["perfil"]["ano"], 2024)
        self.assertAlmostEqual(own[11], 12 / 78 * 100)
        self.assertAlmostEqual(region[0], 100 / 12)
        self.assertAlmostEqual(country[0], 100 / 12)
        # Months 1..6 are below 1/12 of the year; the largest gap comes first.
        self.assertEqual(result["margem_total"], 6)
        self.assertEqual([g["mes"] for g in result["margem"]], [1, 2, 3, 4, 5])
        self.assertAlmostEqual(result["margem"][0]["dif_pp"], 100 / 78 - 100 / 12)
        # Hotelaria share of Alentejo: 0.6 x 6 nights / 7 regional nights.
        self.assertAlmostEqual(result["kpis"]["peso"], 3.6 / 7 * 100)

    def test_segment_without_regional_rows_has_no_share_or_gaps(self):
        result = barometro.barometro(self.frames, "Évora", "Alojamento local", 2024, 12)
        self.assertIsNone(result["kpis"]["peso"])
        self.assertIsNone(result["perfil"]["series"][1]["valores"])
        self.assertEqual(result["margem"], [])
        empty = barometro.barometro(self.frames, "Évora", "TER e habitação", 2024, 12)
        self.assertIsNone(empty["kpis"]["dormidas"])
        self.assertIsNone(empty["perfil"]["series"][0]["valores"])

    def test_confidential_month_is_none_and_profile_falls_back_to_a_complete_year(self):
        def hide_march(seg):
            where = (seg["municipio"] == "Évora") & (seg["ano"] == 2024) & (seg["mes"] == "03")
            seg.loc[where, ["dormidas", "hospedes"]] = None
            return seg
        data = with_monthly(self.frames, hide_march)
        result = barometro.barometro(data, "Évora", "Total", 2024, 3)
        self.assertIsNone(result["kpis"]["dormidas"])
        self.assertIsNone(result["kpis"]["estada"])
        self.assertEqual(result["perfil"]["ano"], 2023)
        self.assertIsNone(result["homologa"]["valores"][2])
        self.assertEqual(result["homologa"]["meses_comparados"], 11)
        self.assertIsNone(result["calendario"][1]["valores"][2])

    def test_partial_year_compares_only_published_months(self):
        def add_2025(seg):
            rows = seg[(seg["ano"] == 2024) & seg["mes"].isin(["01", "02"])].copy()
            rows["ano"] = 2025
            rows[["dormidas", "hospedes"]] *= 2
            return pd.concat([seg, rows], ignore_index=True)
        data = with_monthly(self.frames, add_2025)
        result = barometro.route(data, {})
        self.assertEqual((result["ano"], result["mes"]), (2025, 2))
        self.assertEqual(result["perfil"]["ano"], 2024)
        self.assertEqual(result["homologa"]["meses_comparados"], 2)
        self.assertAlmostEqual(result["homologa"]["valores"][0], 100)
        self.assertIsNone(result["homologa"]["valores"][2])
        self.assertAlmostEqual(result["kpis"]["dormidas_var"], 100)
        self.assertIsNone(result["kpis"]["alentejo_var"])  # no regional 2025 in the fixture
        self.assertEqual([r["nome"] for r in result["calendario"]], ["2023", "2024", "2025"])

    def test_invalid_parameters_raise_bad_request(self):
        for params in ({"mes": ["2019-01"]}, {"mes": ["abc"]}, {"municipio": ["Lisboa"]},
                       {"seg": ["Hostel"]}, {"mes": ["2024-13"]}):
            with self.assertRaises(queries.BadRequest, msg=params):
                barometro.route(self.frames, params)


if __name__ == "__main__":
    unittest.main()
