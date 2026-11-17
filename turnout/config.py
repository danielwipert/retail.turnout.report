"""Paths and settings. Secrets come from environment variables or a local `.env` file."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
UNIVERSE_PATH = DATA_DIR / "universe.json"

load_dotenv(REPO_ROOT / ".env")


class ConfigError(RuntimeError):
    """Raised when a required setting is missing."""


def sec_user_agent() -> str:
    """The SEC requires every script to identify itself with a name and email."""
    value = os.environ.get("SEC_USER_AGENT", "").strip().strip('"')
    if not value or "@" not in value or "example.com" in value:
        raise ConfigError(
            "SEC_USER_AGENT is not set. Copy .env.example to .env and put your "
            'name and email in it, e.g. SEC_USER_AGENT="Dan Wipert dan@yourmail.com".'
        )
    return value
