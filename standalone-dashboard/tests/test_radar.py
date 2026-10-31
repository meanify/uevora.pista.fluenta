import unittest

from backend.dashboards import radar
from fixtures import frames


class RadarV2Tests(unittest.TestCase):
    def setUp(self):
        self.result = radar.radar(frames(), 2024, "anterior", "2013")

    def test_domestic_share_has_the_national_value_beside_it(self):
        kpis = self.result["kpis"]
        # Alentejo: 2 x 60 of 2 x 100 guests; Portugal: 300 of 1000.
        self.assertAlmostEqual(kpis["quota_interna"], 60)
        self.assertAlmostEqual(kpis["quota_interna_portugal"], 30)

    def test_specialisation_is_location_quotient_minus_one(self):
        rows = {r["mercado"]: r for r in self.result["especializacao"]}
        # Espanha: 60 of 80 foreign guests in the Alentejo, 100 of 700 in Portugal.
        self.assertAlmostEqual(rows["Espanha"]["indice"], (0.75 / (100 / 700) - 1) * 100)
        self.assertAlmostEqual(rows["França"]["indice"], (0.25 / (200 / 700) - 1) * 100)
        self.assertAlmostEqual(rows["Espanha"]["quota_portugal"], 100 / 700 * 100)
        self.assertEqual([r["mercado"] for r in self.result["especializacao"]], ["Espanha", "França"])

    def test_specialisation_skips_markets_without_national_value(self):
        data = frames()
        pt = data["pt_markets"]
        data["pt_markets"] = pt[pt["local_residencia"] != "França"]
        result = radar.radar(data, 2024, "anterior", "2013")
        self.assertEqual([r["mercado"] for r in result["especializacao"]], ["Espanha"])


if __name__ == "__main__":
    unittest.main()
