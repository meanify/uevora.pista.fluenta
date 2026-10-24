"""Environment configuration helpers for command-line entry points."""

from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_project_environment():
    """Load optional settings without replacing existing environment values."""
    for dotenv_path in (PROJECT_ROOT.parent / ".env", PROJECT_ROOT / ".env"):
        load_dotenv(dotenv_path=dotenv_path, override=False)
