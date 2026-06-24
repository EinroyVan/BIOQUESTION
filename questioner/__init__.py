"""Natural-science literature learning workflow: extract → quiz → grade."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

__version__ = "1.3.2"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
load_dotenv(ENV_FILE, override=False)


def load_project_env() -> Path:
    """Load .env from project root regardless of current working directory."""
    load_dotenv(ENV_FILE, override=False)
    return ENV_FILE
