import json
import math
import unittest

import pandas as pd

from backend import measures, queries, server
from backend.dashboards import numeros, oportunidades, pulso, radar, raio_x
from fixtures import frames


class MeasureTests(unittest.TestCase):
    def test_gini_is_zero_for_equal_months_and_positive_otherwise(self):
        self.assertAlmostEqual(measures.gini([5] * 12), 0.0)
        self.assertGreater(measures.gini([1] * 11 + [20]), 0.5)
        self.assertIsNone(measures.gini([1, None, 3]))

    def test_seasonality_requires_twelve_published_months(self):
        result = measures.seasonality([1, 1, 1, 1, 1, 2, 2, 2, 2, 1, 1, 1])
        self.assertAlmostEqual(result["pico_vale"], 2.0)
        self.assertAlmostEqual(result["quota_jun_set"], 8 / 16 * 100)
        self.assertIsNone(measures.seasonality([1] * 11 + [float("nan")]))

    def test_hhi_of_a_single_market_is_ten_thousand(self):
        self.assertAlmostEqual(measures.hhi([7.0]), 10000)
        self.assertAlmostEqual(measures.hhi([1, 1, None]), 5000)

    def test_weighted_mean_skips_missing_values_and_weights(self):
        self.assertAlmostEqual(measures.weighted_mean([(10, 1), (20, 3), (None, 5), (99, None)]), 17.5)
        self.assertIsNone(measures.weighted_mean([(None, 1)]))

    def test_latest_year_and_quadrants(self):
        self.assertEqual(measures.latest_year([2019, 2021, 2023], 2022), 2021)
        self.assertIsNone(measures.latest_year([2023], 2020))
        self.assertEqual(measures.quadrant(5, 3, 0, 2), "Estrelas")
        self.assertEqual(measures.quadrant(5, 1, 0, 2), "De passagem")
        self.assertEqual(measures.quadrant(-5, 3, 0, 2), "Fiéis")
        self.assertEqual(measures.quadrant(-5, 1, 0, 2), "A rever")
        self.assertIsNone(measures.quadrant(None, 1, 0, 2))


class QueryTests(unittest.TestCase):
    def setUp(self):
        self.frames = frames()

    def test_nuts_2024_excludes_leziria_and_nuts_2013_includes_it(self):
        nuts2024 = pulso.pulso(self.frames, 2024, "2024")["kpis"]
        nuts2013 = pulso.pulso(self.frames, 2024, "2013")["kpis"]
        self.assertEqual(nuts2024["dormidas"], 1420)
        self.assertEqual(nuts2013["dormidas"], 2120)
        self.assertAlmostEqual(nuts2024["dormidas_var"], (1420 / 1100 - 1) * 100)
        self.assertAlmostEqual(nuts2024["estada"], 1420 / 650)

    def test_revpar_falls_back_to_latest_published_year_weighted_by_rooms(self):
        revpar = pulso.pulso(self.frames, 2024, "2024")["kpis"]["revpar"]
        self.assertEqual(revpar["ano"], 2023)
        self.assertAlmostEqual(revpar["valor"], (50 * 1000 + 20 * 100) / 1100)
        self.assertEqual(revpar["municipios"], 2)

    def test_monthly_series_uses_municipal_sum_for_nuts_2024(self):
        nuts2024 = pulso.pulso(self.frames, 2024, "2024")["sazonalidade"]
        nuts2013 = pulso.pulso(self.frames, 2024, "2013")["sazonalidade"]
        self.assertTrue(nuts2024["soma_municipal"])
        self.assertEqual(nuts2024["series"][0]["valores"][0], 1.0)
        self.assertFalse(nuts2013["soma_municipal"])
        self.assertEqual(nuts2013["series"][0]["valores"][0], 10.0)

    def test_raio_x_compares_with_peers_of_the_same_nuts_iii(self):
        result = raio_x.raio_x(self.frames, "Évora", 2024)
        self.assertEqual([r["municipio"] for r in result["pressao"]], ["Évora", "Mora"])
        self.assertAlmostEqual(result["kpis"]["dormidas_km2"], 130)
        self.assertAlmostEqual(result["kpis"]["dormidas_km2_pares"], 24)
        self.assertAlmostEqual(result["kpis"]["peso_al"], 250 / 1100 * 100)
        self.assertEqual(result["kpis"]["pico"]["mes"], 12)

    def test_raio_x_reports_portugal_apart_from_foreign_markets(self):
        result = raio_x.raio_x(self.frames, "Évora", 2024)
        self.assertNotIn("Portugal", [r["mercado"] for r in result["mercados"]])
        self.assertAlmostEqual(result["portugal_dif_pp"], 0.0)

    def test_radar_ignores_residence_aggregates(self):
        result = radar.radar(self.frames, 2024, "anterior", "2013")
        self.assertEqual([m["mercado"] for m in result["mercados"]], ["Espanha", "França"])
        self.assertAlmostEqual(result["kpis"]["quota_internacional"], 40)
        self.assertAlmostEqual(result["kpis"]["hhi"], 75 ** 2 + 25 ** 2)

    def test_oportunidades_revpar_bars_share_one_year(self):
        result = oportunidades.oportunidades(self.frames, 2023, 2024, "Total", "2024")
        self.assertEqual({r["ano"] for r in result["revpar"]}, {2023})
        gaps = {g["municipio"]: g["gap"] for g in result["gap"]}
        self.assertAlmostEqual(gaps["Évora"], 30 - 10)
        self.assertAlmostEqual(gaps["Mora"], 20 - 0)

    def test_table_keeps_confidential_values_as_none(self):
        result = numeros.alentejo_em_numeros(self.frames, 2024, "2024")
        self.assertFalse(result["revpar_publicado"])
        self.assertTrue(all(r["revpar"] is None for r in result["tabela"]))

    def test_invalid_parameters_raise_bad_request(self):
        with self.assertRaises(queries.BadRequest):
            pulso.pulso(self.frames, 1999, "2024")
        with self.assertRaises(queries.BadRequest):
            pulso.pulso(self.frames, 2024, "1990")
        with self.assertRaises(queries.BadRequest):
            raio_x.raio_x(self.frames, "Lisboa", 2024)
        with self.assertRaises(queries.BadRequest):
            oportunidades.oportunidades(self.frames, 2024, 2023, "Total", "2024")


