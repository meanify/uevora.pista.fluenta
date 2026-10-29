"""Offline execution tests for the all-flow shell runner."""

import importlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from pistadigital.cli.ine_flows import INDICATORS


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "reload-ine-flows.sh"


class IneReloadScriptTests(unittest.TestCase):
    def test_shell_syntax(self):
        subprocess.run(["sh", "-n", str(SCRIPT)], check=True)

    def test_default_preview_discovers_every_registered_flow(self):
        result = subprocess.run(
            ["sh", str(SCRIPT)], cwd="/", capture_output=True, text=True,
            env={**os.environ, "PYTHON": sys.executable}, check=True,
        )
        for code, path in INDICATORS.items():
            module = importlib.import_module(path)
            period = "--all-years-months" if module.MONTHLY else "--all-years"
            self.assertIn(f"INE {code}: {period} --database", result.stdout)
        self.assertIn("Preview only", result.stdout)
        self.assertNotIn("All INE flows completed", result.stdout)

    def test_execution_and_failure_stop_without_live_access(self):
        with tempfile.TemporaryDirectory() as directory:
            fake = Path(directory) / "python"
            log = Path(directory) / "calls"
            fake.write_text(
                '#!/bin/sh\n'
                'if [ "$1" = "-" ]; then\n'
                '  cat >/dev/null\n'
                '  printf "0008350:--all-years\\n0009808:--all-years-months\\n0009880:--all-years\\n"\n'
                'else\n'
                '  printf "%s\\n" "$*" >> "$CALL_LOG"\n'
                '  if [ "$3" = "$FAIL_INDICATOR" ]; then exit 7; fi\n'
                'fi\n',
                encoding="utf-8",
            )
            fake.chmod(0o700)
            for failure in ("", "0009808"):
                with self.subTest(failure=failure):
                    log.write_text("", encoding="utf-8")
                    result = subprocess.run(
                        ["sh", str(SCRIPT), "--database"], cwd="/",
                        capture_output=True, text=True,
                        env={**os.environ, "PYTHON": str(fake),
                             "CALL_LOG": str(log), "FAIL_INDICATOR": failure},
                    )
                    calls = log.read_text(encoding="utf-8").splitlines()
                    self.assertEqual(calls[:2], [
                        "ine_flows.py --indicator 0008350 --all-years --database",
                        "ine_flows.py --indicator 0009808 --all-years-months --database",
                    ])
                    self.assertEqual(len(calls), 2 if failure else 3)
                    self.assertEqual(result.returncode, 7 if failure else 0)
                    if failure:
                        self.assertIn("Earlier periods may already be committed",
                                      result.stderr)
                        self.assertNotIn("All INE flows completed", result.stdout)

    def test_invalid_options_and_help(self):
        for args, status in ((["--help"], 0), (["--unknown"], 2),
                             (["--database", "--dry-run"], 2)):
            with self.subTest(args=args):
                result = subprocess.run(
                    ["sh", str(SCRIPT), *args], capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, status)
                self.assertIn("Usage:", result.stdout + result.stderr)
