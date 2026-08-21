"""AMFI NAV text/CSV parser."""
from __future__ import annotations

import re
from datetime import datetime
from io import StringIO
from typing import Any

import pandas as pd

from lxml import html as lhtml
from ..models import ParserResult


def _parse_amfi_semicolon(
    lines: list[str],
    data_start_idx: int,
    metadata: dict[str, Any],
) -> ParserResult:
    """Parse AMFI semicolon NAV formats (both current and historical layouts).

    Layout A — NAVAll.txt / NAVOpen/Close/Interval.txt (current snapshot):
        Scheme Code;ISIN Div Payout;ISIN Div Reinvestment;Scheme Name;Plan;Option;Net Asset Value;Date
        (scheme name at column 3)

    Layout B — DownloadNAVHistoryReport_Po.aspx (historical, 90-day windows):
        Scheme Code;NAV Name;Plan;Option;ISIN Div Payout;ISIN Div Reinvestment;Net Asset Value;Date
        (scheme name at column 1)

    Both share scheme_code at 0 and nav_value/date at 6/7. IMPORTANT: split on
    ';' only — never on tab/comma. AMFI data rows contain embedded tabs
    (e.g. "Growth Option\\t") and commas inside scheme names, and empty
    Plan/Option fields (";;") must be preserved as empty columns. Using a
    collapsing split such as re.split(r"[\\t,|;]+", ...) silently dropped ~6,000
    of 14,282 real rows (all rows with an empty Plan field).

    Section headers ("Open Ended Schemes(...)") and AMC name rows are skipped.
    """
    records: list[dict[str, Any]] = []
    errors: list[str] = []

    for i, line in enumerate(lines):
        if i < data_start_idx:
            continue
        parts = line.strip().split(";")
        if len(parts) < 8 or not parts[0].strip().isdigit():
            continue  # section header, AMC name row, blank line
        if len(parts) > 8:
            # Scheme names must never contain ';', so >8 means a malformed row;
            # keep it out of canonical rather than guessing column shifts.
            errors.append("Line %d: expected 8 columns, got %d" % (i, len(parts)))
            continue

        scheme_code = parts[0].strip()
        col1 = parts[1].strip()
        col2 = parts[2].strip()
        col3 = parts[3].strip()
        col4 = parts[4].strip()
        col5 = parts[5].strip()
        nav_value_str = parts[6].strip()
        nav_date_str = parts[7].strip()

        # Distinguish layout A vs B by inspecting the middle columns:
        # layout A has an ISIN-looking value in column 1 (or '-' followed by an
        # ISIN in column 2), while layout B carries the scheme NAME in column 1.
        col1_is_isin = bool(re.match(r"^INF[0-9A-Z]{9}$", col1))
        col2_is_isin = bool(re.match(r"^INF[0-9A-Z]{9}$", col2))
        layout_b = not (col1_is_isin or (col1 in ("", "-") and col2_is_isin))
        if not layout_b:
            isin_div_payout, isin_div_reinvestment = col1, col2
            scheme_name, plan, option = col3, col4, col5
        else:
            scheme_name, plan, option = col1, col2, col3
            isin_div_payout, isin_div_reinvestment = col4, col5

        if not nav_value_str or not nav_date_str:
            continue
        try:
            nav_value = float(nav_value_str.replace(",", "").replace(" ", ""))
        except ValueError:
            errors.append("Line %d: invalid NAV value: %s" % (i, nav_value_str))
            continue
        try:
            try:
                nav_date = datetime.strptime(nav_date_str, "%d-%b-%Y").date()
            except ValueError:
                nav_date = datetime.strptime(nav_date_str, "%Y-%m-%d").date()
        except ValueError:
            errors.append("Line %d: invalid date: %s" % (i, nav_date_str))
            continue

        records.append({
            "scheme_code": scheme_code,
            "nav_date": nav_date.isoformat(),
            "nav_value": nav_value,
            "isin_div_payout": isin_div_payout if isin_div_payout not in ("", "-") else None,
            "isin_div_reinvestment": isin_div_reinvestment if isin_div_reinvestment not in ("", "-") else None,
            "scheme_name": scheme_name if scheme_name else None,
            "plan": plan if plan else None,
            "option": option if option else None,
            "source_url": metadata.get("source_url", ""),
        })

    return ParserResult(
        dataset_type="nav_history",
        parser_name="nav_text_v1",
        parser_version="1.2",
        confidence=0.95 if records else 0.0,
        records=records,
        warnings=[],
        errors=errors,
        metadata=metadata,
    )


