"""PostgreSQL connection configuration shared by flow families."""

import os

from sqlalchemy import URL, create_engine


def get_engine():
    """Read credentials at call time, including in Airflow workers."""
    names = (
        "PISTA_DB_HOSTNAME", "PISTA_DB_PORTNUMBER", "PISTA_DB_NAME",
        "PISTA_DB_USERNAME", "PISTA_DB_PASSWORD",
    )
    settings = {name: os.getenv(name, "") for name in names}
    missing = [name for name, value in settings.items() if not value]
    if missing:
        raise RuntimeError("Missing database settings: " + ", ".join(missing))
    try:
        port = int(settings["PISTA_DB_PORTNUMBER"])
    except ValueError as exc:
        raise ValueError("PISTA_DB_PORTNUMBER must be an integer.") from exc
    if not 1 <= port <= 65535:
        raise ValueError("PISTA_DB_PORTNUMBER must be between 1 and 65535.")
    return create_engine(URL.create(
        "postgresql+psycopg2",
        username=settings["PISTA_DB_USERNAME"],
        password=settings["PISTA_DB_PASSWORD"],
        host=settings["PISTA_DB_HOSTNAME"],
        port=port,
        database=settings["PISTA_DB_NAME"],
    ))
