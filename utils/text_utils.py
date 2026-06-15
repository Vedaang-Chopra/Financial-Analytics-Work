"""Shared text and string utilities."""
from __future__ import annotations

import re


def normalize_amc_name(value: str) -> str:
    suffixes = re.compile(r"\b(mutual\s+fund|mf|asset\s+management(?:\s+company)?|amc)\b", re.IGNORECASE)
    normalized = suffixes.sub(" ", value.casefold())
    return re.sub(r"[^a-z0-9]+", " ", normalized).strip()
