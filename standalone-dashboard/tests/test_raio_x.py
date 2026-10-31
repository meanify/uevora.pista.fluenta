import json
import unittest

import pandas as pd

from backend import queries
from backend.dashboards import raio_x
from fixtures import frames


def add_mora_months(data, hidden_month=None):
    """Give Mora (Évora's peer) monthly nights, optionally one confidential month."""
    seg = data["monthly_seg"]
    mora = seg[seg["municipio"] == "Évora"].copy()
    mora["municipio"] = "Mora"
    mora[["dormidas", "hospedes"]] *= 10
    if hidden_month:
        mora.loc[(mora["ano"] == 2024) & (mora["mes"] == hidden_month), ["dormidas", "hospedes"]] = None
    data["monthly_seg"] = pd.concat([seg, mora], ignore_index=True)
    return queries.add_derived_frames(data)


class RaioXTests(unittest.TestCase):
    def test_calendar_rows_and_regional_total(self):
        result = raio_x.raio_x(add_mora_months(frames()), "Évora", 2024)
        own, peers, region = (r["valores"] for r in result["calendario"])
        self.assertEqual(own[11], 12)
        self.assertEqual(peers[11], 120)
        # Alentejo is the published regional row (0009808), not a municipal sum.
        self.assertEqual(region, [10.0] * 12)
        self.assertEqual(result["calendario_pares"], {"completos": 1, "total": 1})
        self.assertEqual(result["mensal_desde"], 2023)
        json.dumps(result, allow_nan=False)

    def test_peers_with_a_confidential_month_are_left_out_of_the_calendar(self):
        result = raio_x.raio_x(add_mora_months(frames(), hidden_month="05"), "Évora", 2024)
        self.assertEqual(result["calendario"][1]["valores"], [None] * 12)
        self.assertEqual(result["calendario_pares"], {"completos": 0, "total": 1})

    def test_year_before_the_monthly_series_has_no_municipal_months(self):
        data = frames()
        result = raio_x.raio_x(data, "Évora", 2023)
        self.assertLessEqual(result["mensal_desde"], 2023)
        self.assertEqual(result["kpis"]["pico"]["mes"], 12)
        self.assertEqual(result["evolucao"]["base"], 2023)


if __name__ == "__main__":
    unittest.main()