class NationalTests(unittest.TestCase):
    def test_national_revpar_uses_latest_published_rooms_year_per_municipality(self):
        keys = {"nuts_ii": "Norte", "tipo_alojamento": "Total", "subtipo_alojamento": "Total",
                "classificacao": "Total"}
        revpar = pd.DataFrame([{**keys, "municipio": "A", "ano": 2025, "revpar": 50.0},
                               {**keys, "municipio": "B", "ano": 2025, "revpar": 100.0}])
        rooms = pd.DataFrame([{**keys, "municipio": "A", "ano": 2024, "quartos": 300.0},
                              {**keys, "municipio": "B", "ano": 2025, "quartos": 100.0},
                              {**keys, "municipio": "B", "ano": 2023, "quartos": 999.0}])
        result = queries.national_revpar(revpar, rooms).iloc[0]
        self.assertAlmostEqual(result["revpar"], (50 * 300 + 100 * 100) / 400)
        self.assertEqual(result["municipios"], 2)
        self.assertEqual(result["ano_quartos"], 2025)

    def test_portugal_sums_and_meta_months(self):
        data = frames()
        national = queries.portugal(data)
        self.assertEqual(national.loc[2024, "dormidas"], 1300 * 11 + 120 + 700)
        self.assertAlmostEqual(national.loc[2023, "revpar"],
                               (50 * 1000 + 20 * 100 + 40 * 400 + 50 * 10000) / 11500)
        meta = queries.meta(data)
        self.assertEqual(meta["ultimo_mes"], {"ano": 2024, "mes": 12})
        self.assertIn("Alqueva", meta["territorios_turisticos"])


class FakeData:
    loaded_at = 0.0

    def __init__(self, data):
        self._data = data

    def frames(self, refresh=False):
        return self._data


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.data = FakeData(frames())

    def test_routes_return_json_serialisable_payloads(self):
        for name in server.ROUTES:
            status, payload = server.handle_api(self.data, name, {})
            self.assertEqual(status, 200, (name, payload))
            json.dumps(payload, allow_nan=False)

    def test_unknown_route_and_bad_parameter(self):
        self.assertEqual(server.handle_api(self.data, "nada", {})[0], 404)
        status, payload = server.handle_api(self.data, "pulso", {"ano": ["abc"]})
        self.assertEqual(status, 400)
        self.assertIn("ano", payload["erro"])

    def test_only_pages_and_assets_are_served(self):
        for path in ("/", "/index.html", "/assets/common.js", "/assets/common.css",
                     "/01_pulso_alentejo.html"):
            self.assertTrue(server.is_web_file(path), path)
        for path in ("/../backend/server.py", "/%2e%2e/README.md", "/../dashboards.py",
                     "/../.env", "/.env", "/assets", "/nada.html", "/assets/../../README.md"):
            self.assertFalse(server.is_web_file(path), path)

    def test_payload_reports_whether_running_code_is_current(self):
        status, payload = server.handle_api(self.data, "meta", {})
        self.assertEqual(payload["versao"], server.RUNNING_CODE)
        self.assertFalse(payload["servidor_desatualizado"])
        original = server.RUNNING_CODE
        try:
            server.RUNNING_CODE = "old"
            self.assertTrue(server.handle_api(self.data, "meta", {})[1]["servidor_desatualizado"])
        finally:
            server.RUNNING_CODE = original

    def test_json_safe_replaces_non_finite_numbers(self):
        self.assertEqual(server._json_safe({"a": [math.nan, 1.0, math.inf]}), {"a": [None, 1.0, None]})


if __name__ == "__main__":
    unittest.main()
