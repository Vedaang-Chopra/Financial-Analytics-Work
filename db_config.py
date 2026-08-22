"""Database DSN resolution for all ingestion/backfill tooling.

Resolution order (per database):
1. Explicit environment variable (``MF_DATABASE_URL`` / ``SCREENER_DATABASE_URL``
   / ``DATABASE_URL``)
2. ``api.env`` in the repo root (gitignored; ``KEY=value`` lines, ``#`` comments)
3. Hardcoded local Docker default (dev convenience only)

New code must import from here instead of embedding connection strings.
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_API_ENV_PATH = REPO_ROOT / "api.env"

_MF_DEFAULT = "postgresql://vlmrouter:vlmrouter@localhost:5432/mutual_funds"
_SCREENER_DEFAULT = "postgresql://vlmrouter:vlmrouter@localhost:5432/screener"

_env_cache: dict[str, str] | None = None


def _load_api_env() -> dict[str, str]:
    """Parse api.env once (no python-dotenv dependency)."""
    global _env_cache
    if _env_cache is not None:
        return _env_cache
    parsed: dict[str, str] = {}
    try:
        text = _API_ENV_PATH.read_text()
    except OSError:
        text = ""
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        parsed[key.strip()] = value.strip().strip("'\"")
    _env_cache = parsed
    return parsed


def db_url(env_var: str, default: str) -> str:
    """Resolve a database URL: environment variable > api.env > default."""
    return os.environ.get(env_var) or _load_api_env().get(env_var) or default


def mutual_funds_url() -> str:
    """DSN for the ``mutual_funds`` PostgreSQL database."""
    return db_url("MF_DATABASE_URL", _MF_DEFAULT)


def screener_url() -> str:
    """DSN for the ``screener`` PostgreSQL database."""
    return db_url("SCREENER_DATABASE_URL", _SCREENER_DEFAULT)


def generic_database_url() -> str:
    """DSN honouring the generic ``DATABASE_URL`` convention."""
    return db_url("DATABASE_URL", _MF_DEFAULT)
