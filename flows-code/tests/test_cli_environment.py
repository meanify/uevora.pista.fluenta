import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from pistadigital.cli import environment, ine_flows, lime_flows


class ProjectEnvironmentTests(unittest.TestCase):
    def test_keeps_system_environment_when_dotenv_files_are_missing(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(environment, "PROJECT_ROOT", Path(directory)), \
                patch.dict(
                    os.environ,
                    {
                        "LIME_SURVEY_URL": "system-url",
                        "LIME_SURVEY_USERNAME": "system-user",
                        "LIME_SURVEY_PASSWORD": "system-password",
                    },
                    clear=True,
                ):
            environment.load_project_environment()
            self.assertEqual(os.environ["LIME_SURVEY_URL"], "system-url")
            self.assertEqual(os.environ["LIME_SURVEY_USERNAME"], "system-user")
            self.assertEqual(os.environ["LIME_SURVEY_PASSWORD"], "system-password")

    def test_loads_root_and_project_files_without_overriding_values(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project_root = root / "flows-code"
            project_root.mkdir()
            (root / ".env").write_text(
                "CLI_ENV_FROM_ROOT=root\nCLI_ENV_PRECEDENCE=root\n",
                encoding="utf-8",
            )
            (project_root / ".env").write_text(
                "CLI_ENV_FROM_PROJECT=project\nCLI_ENV_PRECEDENCE=project\n",
                encoding="utf-8",
            )
            with patch.object(environment, "PROJECT_ROOT", project_root), \
                    patch.dict(
                        os.environ,
                        {"CLI_ENV_PRECEDENCE": "process"},
                        clear=True,
                    ):
                environment.load_project_environment()
                self.assertEqual(os.environ["CLI_ENV_FROM_ROOT"], "root")
                self.assertEqual(os.environ["CLI_ENV_FROM_PROJECT"], "project")
                self.assertEqual(os.environ["CLI_ENV_PRECEDENCE"], "process")

    def test_both_clis_load_project_environment_before_processing(self):
        for cli, args, flow_module, flow_name in (
            (
                ine_flows,
                ["-i", "9929", "-y", "2024", "--csv"],
                "pistadigital.flows.ine_0009929_flow",
                "processar_indicador_ine",
            ),
            (
                lime_flows,
                ["--survey", "666914", "--csv"],
                "pistadigital.flows.limesurvey_flows",
                "processar_inquerito",
            ),
        ):
            with self.subTest(cli=cli.__name__), \
                    patch.object(cli, "load_project_environment") as load_env, \
                    patch(
                        f"{flow_module}.{flow_name}",
                        return_value=pd.DataFrame({"id": [1]}),
                    ):
                self.assertEqual(cli.main(args), 0)
                load_env.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
