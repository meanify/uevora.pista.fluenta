import contextlib
import io
import logging
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import warnings
from unittest.mock import Mock, call, patch

import pandas as pd
from sqlalchemy import create_engine, text

from pistadigital.cli import lime_flows as cli
from pistadigital.utils import limesurvey_flows as flows


SURVEY = "237583"


def raw_answers():
    return pd.DataFrame({"id": [4, 5], "submitdate": ["2024-01-01", "2024-01-02"]})


class LimeCliTests(unittest.TestCase):
    def test_citric_info_requires_debug_but_warnings_and_progress_remain(self):
        session_logger = logging.getLogger("citric.session")

        def process(**options):
            session_logger.debug("RPC debug")
            session_logger.info("RPC noise")
            session_logger.warning("RPC warning")
            session_logger.error("RPC error")
            flows.logger.info("Batch progress")
            return raw_answers()

        for flags in ([], ["--debug"]):
            with self.subTest(flags=flags), \
                    patch.object(session_logger, "level", logging.NOTSET), \
                    patch.object(flows, "processar_inquerito", side_effect=process), \
                    self.assertLogs(level="DEBUG") as captured:
                self.assertEqual(cli.main(["-s", SURVEY, "--csv", *flags]), 0)
            messages = [record.getMessage() for record in captured.records]
            if "--debug" in flags:
                self.assertIn("RPC debug", messages)
                self.assertIn("RPC noise", messages)
            else:
                self.assertNotIn("RPC debug", messages)
                self.assertNotIn("RPC noise", messages)
            self.assertIn("RPC warning", messages)
            self.assertIn("RPC error", messages)
            self.assertIn("Batch progress", messages)

    def test_output_modes_and_debug_execute(self):
        for flags in (["--csv"], ["--database"], ["--csv", "--database", "--debug"]):
            with self.subTest(flags=flags), patch.object(
                flows, "processar_inquerito", return_value=raw_answers()
            ) as process:
                self.assertEqual(cli.main(["-s", SURVEY, *flags]), 0)
                process.assert_called_once_with(
                    survey_id=SURVEY, from_response_id=None, to_response_id=None,
                    increment=1000,
                    exportar_csv="--csv" in flags, gravar_bd="--database" in flags,
                    caminho_csv=None,
                    output_directory=(
                        Path("/tmp") if "--csv" in flags else None
                    ),
                )

    def test_bounded_response_range_is_forwarded(self):
        with patch.object(
            flows, "processar_inquerito", return_value=raw_answers()
        ) as process:
            self.assertEqual(cli.main([
                "-s", SURVEY, "--csv", "-f", "4", "-t", "25",
                "--increment", "10",
            ]), 0)
        self.assertEqual(process.call_args.kwargs["from_response_id"], 4)
        self.assertEqual(process.call_args.kwargs["to_response_id"], 25)
        self.assertEqual(process.call_args.kwargs["increment"], 10)

    def test_compatibility_commands(self):
        for command, csv, database in (("export", True, False), ("all", True, True)):
            with self.subTest(command=command), patch.object(
                flows, "processar_inquerito", return_value=raw_answers()
            ) as process:
                self.assertEqual(cli.main(["--debug", command, "-s", SURVEY, "-f", "4"]), 0)
                self.assertEqual(process.call_args.kwargs["from_response_id"], 4)
                self.assertEqual(process.call_args.kwargs["exportar_csv"], csv)
                self.assertEqual(process.call_args.kwargs["gravar_bd"], database)
        with patch.object(flows, "load_answers", return_value="Loaded") as load:
            self.assertEqual(
                cli.main(["load", "-s", SURVEY, "--file", "input.csv"]), 0
            )
            load.assert_called_once_with(SURVEY, Path("input.csv"))
        with patch.object(flows, "get_last_answer_id", return_value=6), \
                self.assertLogs("pista.fluenta.lime_cli", level="INFO") as captured:
            self.assertEqual(cli.main(["latest", "-s", SURVEY]), 0)
        self.assertIn(f"Latest response ID for survey {SURVEY}: 6", captured.output[0])

    def test_invalid_options(self):
        cases = [
            ["-s", SURVEY],
            ["-s", SURVEY, "--database", "--output", "out.csv"],
            ["-s", SURVEY, "--csv", "--increment", "0"],
            ["-s", SURVEY, "--csv", "--from-response-id", "-1"],
            ["-s", SURVEY, "--to-response-id", "0", "--csv"],
            ["latest", "-s", SURVEY, "--to-response-id", "10"],
            ["-s", "unknown", "--csv"],
            ["export", "-s", SURVEY, "--database"],
            ["load", "-s", SURVEY],
            ["load", "-s", SURVEY, "-f", "input.csv"],
            ["load", "-s", SURVEY, "--file", "in.csv", "--from-response-id", "1"],
            ["load", "-s", SURVEY, "--file", "in.csv", "--to-response-id", "10"],
            ["-s", SURVEY, "--csv", "--file", "in.csv"],
            ["-s", SURVEY, "--csv", "-f", "not-an-id"],
        ]
        for args in cases:
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()), \
                    patch.object(flows, "processar_inquerito") as process:
                with self.assertRaises(SystemExit) as error:
                    cli.main(args)
                self.assertEqual(error.exception.code, 2)
                process.assert_not_called()

    def test_failure_exit_code_and_empty_success(self):
        with patch.object(flows, "processar_inquerito", side_effect=RuntimeError("API down")):
            self.assertEqual(cli.main(["-s", SURVEY, "--csv"]), 1)
        with patch.object(flows, "processar_inquerito", return_value=pd.DataFrame()):
            self.assertEqual(cli.main(["-s", SURVEY, "--csv"]), 0)

    def test_entry_point_help(self):
        entrypoint = Path(__file__).resolve().parents[1] / "lime_flows.py"
        result = subprocess.run(
            [sys.executable, str(entrypoint), "--help"], capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        for flag in (
            "--database", "--csv", "--output", "--debug", "--to-response-id",
        ):
            self.assertIn(flag, result.stdout)


class LimeOutputTests(unittest.TestCase):
    def setUp(self):
        discovery = patch.object(
            flows, "get_export_end_id",
            side_effect=lambda survey, start: start + 1000,
        )
        self.discover_end = discovery.start()
        self.addCleanup(discovery.stop)

    def test_large_mixed_type_exports_preserve_values_without_dtype_warning(self):
        header = ["id", "submitdate", "startdate", "token", "G01Q22[SQ002]"]
        header += [f"question_{index}" for index in range(19)]
        numeric_row = ";".join(
            ["4", "2024-01-01", "2024-01-01", "participant-a", "2"]
            + ["1"] * 19
        )
        text_row = numeric_row.replace(";2;", ";not recorded;", 1)
        incomplete_row = ";".join(
            ["5", "", "2024-01-01", "participant-a", "3"] + ["1"] * 19
        )
        content = (
            ";".join(header) + "\n" + (numeric_row + "\n") * 69999
            + text_row + "\n" + incomplete_row + "\n"
        ).encode()
        mapping = {
            "date_fields": ["submitdate", "startdate"],
            "drop_columns": ["startdate"],
        }
        for extractor in (flows.no_participants, flows.participants):
            client = Mock()
            client.export_responses.return_value = content
            client.list_participants.return_value = [{
                "tid": 1,
                "token": "participant-a",
                "participant_info": {
                    "firstname": "Test", "lastname": "Participant",
                    "email": "test@example.com",
                },
            }]
            context = Mock()
            context.__enter__ = Mock(return_value=client)
            context.__exit__ = Mock(return_value=False)
            with self.subTest(extractor=extractor.__name__), \
                    patch.dict(flows.survey_mappings, {"test": mapping}), \
                    patch.object(flows, "limesurvey_client", return_value=context), \
                    warnings.catch_warnings():
                warnings.simplefilter("error", pd.errors.DtypeWarning)
                answers = extractor("test", 1, None)
                self.assertEqual(len(answers), 70000)
                self.assertEqual(answers["G01Q22[SQ002]"].iloc[0], "2")
                self.assertEqual(answers["G01Q22[SQ002]"].iloc[-1], "not recorded")
                self.assertEqual(
                    answers["submitdate"].iloc[0], pd.Timestamp("2024-01-01")
                )
                self.assertEqual(answers["id"].iloc[0], 4)
                self.assertNotIn("startdate", answers.columns)
                if extractor is flows.participants:
                    self.assertTrue(answers["firstname"].eq("Test").all())

    def test_csv_only_has_no_database_dependency(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "survey.csv"
            with patch.dict(os.environ, {}, clear=True), \
                    patch.object(flows, "no_participants", return_value=raw_answers()) as fetch, \
                    patch.object(flows, "get_engine", side_effect=AssertionError("DB accessed")), \
                    patch.object(flows, "get_last_answer_id",
                                 side_effect=AssertionError("Resume queried")):
                df = flows.processar_inquerito(SURVEY, caminho_csv=output)
            fetch.assert_called_once_with(SURVEY, 1, 1000)
            stored = pd.read_csv(output, sep=";")
            self.assertEqual(stored["id"].tolist(), [4, 5])
            self.assertIn("data_submissao", df.columns)
            self.assertIn("create_date", stored.columns)

    def test_output_directory_override_writes_to_requested_directory(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(flows, "no_participants", return_value=raw_answers()):
            flows.processar_inquerito(
                SURVEY,
                caminho_csv=None,
                output_directory=Path(directory),
            )
            self.assertTrue(
                (Path(directory) / "237583_answers_4-5.csv").exists()
            )

    def test_open_ended_export_starts_at_requested_response_id(self):
        with patch.object(flows, "no_participants", return_value=raw_answers()) as fetch:
            answers = flows.processar_inquerito(
                SURVEY, from_response_id=142927, exportar_csv=False
            )
        self.assertEqual(answers["id"].tolist(), [4, 5])
        fetch.assert_called_once_with(SURVEY, 142927, 1000)
        self.discover_end.assert_called_once_with(SURVEY, 142927)

    def test_database_only_resumes_without_csv(self):
        with patch.object(flows, "get_last_answer_id", return_value=10) as latest, \
                patch.object(flows, "no_participants", return_value=raw_answers()) as fetch, \
                patch.object(flows, "write_answers") as write, \
                patch.object(pd.DataFrame, "to_csv") as export:
            flows.processar_inquerito(SURVEY, exportar_csv=False, gravar_bd=True)
        latest.assert_called_once_with(SURVEY)
        fetch.assert_called_once_with(SURVEY, 10, 1000)
        write.assert_called_once()
        export.assert_not_called()

    def test_explicit_start_skips_resume_and_both_outputs_fetch_once(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "both.csv"
            with patch.object(flows, "get_last_answer_id") as latest, \
                    patch.object(flows, "no_participants", return_value=raw_answers()) as fetch, \
                    patch.object(flows, "write_answers") as write:
                flows.processar_inquerito(
                    SURVEY, 4, exportar_csv=True, gravar_bd=True, caminho_csv=output
                )
            latest.assert_not_called()
            fetch.assert_called_once_with(SURVEY, 4, 1000)
            write.assert_called_once()
            self.assertTrue(output.exists())

    def test_empty_results_write_nothing(self):
        with patch.object(flows, "no_participants", return_value=pd.DataFrame()), \
                patch.object(flows, "write_answers") as write, \
                patch.object(pd.DataFrame, "to_csv") as export:
            df = flows.processar_inquerito(SURVEY, 1, gravar_bd=True)
        self.assertTrue(df.empty)
        write.assert_not_called()
        export.assert_not_called()

    def test_bounded_range_continues_after_empty_batch_and_writes_once(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "bounded.csv"
            with patch.object(
                flows, "no_participants",
                side_effect=[pd.DataFrame(), raw_answers()],
            ) as fetch, patch.object(flows, "write_answers") as write:
                answers = flows.processar_inquerito(
                    SURVEY,
                    from_response_id=1,
                    increment=2,
                    to_response_id=5,
                    caminho_csv=output,
                    gravar_bd=True,
                )

            self.assertEqual(fetch.call_args_list, [
                call(SURVEY, 1, 2),
                call(SURVEY, 4, 1),
            ])
            self.assertEqual(answers["id"].tolist(), [4, 5])
            self.assertEqual(pd.read_csv(output, sep=";")["id"].tolist(), [4, 5])
            write.assert_called_once()
            self.assertEqual(write.call_args.args[1]["id"].tolist(), [4, 5])
            self.discover_end.assert_not_called()

    def test_open_ended_export_batches_through_gaps_to_snapshot_end(self):
        self.discover_end.side_effect = None
        self.discover_end.return_value = 8
        later_answers = pd.DataFrame({
            "id": [7, 8], "submitdate": ["2024-01-01", "2024-01-02"],
        })
        with patch.object(
            flows, "no_participants",
            side_effect=[pd.DataFrame(), raw_answers(), later_answers],
        ) as fetch, patch.object(flows, "write_answers") as write:
            answers = flows.processar_inquerito(
                SURVEY, 1, increment=2, exportar_csv=False, gravar_bd=True,
            )
        self.assertEqual(fetch.call_args_list, [
            call(SURVEY, 1, 2), call(SURVEY, 4, 2), call(SURVEY, 7, 1),
        ])
        self.assertEqual(answers["id"].tolist(), [4, 5, 7, 8])
        write.assert_called_once()

    def test_open_ended_export_without_ids_skips_fetch_and_outputs(self):
        self.discover_end.side_effect = None
        self.discover_end.return_value = None
        with patch.object(flows, "no_participants") as fetch, \
                patch.object(flows, "write_answers") as write, \
                patch.object(pd.DataFrame, "to_csv") as export:
            answers = flows.processar_inquerito(SURVEY, 1, gravar_bd=True)
        self.assertTrue(answers.empty)
        fetch.assert_not_called()
        write.assert_not_called()
        export.assert_not_called()

    def test_discovery_failure_does_not_fetch_or_write(self):
        self.discover_end.side_effect = RuntimeError("ID discovery failed")
        with patch.object(flows, "no_participants") as fetch, \
                patch.object(flows, "write_answers") as write, \
                patch.object(pd.DataFrame, "to_csv") as export:
            with self.assertRaisesRegex(RuntimeError, "ID discovery failed"):
                flows.processar_inquerito(SURVEY, 1, gravar_bd=True)
        fetch.assert_not_called()
        write.assert_not_called()
        export.assert_not_called()

    def test_bounded_range_rejects_end_before_start(self):
        with patch.object(flows, "no_participants") as fetch:
            with self.assertRaisesRegex(ValueError, "greater than or equal"):
                flows.processar_inquerito(
                    SURVEY, from_response_id=5, to_response_id=4
                )
        fetch.assert_not_called()

    def test_batch_progress_logs_include_empty_batches_counts_and_timing(self):
        with patch.object(
            flows, "no_participants",
            side_effect=[pd.DataFrame(), raw_answers()],
        ), patch.object(flows, "perf_counter", side_effect=[10, 12, 20, 23]), \
                self.assertLogs("pista.fluenta", level="INFO") as captured:
            flows.processar_inquerito(
                SURVEY, 1, increment=2, to_response_id=5, exportar_csv=False,
            )
        messages = [record.getMessage() for record in captured.records]
        self.assertEqual(messages, [
            f"Survey {SURVEY}: starting batch 1/2, response IDs 1-3.",
            f"Survey {SURVEY}: completed batch 1/2, response IDs 1-3: "
            "0 completed responses, 0 cumulative, 2.00 seconds.",
            f"Survey {SURVEY}: starting batch 2/2, response IDs 4-5.",
            f"Survey {SURVEY}: completed batch 2/2, response IDs 4-5: "
            "2 completed responses, 2 cumulative, 3.00 seconds.",
            f"Survey {SURVEY}: combining 1 non-empty batches (2 completed responses).",
            f"Survey {SURVEY}: transforming 2 completed responses.",
        ])

    def test_open_ended_progress_and_output_stages(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "progress.csv"
            with patch.object(flows, "no_participants", return_value=raw_answers()), \
                    patch.object(flows, "write_answers"), \
                    patch.object(flows, "perf_counter", side_effect=[10, 12]), \
                    self.assertLogs("pista.fluenta", level="INFO") as captured:
                flows.processar_inquerito(
                    SURVEY, 1, gravar_bd=True, caminho_csv=output,
                )
            self.assertTrue(output.exists())
        messages = [record.getMessage() for record in captured.records]
        self.assertEqual(messages, [
            f"Survey {SURVEY}: starting batch 1/1, response IDs 1-1001.",
            f"Survey {SURVEY}: completed batch 1/1, response IDs 1-1001: "
            "2 completed responses, 2 cumulative, 2.00 seconds.",
            f"Survey {SURVEY}: combining 1 non-empty batches (2 completed responses).",
            f"Survey {SURVEY}: transforming 2 completed responses.",
            f"Survey {SURVEY}: writing 2 responses to database table "
            f"{flows.obter_mapeamento(SURVEY)['table_name']}.",
            f"Survey {SURVEY}: database write completed.",
            f"Survey {SURVEY}: writing 2 responses to CSV {output}.",
            f"Exported answers to {output}",
        ])

    def test_failed_batch_does_not_log_completion(self):
        with patch.object(
            flows, "no_participants", side_effect=RuntimeError("API down"),
        ), self.assertLogs("pista.fluenta", level="INFO") as captured:
            with self.assertRaisesRegex(RuntimeError, "API down"):
                flows.processar_inquerito(
                    SURVEY, 1, to_response_id=1, exportar_csv=False,
                )
        self.assertEqual(
            [record.getMessage() for record in captured.records],
            [f"Survey {SURVEY}: starting batch 1/1, response IDs 1-1."],
        )

    def test_participant_survey_uses_same_output_selection(self):
        with patch.object(flows, "participants", return_value=raw_answers()) as fetch, \
                patch.object(flows, "write_answers") as write:
            flows.processar_inquerito("666914", 1, exportar_csv=False, gravar_bd=True)
        fetch.assert_called_once_with("666914", 1, 1000)
        write.assert_called_once()

    def test_append_is_transactional_and_disposes_engine(self):
        mapping = flows.obter_mapeamento(SURVEY)
        engine = create_engine("sqlite:///:memory:")
        table = mapping["table_name"]
        try:
            with engine.begin() as conn:
                conn.execute(text(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY)"))
                conn.execute(text(f"INSERT INTO {table} VALUES (1)"))
            with patch.object(flows, "get_engine", return_value=engine), \
                    patch.object(engine, "dispose") as dispose:
                with self.assertRaisesRegex(RuntimeError, "rolled back"):
                    flows.write_answers(SURVEY, pd.DataFrame({"id": [2, 1]}))
                dispose.assert_called_once()
            with engine.connect() as conn:
                self.assertEqual(list(conn.execute(text(f"SELECT id FROM {table}"))), [(1,)])
        finally:
            engine.dispose()

    def test_resume_failure_does_not_silently_start_from_zero(self):
        engine = create_engine("sqlite:///:memory:")
        try:
            with patch.object(flows, "get_engine", return_value=engine), \
                    patch.object(engine, "dispose") as dispose:
                with self.assertRaisesRegex(RuntimeError, "next response ID"):
                    flows.get_last_answer_id(SURVEY)
                dispose.assert_called_once()
        finally:
            engine.dispose()

    def test_empty_table_starts_at_one(self):
        engine = create_engine("sqlite:///:memory:")
        table = flows.obter_mapeamento(SURVEY)["table_name"]
        try:
            with engine.begin() as conn:
                conn.execute(text(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY)"))
            with patch.object(flows, "get_engine", return_value=engine), \
                    patch.object(engine, "dispose"):
                self.assertEqual(flows.get_last_answer_id(SURVEY), 1)
        finally:
            engine.dispose()

    def test_legacy_python_wrappers_keep_outputs(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.dict(os.environ, {"PISTAFLOWS_EXPORTS_PATH": directory}), \
                patch.object(flows, "no_participants", return_value=raw_answers()) as fetch, \
                patch.object(flows, "get_last_answer_id", return_value=4) as latest, \
                patch.object(flows, "write_answers") as write:
            filename = flows.export_answers(SURVEY)
            self.assertTrue(Path(filename).exists())
            latest.assert_not_called()
            write.assert_not_called()
            self.assertEqual(fetch.call_args.args[1], 1)
            result = flows.export_and_load(SURVEY, None, 1000)
            self.assertIn("Successfully loaded 2", result)
            latest.assert_called_once_with(SURVEY)
            self.assertEqual(fetch.call_args.args[1:], (4, 1000))
            write.assert_called_once()
            result = flows.load_answers(SURVEY, filename)
            self.assertIn("Successfully loaded 2", result)
            self.assertEqual(write.call_count, 2)

    def test_settings_and_api_failures_are_explicit(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "Missing LimeSurvey settings"):
                flows.limesurvey_client()
        from citric.exceptions import LimeSurveyError
        with patch.object(flows, "no_participants", side_effect=LimeSurveyError("API failure")):
            self.assertEqual(cli.main(["-s", SURVEY, "--csv"]), 1)

    def test_real_extractor_csv_only_uses_api_without_database(self):
        client = Mock()
        client.export_responses.return_value = (
            b"id;submitdate;startdate\n4;2024-01-01;2024-01-01\n"
        )
        context = Mock()
        context.__enter__ = Mock(return_value=client)
        context.__exit__ = Mock(return_value=False)
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(flows, "limesurvey_client", return_value=context), \
                    patch.object(flows, "get_engine", side_effect=AssertionError("DB")), \
                    patch.object(flows, "get_last_answer_id", side_effect=AssertionError("DB")):
                frame = flows.processar_inquerito(
                    SURVEY, caminho_csv=Path(directory) / "api.csv"
                )
            self.assertEqual(frame["id"].tolist(), [4])
            self.assertEqual(client.export_responses.call_args.kwargs["from_response_id"], 1)
            self.assertEqual(
                client.export_responses.call_args.kwargs["to_response_id"], 1001,
            )


class LimeExportEndTests(unittest.TestCase):
    def test_default_cli_exports_participant_survey_in_batches(self):
        client = Mock()
        header = "id;submitdate;G00Q19;token\n"
        client.export_responses.side_effect = [
            b"id\n1\n1002\n2500\n",
            *((
                header + f"{response_id};2024-01-01;2024-01-01;participant-a\n"
            ).encode() for response_id in (1, 1002, 2500)),
        ]
        client.list_participants.return_value = [{
            "tid": 1, "token": "participant-a",
            "participant_info": {
                "firstname": "Test", "lastname": "Participant",
                "email": "test@example.com",
            },
        }]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "survey.csv"
            with patch.object(
                flows, "limesurvey_client",
                side_effect=lambda: contextlib.nullcontext(client),
            ), patch.object(flows, "get_engine", side_effect=AssertionError("DB")), \
                    patch.object(flows, "get_last_answer_id", side_effect=AssertionError("DB")), \
                    self.assertLogs("pista.fluenta", level="INFO") as captured:
                result = cli.main([
                    "--survey", "666914", "--csv", "--output", str(output),
                ])
            self.assertEqual(result, 0)
            stored = pd.read_csv(output, sep=";")
        self.assertEqual(stored["id"].tolist(), [1, 1002, 2500])
        self.assertEqual(stored["primeiro_nome"].tolist(), ["Test"] * 3)
        calls = client.export_responses.call_args_list
        self.assertEqual(
            [(entry.kwargs["from_response_id"], entry.kwargs["to_response_id"])
             for entry in calls[1:]],
            [(1, 1001), (1002, 2002), (2003, 2500)],
        )
        for batch_number in range(1, 4):
            self.assertTrue(any(
                f"completed batch {batch_number}/3" in record.getMessage()
                for record in captured.records
            ))

    def test_id_discovery_uses_only_ids_and_actual_maximum_not_count(self):
        client = Mock()
        client.export_responses.return_value = b"id\n5\n9001\n22\n"
        context = contextlib.nullcontext(client)
        with patch.object(flows, "limesurvey_client", return_value=context):
            self.assertEqual(flows.get_export_end_id(SURVEY, 5), 9001)
        client.export_responses.assert_called_once_with(
            SURVEY, file_format="csv", heading_type="code",
            from_response_id=5, fields=["id"],
        )

    def test_empty_id_exports(self):
        for content in (b"", b"\r\n", b"id\n"):
            client = Mock()
            client.export_responses.return_value = content
            with self.subTest(content=content), patch.object(
                flows, "limesurvey_client", return_value=contextlib.nullcontext(client),
            ):
                self.assertIsNone(flows.get_export_end_id(SURVEY, 1))

    def test_invalid_ids_fail_explicitly(self):
        for content in (b"id\ninvalid\n", b"id\n0\n", b"other\n1\n"):
            client = Mock()
            client.export_responses.return_value = content
            with self.subTest(content=content), patch.object(
                flows, "limesurvey_client", return_value=contextlib.nullcontext(client),
            ):
                with self.assertRaises(ValueError):
                    flows.get_export_end_id(SURVEY, 1)

    def test_real_open_ended_export_fetches_multiple_batches(self):
        client = Mock()
        client.export_responses.side_effect = [
            b"id\n1\n8\n",
            b"id;submitdate;startdate\n1;2024-01-01;2024-01-01\n",
            b"id;submitdate;startdate\n",
            b"id;submitdate;startdate\n8;2024-01-02;2024-01-02\n",
        ]
        with patch.object(
            flows, "limesurvey_client",
            side_effect=lambda: contextlib.nullcontext(client),
        ), patch.object(flows, "get_engine", side_effect=AssertionError("DB")), \
                self.assertLogs("pista.fluenta", level="INFO") as captured:
            answers = flows.processar_inquerito(
                SURVEY, increment=2, exportar_csv=False,
            )
        self.assertEqual(answers["id"].tolist(), [1, 8])
        calls = client.export_responses.call_args_list
        self.assertEqual(calls[0].kwargs["fields"], ["id"])
        self.assertEqual(
            [(entry.kwargs["from_response_id"], entry.kwargs["to_response_id"])
             for entry in calls[1:]],
            [(1, 3), (4, 6), (7, 8)],
        )
        self.assertTrue(any(
            "completed batch 3/3" in record.getMessage()
            for record in captured.records
        ))


if __name__ == "__main__":
    unittest.main()
