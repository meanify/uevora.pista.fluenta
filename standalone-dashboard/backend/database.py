"""Database connection for the dashboards, independent of the flows package."""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import URL, create_engine


APP_DIR = Path(__file__).resolve().parent.parent
SETTINGS = (
    "PISTA_DB_HOSTNAME", "PISTA_DB_PORTNUMBER", "PISTA_DB_NAME",
    "PISTA_DB_USERNAME", "PISTA_DB_PASSWORD",
)


def load_environment():
    """Load .env from standalone-dashboard, then from the workspace root.

    Existing environment variables and earlier files take precedence.
    """
    for directory in (APP_DIR, APP_DIR.parent):
        load_dotenv(dotenv_path=directory / ".env", override=False)


def get_engine():
    """Create a read engine from the PISTA_DB_* variables."""
    settings = {name: os.getenv(name, "") for name in SETTINGS}
    missing = [name for name, value in settings.items() if not value]
    if missing:
        raise RuntimeError("Missing database settings: " + ", ".join(missing))
    try:
        port = int(settings["PISTA_DB_PORTNUMBER"])
    except ValueError as exc:
        raise ValueError("PISTA_DB_PORTNUMBER must be an integer.") from exc
    return create_engine(URL.create(
        "postgresql+psycopg2",
        username=settings["PISTA_DB_USERNAME"],
        password=settings["PISTA_DB_PASSWORD"],
        host=settings["PISTA_DB_HOSTNAME"],
        port=port,
        database=settings["PISTA_DB_NAME"],
    ))
