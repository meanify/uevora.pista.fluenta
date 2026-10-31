import json
import unittest

from backend import queries, server
from backend.dashboards import noites_quartos
from fixtures import frames


def run(data=None, year=2024, segment="Total", territory="2024"):
    return noites_quartos.noites_quartos(data or frames(), year, segment, territory)


class ProcuraTests(unittest.TestCase):
    def test_kpis_use_total_rows_and_recompute_stay(self):
        kpis = run()["procura"]["kpis"]
        # NUTS 2024: Évora + Mora (Santarém is in Lezíria do Tejo).
        self.assertEqual(kpis["dormidas"]["valor"], 1300 + 120)
        self.assertAlmostEqual(kpis["dormidas"]["var"], (1420 / 1100 - 1) * 100)
        self.assertAlmostEqual(kpis["estada"]["valor"], 1420 / 650)
        self.assertAlmostEqual(kpis["estada"]["pt"], (1300 * 11 + 120 + 700) / (600 * 11 + 50 + 300))

    def test_monthly_series_and_peak_follow_the_territory(self):
        municipal = run()["procura"]
        self.assertTrue(municipal["mensal"]["soma_municipal"])
        self.assertEqual(municipal["kpis"]["pico"]["mes"], 12)
        self.assertAlmostEqual(municipal["kpis"]["pico"]["quota"], 12 / 78 * 100)
        regional = run(territory="2013")["procura"]
        self.assertFalse(regional["mensal"]["soma_municipal"])
        self.assertEqual(regional["mensal"]["dormidas"], [10.0] * 12)

    def test_international_share_from_markets(self):
        kpis = run(territory="2013")["procura"]["kpis"]
        self.assertAlmostEqual(kpis["quota_internacional"]["valor"], 40)

    def test_confidential_municipalities_are_counted_not_zero(self):
        nuts3 = run(segment="Alojamento local")["procura"]["nuts3"]
        self.assertEqual(nuts3, [{"nuts_iii": "Alentejo Central", "valor": 200.0, "conf": 1}])


class OfertaEquilibrioTests(unittest.TestCase):
    def test_nights_per_room_and_gap(self):
        balance = run()["equilibrio"]
        self.assertEqual(balance["ano"], 2024)
        self.assertEqual(balance["base"], 2023)
        self.assertAlmostEqual(balance["kpis"]["noites_quarto"]["valor"], 1420 / 1200)
        gap = balance["kpis"]["gap"]
        self.assertAlmostEqual(gap["valor"], (1420 / 1100 - 1) * 100 - (1200 / 1100 - 1) * 100)
        self.assertEqual(balance["indice"]["base"], 2023)
        self.assertEqual(balance["indice"]["dormidas"][0], 100)

    def test_missing_rooms_fall_back_to_the_latest_year(self):
        data = frames()
        acc = data["acc"]
        acc.loc[acc["ano"] == 2024, "quartos"] = None
        result = run(data)
        self.assertEqual(result["oferta"]["kpis"]["quartos"]["ano"], 2023)
        self.assertEqual(result["equilibrio"]["ano"], 2023)
        self.assertIsNone(result["equilibrio"]["base"])
        self.assertIsNone(result["equilibrio"]["kpis"]["gap"]["valor"])
        self.assertEqual(result["equilibrio"]["dispersao"], [])

    def test_rooms_per_km2_and_ter_share(self):
        kpis = run()["oferta"]["kpis"]
        self.assertAlmostEqual(kpis["quartos_km2"]["valor"], 1200 / 15)
        self.assertIsNone(kpis["peso_ter"]["valor"])

    def test_invalid_parameters_and_route_payload(self):
        with self.assertRaises(queries.BadRequest):
            run(segment="Hostel")
        with self.assertRaises(queries.BadRequest):
            run(year=2010)

        class Data:
            loaded_at = 0.0

            def frames(self, refresh=False):
                return frames()

        status, payload = server.handle_api(Data(), "noites-quartos", {})
        self.assertEqual(status, 200, payload)
        self.assertEqual(payload["ano"], 2024)
        json.dumps(payload, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