def parse_nav_text(content: bytes | str, metadata: dict[str, Any]) -> ParserResult:
    """Parse NAV data from AMFI text format.

    Supports multiple formats:
    1. Full AMFI NAVAll.txt (8 semicolon columns) — detected by header line
    2. Simplified format (3+ columns): Scheme Code\\tNAV Date\\tNAV
    3. Other delimited formats with scheme_code, nav_date, nav_value columns
    """
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")
    records = []
    errors = []
    lines = content.strip().split("\n")

    # Detect the canonical AMFI semicolon format first (NAVAll.txt layout).
    amfi_header_prefixes = (
        "Scheme Code;",
        "Scheme Code\t",
    )
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(amfi_header_prefixes) and len(stripped.split(";")) == 8:
            return _parse_amfi_semicolon(lines, idx + 1, metadata)

    # Non-AMFI formats: detect header format to understand column positions
    header_info = None
    for i, line in enumerate(lines):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Check if this is a header line
        if any(keyword in line.lower() for keyword in ["scheme code", "nav date", "net asset value", "scheme_code", "nav_date"]):
            parts = re.split(r"[\t,|;]+", line)
            # Map column names to indices
            col_map = {}
            for col_idx, col in enumerate(parts):
                col_lower = col.strip().lower()
                if "scheme" in col_lower and "code" in col_lower:
                    col_map["scheme_code"] = col_idx
                elif "nav" in col_lower and "date" in col_lower:
                    col_map["nav_date"] = col_idx
                elif "net asset value" in col_lower or col_lower == "nav" or col_lower == "nav value":
                    col_map["nav_value"] = col_idx
            if len(col_map) >= 3:
                header_info = col_map
            continue
        break

    # If no clear header, try to infer from first data line
    data_start_idx = 0
    if header_info is None:
        # Look for first line that looks like data (has numeric NAV and date)
        for i, line in enumerate(lines):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = re.split(r"[\t,|;]+", line)
            if len(parts) >= 3:
                # Check if parts[1] looks like a date and parts[2] looks like a number
                try:
                    float(parts[2].replace(",", "").replace(" ", ""))
                    # Check if parts[1] is date-like
                    datetime.strptime(parts[1].strip(), "%d-%b-%Y")
                    header_info = {"scheme_code": 0, "nav_date": 1, "nav_value": 2}
                    data_start_idx = i
                    break
                except (ValueError, IndexError):
                    continue
            try:
                float(parts[6].replace(",", "").replace(" ", ""))
                datetime.strptime(parts[7].strip(), "%d-%b-%Y")
                header_info = {"scheme_code": 0, "nav_date": 7, "nav_value": 6}
                data_start_idx = i
                break
            except (ValueError, IndexError):
                continue

    if header_info is None:
        errors.append("Could not detect NAV text format")
        return ParserResult(
            dataset_type="nav_history",
            parser_name="nav_text_v1",
            parser_version="1.1",
            confidence=0.0,
            records=[],
            warnings=[],
            errors=errors,
            metadata=metadata,
        )

    # Add optional column indices for full AMFI format
    isin_payout_idx = header_info.get("isin_div_payout", 1)
    isin_reinv_idx = header_info.get("isin_div_reinvestment", 2)
    scheme_name_idx = header_info.get("scheme_name", 3)
    plan_idx = header_info.get("plan", 4)
    option_idx = header_info.get("option", 5)

    for i, line in enumerate(lines):
        if i < data_start_idx:
            continue
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = re.split(r"[\t,|;]+", line)

        scheme_code_idx = header_info.get("scheme_code", 0)
        nav_date_idx = header_info.get("nav_date", 1)
        nav_value_idx = header_info.get("nav_value", 2)

        if len(parts) <= max(scheme_code_idx, nav_date_idx, nav_value_idx):
            errors.append("Line %d: insufficient columns for detected format: %s" % (i, line))
            continue

        scheme_code = parts[scheme_code_idx].strip()
        nav_date_str = parts[nav_date_idx].strip()
        nav_value_str = parts[nav_value_idx].strip()

        # Extract optional fields if available
        isin_div_payout = parts[isin_payout_idx].strip() if len(parts) > isin_payout_idx else ""
        isin_div_reinvestment = parts[isin_reinv_idx].strip() if len(parts) > isin_reinv_idx else ""
        scheme_name = parts[scheme_name_idx].strip() if len(parts) > scheme_name_idx else ""
        plan = parts[plan_idx].strip() if len(parts) > plan_idx else ""
        option = parts[option_idx].strip() if len(parts) > option_idx else ""

        if not scheme_code or not nav_value_str or not nav_date_str:
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
                try:
                    nav_date = datetime.strptime(nav_date_str, "%d/%m/%Y").date()
                except ValueError:
                    errors.append("Line %d: invalid date: %s" % (i, nav_date_str))
                    continue
        records.append({
            "scheme_code": scheme_code,
            "nav_date": nav_date.isoformat(),
            "nav_value": nav_value,
            "isin_div_payout": isin_div_payout if isin_div_payout else None,
            "isin_div_reinvestment": isin_div_reinvestment if isin_div_reinvestment else None,
            "scheme_name": scheme_name if scheme_name else None,
            "plan": plan if plan else None,
            "option": option if option else None,
            "source_url": metadata.get("source_url", ""),
        })
    return ParserResult(
        dataset_type="nav_history",
        parser_name="nav_text_v1",
        parser_version="1.1",
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

def parse_nav_html(content: bytes | str, metadata: dict[str, Any]) -> ParserResult:
    """Parse NAV data from an HTML table."""
    records = []
    errors = []
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")
    try:
        doc = lhtml.fromstring(content)
        for table in doc.cssselect("table"):
            headers = [th.text_content().strip().lower() for th in table.cssselect("tr:first-child th, tr:first-child td")]
            for row in table.cssselect("tr")[1:]:
                cells = [td.text_content().strip() for td in row.cssselect("td")]
                if len(cells) < 3:
                    continue
                record = {}
                for i, header in enumerate(headers):
                    if "scheme code" in header or "code" == header:
                        record["scheme_code"] = cells[i] if i < len(cells) else None
                    elif "nav" in header:
                        try:
                            record["nav_value"] = float(cells[i].replace(",", ""))
                        except (ValueError, IndexError):
                            pass
                    elif "date" in header:
                        record["nav_date"] = cells[i] if i < len(cells) else None
                    elif "scheme name" in header or "name" in header:
                        record["scheme_name"] = cells[i] if i < len(cells) else None
                if record.get("scheme_code") and record.get("nav_value"):
                    record.setdefault("source_url", metadata.get("source_url", ""))
                    records.append(record)
    except Exception as exc:
        errors.append(f"HTML NAV parse error: {exc}")
    return ParserResult(
        dataset_type="nav_history",
        parser_name="nav_html_v1",
        parser_version="1.0",
        confidence=0.7 if records else 0.0,
        records=records, warnings=[], errors=errors, metadata=metadata,
    )
