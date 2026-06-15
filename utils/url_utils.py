"""Shared URL and filename utilities."""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse, urlunparse


FILE_EXTENSIONS = {"pdf", "xls", "xlsx", "csv", "zip"}


def canonical_url(value: str) -> str:
    parsed = urlparse(value)
    return urlunparse(
        (parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, "", parsed.query, "")
    )


def file_type_from_url(value: str) -> str | None:
    suffix = Path(unquote(urlparse(value).path)).suffix.lower().lstrip(".")
    return suffix if suffix in FILE_EXTENSIONS else None


def safe_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_") or "unknown"


def slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value or "unknown"
