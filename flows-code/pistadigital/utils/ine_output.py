"""CSV and database output shared by annual and monthly INE indicators."""

import logging
from pathlib import Path
import re

import pandas as pd
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from pistadigital.utils.database import get_engine

logger = logging.getLogger("pista.fluenta.ine_output")


def create_indicator_table(table_name: str, create_table_sql: str) -> None:
    """Create an indicator table without extracting or replacing any data."""
    engine = get_engine()
    try:
        with engine.begin() as connection:
            connection.execute(text(create_table_sql))
    except SQLAlchemyError as exc:
        raise RuntimeError(
            f"Erro ao criar/verificar a tabela {table_name}: {exc}"
        ) from exc
    finally:
        engine.dispose()


def write_csv(df: pd.DataFrame, path: str | Path) -> None:
    """Export INE records with a header, comma delimiters, and no index."""
    df.to_csv(path, index=False, sep=",")
    logger.info("Exported %d records to %s.", len(df), path)


def validate_period(year: int, month: int | None = None) -> None:
    if isinstance(year, bool) or not isinstance(year, int) or not 1 <= year <= 9999:
        raise ValueError("Year must be an integer between 1 and 9999.")
    if month is not None and (
        isinstance(month, bool) or not isinstance(month, int) or not 1 <= month <= 12
    ):
        raise ValueError("Month must be an integer between 1 and 12.")


def validate_annual_frame(df, columns, lengths, year):
    """Validate annual CSV and database rows against the indicator's dimensions."""
    if df.columns.tolist() != columns:
        raise ValueError("Transformed columns do not match the table schema.")
    if not df["ano"].eq(year).all():
        raise ValueError(f"All records must have ano={year}.")
    for column, limit in lengths.items():
        values = df[column]
        if not values.map(lambda value: isinstance(value, str)).all():
            raise ValueError(f"Column {column} must contain non-null strings.")
        if values.str.len().gt(limit).any():
            raise ValueError(f"Values in {column} exceed {limit} characters.")
    if df.duplicated(subset=[*lengths, "ano"]).any():
        raise ValueError("Transformed records contain duplicate primary keys.")


def replace_period_data(
    df: pd.DataFrame,
    table_name: str,
    create_table_sql: str,
    year: int,
    month: int | None = None,
    *,
    engine=None,
) -> int:
    """Replace exactly one period atomically; empty input preserves stored data.

    Monthly frames and tables must include an integer or zero-padded CHAR(2)
    ``mes`` column, and
    their primary key must include both ``ano`` and ``mes``. Annual frames
    must not include ``mes``. DDL is supplied by the trusted indicator module.
    """
    validate_period(year, month)
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", table_name):
        raise ValueError("Invalid INE table name.")
    if not create_table_sql.strip():
        raise ValueError("The indicator must provide its table creation SQL.")
    if month is None and "mes" in df.columns:
        raise ValueError("Monthly data requires an explicit month.")
    periods: dict[str, int | str] = {"ano": year}
    if month is not None:
        periods["mes"] = month
        if "mes" in df.columns and not df.empty and df["mes"].map(
            lambda value: isinstance(value, str)
        ).all():
            periods["mes"] = f"{month:02d}"
    for column, expected in periods.items():
        if column not in df.columns:
            raise ValueError(f"Missing period column: {column}")
        if not df[column].eq(expected).fillna(False).all():
            raise ValueError(f"All records must have {column}={expected}.")
    if df.empty:
        logger.warning("No records for %s (%s); existing data kept.", table_name, periods)
        return 0

    own_engine = engine is None
    engine = get_engine() if own_engine else engine
    where = " AND ".join(f"{column} = :{column}" for column in periods)
    try:
        with engine.begin() as connection:
            connection.execute(text(create_table_sql))
            connection.execute(
                text(f"DELETE FROM {table_name} WHERE {where}"), periods
            )
            df.to_sql(table_name, con=connection, index=False, if_exists="append")
    except (SQLAlchemyError, pd.errors.DatabaseError) as exc:
        raise RuntimeError(
            f"Failed to replace data in {table_name} for {periods}; "
            "transaction rolled back."
        ) from exc
    finally:
        if own_engine:
            engine.dispose()
    logger.info("Replaced %d records in %s for %s.", len(df), table_name, periods)
    return len(df)
