"""AMFI NAV text/CSV parser."""
from __future__ import annotations

import re
from datetime import datetime
from io import StringIO
from typing import Any

import pandas as pd

from ..models import ParserResult


def parse_nav_text(content: bytes | str, metadata: dict[str, Any]) -> ParserResult:
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")
    records = []
    errors = []
    lines = content.strip().split("\n")
    for i, line in enumerate(lines):
        line = line.strip()
        if not line or line.startswith("#") or "Scheme Code" in line or "NAV Date" in line:
            continue
        parts = re.split(r"[\t,|]+", line)
        if len(parts) < 3:
            errors.append("Line %d: insufficient columns: %s" % (i, line))
            continue
        scheme_code = parts[0].strip()
        nav_date_str = parts[1].strip() if len(parts) > 1 else ""
        nav_value_str = parts[2].strip() if len(parts) > 2 else ""
        if not scheme_code or not nav_value_str:
            continue
        try:
            nav_value = float(nav_value_str.replace(",", "").replace(" ", ""))
        except ValueError:
            errors.append("Line %d: invalid NAV value: %s" % (i, nav_value_str))
            continue
        try:
            nav_date = datetime.strptime(nav_date_str, "%d-%b-%Y").date()
        except ValueError:
            try:
                nav_date = datetime.strptime(nav_date_str, "%Y-%m-%d").date()
            except ValueError:
                errors.append("Line %d: invalid date: %s" % (i, nav_date_str))
                continue
        records.append({
            "scheme_code": scheme_code,
            "nav_date": nav_date.isoformat(),
            "nav_value": nav_value,
            "source_url": metadata.get("source_url", ""),
        })
    return ParserResult(
        dataset_type="nav_history",
        parser_name="nav_text_v1",
        parser_version="1.0",
        confidence=0.85 if records else 0.0,
        records=records,
        warnings=[],
        errors=errors,
        metadata=metadata,
    )


def parse_nav_csv(content: bytes | str, metadata: dict[str, Any]) -> ParserResult:
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")
    records = []
    errors = []
    try:
        df = pd.read_csv(StringIO(content))
        for _, row in df.iterrows():
            scheme_code = str(row.get("Scheme Code", "") or row.get("scheme_code", "") or row.get("scheme code", "")).strip()
            nav_date_str = str(row.get("NAV Date", "") or row.get("nav_date", "") or row.get("Date", "")).strip()
            nav_value_str = str(row.get("NAV", "") or row.get("nav", "") or row.get("NAV Value", "")).strip()
            if not scheme_code or not nav_value_str or nav_value_str == "nan":
                continue
            try:
                nav_value = float(nav_value_str.replace(",", "").replace(" ", ""))
                nav_date = pd.to_datetime(nav_date_str).date()
                records.append({
                    "scheme_code": scheme_code,
                    "nav_date": nav_date.isoformat(),
                    "nav_value": nav_value,
                    "source_url": metadata.get("source_url", ""),
                })
            except (ValueError, TypeError) as exc:
                errors.append("Row %s: %s" % (str(row), str(exc)))
    except Exception as exc:
        errors.append("CSV parse error: %s" % exc)
    return ParserResult(
        dataset_type="nav_history",
        parser_name="nav_csv_v1",
        parser_version="1.0",
        confidence=0.9 if records else 0.0,
        records=records,
        warnings=[],
        errors=errors,
        metadata=metadata,
    )