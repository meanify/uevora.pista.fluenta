import unittest

import pandas as pd

from backend.dashboards import oportunidades
from fixtures import frames


def with_top_hotels(data):
    """Add Hotéis 4★ rows; rooms are confidential in the RevPAR year 2024."""
    rows = [
        # (municipio, ano, quartos, revpar)
        ("Évora", 2023, 100.0, 80.0),
        ("Évora", 2024, None, 90.0),
        ("Mora", 2023, 50.0, None),
        ("Mora", 2024, None, 70.0),
    ]
    extra = pd.DataFrame([{
        "municipio": name, "nuts_iii": "Alentejo Central", "ano": year,
        "tipo_alojamento": "Hotelaria", "subtipo_alojamento": "Hotéis", "classificacao": "4 estrelas",
        "estabelecimentos": None, "quartos": rooms, "hospedes": None, "dormidas": None, "revpar": revpar,
    } for name, year, rooms, revpar in rows])
    data["acc"] = pd.concat([data["acc"], extra], ignore_index=True)
    return data


class OportunidadesTests(unittest.TestCase):
    def test_top_hotel_revpar_uses_latest_published_rooms_per_cell(self):
        result = oportunidades.oportunidades(with_top_hotels(frames()), 2023, 2024, "Total", "2024")
        revpar = result["kpis"]["revpar_4_5"]
        self.assertAlmostEqual(revpar["valor"], (90 * 100 + 70 * 50) / 150)
        self.assertEqual(revpar["ano"], 2024)
        self.assertEqual(revpar["ano_quartos"], 2023)
        self.assertEqual(revpar["municipios"], 2)

    def test_top_hotel_revpar_is_none_without_published_values(self):
        result = oportunidades.oportunidades(frames(), 2023, 2024, "Total", "2024")
        self.assertIsNone(result["kpis"]["revpar_4_5"])

    def test_supply_demand_index_starts_at_first_year(self):
        index = oportunidades.oportunidades(frames(), 2023, 2024, "Total", "2024")["indice"]
        self.assertEqual(index["base"], 2023)
        self.assertEqual(index["anos"], [2023, 2024])
        self.assertAlmostEqual(index["dormidas"][1], 1420 / 1100 * 100)
        self.assertAlmostEqual(index["quartos"][1], 1200 / 1100 * 100)


if __name__ == "__main__":
    unittest.main()
