"""Command-line runner for registered INE indicator flows."""

import argparse
import importlib
import logging
from pathlib import Path

import pandas as pd

from pistadigital.cli.environment import load_project_environment
from pistadigital.utils.ine_api import (
    available_monthly_periods, fetch_available_annual_years,
    fetch_indicator_metadata,
)
from pistadigital.utils.ine_output import write_csv


logger = logging.getLogger("pista.fluenta.ine_cli")
INDICATORS = {
    "0008350": "pistadigital.utils.ine_0008350_flow",
    "0009183": "pistadigital.utils.ine_0009183_flow",
    "0009808": "pistadigital.utils.ine_0009808_flow",
    "0009812": "pistadigital.utils.ine_0009812_flow",
    "0009873": "pistadigital.utils.ine_0009873_flow",
    "0009874": "pistadigital.utils.ine_0009874_flow",
    "0009876": "pistadigital.utils.ine_0009876_flow",
    "0009877": "pistadigital.utils.ine_0009877_flow",
    "0009880": "pistadigital.utils.ine_0009880_flow",
    "0009929": "pistadigital.utils.ine_0009929_flow",
    "0009930": "pistadigital.utils.ine_0009930_flow",
    "0010735": "pistadigital.utils.ine_0010735_flow",
    "0010736": "pistadigital.utils.ine_0010736_flow",
    "0011140": "pistadigital.utils.ine_0011140_flow",
    "0012093": "pistadigital.utils.ine_0012093_flow",
}


def indicator_code(value):
    if not value.isascii() or not value.isdigit() or len(value) > 7:
        raise argparse.ArgumentTypeError(
            "Indicator must contain at most seven digits.")
    return value.zfill(7)


def year_number(value):
    year = int(value)
    if not 1 <= year <= 9999:
        raise argparse.ArgumentTypeError("Year must be between 1 and 9999.")
    return year


def main(command_line=None):
    parser = argparse.ArgumentParser(
        description="Run INE flows, writing to PostgreSQL, CSV, or both."
    )
    parser.add_argument("-i", "--indicator", required=True, type=indicator_code,
                        choices=INDICATORS)
    period = parser.add_mutually_exclusive_group(required=True)
    period.add_argument("-y", "--year", type=year_number)
    period.add_argument(
        "--all-years", action="store_true",
        help="Process every annual period available in INE metadata.",
    )
    period.add_argument(
        "--all-years-months", action="store_true",
        help="Process every published year/month for a monthly indicator.",
    )
    months = parser.add_mutually_exclusive_group()
    months.add_argument("-m", "--month", type=int, choices=range(1, 13),
                        help="Single month for monthly indicators; invalid for annual ones.")
    months.add_argument(
        "--all-months", action="store_true",
        help="Process every published month of --year for a monthly indicator.",
    )
    parser.add_argument("--database", action="store_true",
                        help="Write records to PostgreSQL.")
    parser.add_argument("--csv", action="store_true",
                        help="Export records to CSV.")
    parser.add_argument("-o", "--output", type=Path,
                        help="CSV path (requires --csv).")
    parser.add_argument("-d", "--debug", action="store_true",
                        help="Enable debug logging and processing error tracebacks.")
    args = parser.parse_args(command_line)
    if not args.database and not args.csv:
        parser.error("Choose at least one output: --database and/or --csv.")
    if args.output is not None and not args.csv:
        parser.error("--output requires --csv.")
    if args.all_months and args.year is None:
        parser.error("--all-months requires --year.")
    if args.all_years_months and args.month is not None:
        parser.error("--all-years-months cannot be combined with --month.")

    load_project_environment()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)
    module = importlib.import_module(INDICATORS[args.indicator])
    if args.all_years and module.MONTHLY:
        parser.error("--all-years is only supported for annual indicators.")
    monthly_batch = args.all_months or args.all_years_months
    if monthly_batch and not module.MONTHLY:
        parser.error("--all-months and --all-years-months require a monthly indicator.")
    if module.MONTHLY and args.month is None and not monthly_batch:
        parser.error("This indicator is monthly; --month or --all-months is required.")
    if not module.MONTHLY and args.month is not None:
        parser.error(
            f"Indicator {args.indicator} is annual; do not supply --month.")

    try:
        if args.all_years or monthly_batch:
            if monthly_batch:
                periods = available_monthly_periods(
                    fetch_indicator_metadata(args.indicator)
                )
                if args.all_months:
                    periods = [
                        (year, month) for year, month in periods
                        if year == args.year
                    ]
                    if not periods:
                        raise ValueError(
                            f"No published monthly periods found for year {args.year}."
                        )
                suffix = (
                    f"{args.year}_all_months" if args.all_months
                    else "all_years_months"
                )
            else:
                periods = [
                    (year, None)
                    for year in fetch_available_annual_years(args.indicator)
                ]
                suffix = "all_years"
            logger.info(
                "Processing INE %s for available periods: %s",
                args.indicator,
                ", ".join(
                    str(year) if month is None else f"{year:04d}-{month:02d}"
                    for year, month in periods
                ),
            )
            frames = [
                module.processar_indicador_ine(
                    varcd=args.indicator,
                    ano=year,
                    exportar_csv=False,
                    gravar_bd=args.database,
                    **({"mes": month} if month is not None else {}),
                )
                for year, month in periods
            ]
            df = pd.concat(frames, ignore_index=True)
            if args.csv:
                output = args.output or (
                    Path("/tmp")
                    / f"ine_{args.indicator}_{suffix}_tratado.csv"
                )
                write_csv(df, output)
        else:
            options = {
                "varcd": args.indicator,
                "ano": args.year,
                "exportar_csv": args.csv,
                "gravar_bd": args.database,
                "caminho_csv": (
                    args.output
                    if args.output is not None or not args.csv
                    else Path("/tmp")
                    / f"ine_{args.indicator}_{args.year}_tratado.csv"
                ),
            }
            if module.MONTHLY:
                options["mes"] = args.month
                if args.csv and args.output is None:
                    options["caminho_csv"] = (
                        Path("/tmp")
                        / f"ine_{args.indicator}_{args.year}_{args.month:02d}_tratado.csv"
                    )
            df = module.processar_indicador_ine(**options)
    except (RuntimeError, ValueError, OSError) as exc:
        logger.error("INE %s failed: %s", args.indicator, exc,
                     exc_info=args.debug)
        return 1
    if df.empty:
        logger.warning(
            "No records returned; existing database records were preserved.")
    else:
        logger.info("Completed INE %s: %d records.", args.indicator, len(df))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
