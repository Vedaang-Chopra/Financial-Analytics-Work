"""Shared DB connection helpers for scripts/.

Restored 2026-08-22: several analysis/backfill scripts import
``mutual_funds_url`` from this module; the original file was lost during
scratch cleanup. DSN default matches the project's local Docker postgres.
"""

from __future__ import annotations

import os


def mutual_funds_url() -> str:
    """DSN for the mutual_funds database (env override: MUTUAL_FUNDS_URL)."""
    return os.environ.get(
        "MUTUAL_FUNDS_URL",
        "postgresql://vlmrouter:vlmrouter@localhost:5432/mutual_funds",
    )


def screener_url() -> str:
    """DSN for the screener database (env override: SCREENER_URL)."""
    return os.environ.get(
        "SCREENER_URL",
        "postgresql://vlmrouter:vlmrouter@localhost:5432/screener",
    )
