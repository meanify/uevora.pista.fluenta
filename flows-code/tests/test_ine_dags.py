"""Verify every INE DAG entry point against the single shared factory."""

import ast
import importlib
import inspect
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

import pandas as pd

from pistadigital.cli.ine_flows import INDICATORS
from pistadigital.utils import ine_api


DAG_FOLDER = Path(__file__).resolve().parents[1] / "dags"


class IneDagTests(unittest.TestCase):
    def setUp(self):
        self.dags, self.operators = [], []
        dags = self.dags

        class FakeDAG:
            def __init__(self, dag_id, **options):
                self.dag_id, self.options = dag_id, options
                dags.append(self)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        self.dag_type = FakeDAG
        sdk = types.ModuleType("airflow.sdk")
        sdk.DAG = FakeDAG
        operator = types.ModuleType("airflow.providers.standard.operators.python")
        operator.PythonVirtualenvOperator = lambda **options: self.operators.append(options)
        pendulum = types.ModuleType("pendulum")
        pendulum.datetime = lambda *args: args
        pendulum.duration = lambda **kwargs: kwargs
        pendulum.now = lambda: types.SimpleNamespace(year=2026)
        modules = patch.dict(sys.modules, {
            "airflow.sdk": sdk,
            "airflow.providers.standard.operators.python": operator,
            "pendulum": pendulum,
        })
        modules.start()
        self.addCleanup(modules.stop)
        path = DAG_FOLDER / "dags_ine.py"
        self.factory = types.ModuleType("dags_ine")
        with patch.object(ine_api, "fetch_indicator_metadata") as fetch:
            exec(compile(path.read_text(), str(path), "exec"), self.factory.__dict__)
        fetch.assert_not_called()
        self.assertEqual(self.dags, [])
        helper = patch.dict(sys.modules, {"dags_ine": self.factory})
        helper.start()
        self.addCleanup(helper.stop)

    def test_all_entry_points_ids_windows_and_operator_configuration(self):
        registered = {}
        for code, module_path in INDICATORS.items():
            module = importlib.import_module(module_path)
            path = DAG_FOLDER / f"dags_ine_{code}.py"
            source = path.read_text()
            self.assertIn("airflow", source)
            self.assertIn("DAG", source)
            namespace = {}
            with patch.object(ine_api, "fetch_indicator_metadata") as fetch, \
                    patch.object(module, "processar_indicador_ine") as process:
                exec(compile(source, str(path), "exec"), namespace)
            fetch.assert_not_called()
            process.assert_not_called()
            years = range(2020, 2023) if code == "0008350" else range(2024, 2027)
            periods = [
                (year, month) for year in years
                for month in (range(1, 13) if module.MONTHLY else (None,))
            ]
            expected = {
                f"ine_{code}_{year}" + (f"_{month:02d}" if month is not None else "")
                for year, month in periods
            }
            found = {
                name: value for name, value in namespace.items()
                if isinstance(value, self.dag_type)
            }
            self.assertEqual(set(found), expected)
            self.assertTrue(registered.keys().isdisjoint(found))
            registered.update(found)
            operators = self.operators[-len(periods):]
            for operator, (year, month) in zip(operators, periods):
                self.assertEqual(
                    operator["op_args"],
                    [code, year] + ([month] if month is not None else []),
                )
        expected_count = sum(
            36 if importlib.import_module(path).MONTHLY else 3
            for path in INDICATORS.values()
        )
        self.assertEqual(len(registered), expected_count)
        self.assertEqual(len({dag.dag_id for dag in self.dags}), expected_count)
        self.assertEqual(len(self.operators), expected_count)
        for dag, operator in zip(self.dags, self.operators):
            self.assertEqual(operator["task_id"], f"task_{dag.dag_id}")
            self.assertIs(operator["python_callable"], self.factory.execute_indicator)
            self.assertEqual(dag.options["schedule"], "0 6 1 * *")
            self.assertEqual(dag.options["start_date"], (2025, 12, 1))
            self.assertFalse(dag.options["catchup"])
            self.assertEqual(dag.options["default_args"]["retries"], 1)
            self.assertEqual(dag.options["default_args"]["retry_delay"], {"minutes": 5})
            self.assertEqual(operator["python_version"], "3.13.2")
            self.assertTrue(operator["inherit_env"])
            self.assertTrue(operator["system_site_packages"])
            self.assertEqual(operator["requirements"], [
                "requests>=2.32.5", "pandas>=2.3.3", "psycopg2-binary>=2.9.11",
                "sqlalchemy>=2.0.45", "apache-airflow[otel]", "apache-airflow[cncf.kubernetes]",
            ])
            self.assertEqual(operator["env_vars"], {
                f"PISTA_DB_{name}": "{{ conn.pista_db." + field + " }}"
                for name, field in (
                    ("HOSTNAME", "host"), ("PORTNUMBER", "port"), ("NAME", "schema"),
                    ("USERNAME", "login"), ("PASSWORD", "password"),
                )
            })

    def test_every_task_dispatches_its_exact_period_database_only(self):
        for code, path in INDICATORS.items():
            module = importlib.import_module(path)
            args = (code, 2026, 8) if module.MONTHLY else (code, 2025)
            expected = dict(varcd=code, ano=args[1], exportar_csv=False, gravar_bd=True)
            if module.MONTHLY:
                expected["mes"] = 8
            with self.subTest(code=code), patch.object(
                module, "processar_indicador_ine", return_value=pd.DataFrame({"ano": [args[1]]}),
            ) as process:
                result = self.factory.execute_indicator(*args)
                process.assert_called_once_with(**expected)
                self.assertIsInstance(result, str)
                self.assertIn("Loaded 1 records", result)
                self.assertIn("no CSV exported", result)
                self.assertIn("Processing month replaced" if module.MONTHLY else
                              "Processing year replaced", result)

    def test_empty_none_and_failures_propagate_for_all_indicators(self):
        for code, path in INDICATORS.items():
            module = importlib.import_module(path)
            args = (code, 2026, 8) if module.MONTHLY else (code, 2025)
            with self.subTest(code=code), patch.object(module, "processar_indicador_ine") as process:
                process.return_value = pd.DataFrame()
                self.assertTrue(self.factory.execute_indicator(*args).startswith("WARNING:"))
                process.return_value = None
                with self.assertRaisesRegex(RuntimeError, "no result"):
                    self.factory.execute_indicator(*args)
                process.side_effect = RuntimeError("database unavailable")
                with self.assertRaisesRegex(RuntimeError, "database unavailable"):
                    self.factory.execute_indicator(*args)

    def test_invalid_or_incompatible_periods_fail_before_processing(self):
        cases = (
            ("0009808", 2026, None), ("0009930", 2025, 8),
            ("0009808", 2026, 0), ("0009808", 2026, 13),
            ("0009808", 2026, True), ("0009930", True, None),
        )
        for code, year, month in cases:
            module = importlib.import_module(INDICATORS[code])
            with self.subTest(code=code, year=year, month=month), \
                    patch.object(module, "processar_indicador_ine") as process, \
                    self.assertRaises(ValueError):
                self.factory.execute_indicator(code, year, month)
            process.assert_not_called()

    def test_callable_is_self_contained_for_virtualenv_serialization(self):
        source = (DAG_FOLDER / "dags_ine.py").read_text()
        function = next(
            node for node in ast.parse(source).body
            if isinstance(node, ast.FunctionDef) and node.name == "execute_indicator"
        )
        namespace = {}
        exec(compile(ast.Module(body=[function], type_ignores=[]), "<virtualenv>", "exec"),
             namespace)
        module = importlib.import_module(INDICATORS["0009808"])
        with patch.object(module, "processar_indicador_ine",
                          return_value=pd.DataFrame({"ano": [2026]})) as process:
            namespace["execute_indicator"]("0009808", 2026, 8)
        process.assert_called_once_with(
            varcd="0009808", ano=2026, mes=8, exportar_csv=False, gravar_bd=True,
        )
        self.assertEqual(list(inspect.signature(namespace["execute_indicator"]).parameters),
                         ["indicator", "year", "month"])

    def test_unpublished_month_propagates_without_substituting_another_period(self):
        module = importlib.import_module(INDICATORS["0009808"])
        with patch.object(module, "processar_indicador_ine",
                          side_effect=RuntimeError("Month 2026-12 is not published")) as process:
            with self.assertRaisesRegex(RuntimeError, "not published"):
                self.factory.execute_indicator("0009808", 2026, 12)
        process.assert_called_once_with(
            varcd="0009808", ano=2026, mes=12, exportar_csv=False, gravar_bd=True,
        )
