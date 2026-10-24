"""Run LimeSurvey flows with CSV and/or database output."""

import argparse
import logging
from pathlib import Path

from citric.exceptions import LimeSurveyError, ResponseMismatchError
import requests

from pistadigital.cli.environment import load_project_environment
from pistadigital.utils import limesurvey_flows as flows


logger = logging.getLogger("pista.fluenta.lime_cli")


def positive_integer(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("Value must be a positive integer.")
    return number


def main(command_line=None):
    parser = argparse.ArgumentParser(
        description="Run LimeSurvey flows, writing to PostgreSQL, CSV, or both."
    )
    parser.add_argument("command", nargs="?", choices=("latest", "export", "load", "all"),
                        help="Optional compatibility command.")
    parser.add_argument("-s", "--survey", required=True, choices=flows.survey_mappings,
                        help="Mapped survey ID.")
    parser.add_argument("-f", "--from-response-id", type=positive_integer,
                        help="First response ID; defaults to resume for DB, 1 for CSV-only.")
    parser.add_argument("-t", "--to-response-id", type=positive_integer,
                        help="Inclusive last response ID; fetch successive intervals through it.")
    parser.add_argument("-i", "--increment", type=positive_integer, default=1000,
                        help="Response-ID interval step for all exports (default: 1000).")
    parser.add_argument("--file", type=Path,
                        help="Existing CSV to load (load command only).")
    parser.add_argument("--database", action="store_true",
                        help="Write records to PostgreSQL.")
    parser.add_argument("--csv", action="store_true",
                        help="Export records to CSV.")
    parser.add_argument("-o", "--output", type=Path,
                        help="CSV path (requires --csv).")
    parser.add_argument("-d", "--debug", action="store_true",
                        help="Enable debug logging and processing error tracebacks.")
    args = parser.parse_args(command_line)

    if args.command is not None and (args.database or args.csv):
        parser.error(
            "Use either a compatibility command or output flags, not both.")
    if args.command == "export":
        args.csv = True
    elif args.command == "all":
        args.database = args.csv = True
    elif args.command == "load":
        args.database = True
        if args.file is None:
            parser.error("load requires --file.")
        if args.from_response_id is not None:
            parser.error("load does not accept --from-response-id.")
        if args.to_response_id is not None:
            parser.error("load does not accept --to-response-id.")
    if args.command != "load" and args.file is not None:
        parser.error("--file is only valid with the load command.")
    if args.command == "latest":
        if (args.output is not None or args.from_response_id is not None
                or args.to_response_id is not None):
            parser.error(
                "latest does not accept output or response-range options.")
    else:
        if not args.database and not args.csv:
            parser.error(
                "Choose at least one output: --database and/or --csv.")
        if args.output is not None and not args.csv:
            parser.error("--output requires --csv.")

    load_project_environment()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)
    logging.getLogger("citric.session").setLevel(
        logging.DEBUG if args.debug else logging.WARNING
    )
    try:
        if args.command == "latest":
            logger.info(
                "Latest response ID for survey %s: %s",
                args.survey,
                flows.get_last_answer_id(args.survey),
            )
        elif args.command == "load":
            logger.info("%s", flows.load_answers(args.survey, args.file))
        else:
            df = flows.processar_inquerito(
                survey_id=args.survey,
                from_response_id=args.from_response_id,
                to_response_id=args.to_response_id,
                increment=args.increment,
                exportar_csv=args.csv,
                gravar_bd=args.database,
                caminho_csv=args.output,
                output_directory=(
                    Path("/tmp")
                    if args.csv and args.output is None
                    else None
                ),
            )
            if df.empty:
                logger.warning(
                    "No completed responses returned; no outputs written.")
            else:
                logger.info("Completed LimeSurvey %s: %d records.",
                            args.survey, len(df))
    except (RuntimeError, ValueError, OSError, requests.RequestException,
            LimeSurveyError, ResponseMismatchError) as exc:
        logger.error("LimeSurvey %s failed: %s",
                     args.survey, exc, exc_info=args.debug)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
