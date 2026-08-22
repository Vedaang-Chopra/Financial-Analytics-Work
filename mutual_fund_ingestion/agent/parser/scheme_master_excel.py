"""AMFI Scheme Master Excel/CSV parser.

Handles the AMFI scheme master downloads:
- ``DownloadSchemeData_Po.aspx`` CSV snapshot (AMC, Code, Scheme Name,
  Scheme Type, Scheme Category, Scheme Minimum Amount, Launch Date,
  Closure Date, ISIN columns) — the canonical per-scheme category source.
- Generic scheme-master workbooks (.xlsx/.xls) whose sheets carry
  scheme_code / scheme_name / amc / category style headers.

Complements ``scheme_master.py`` (CSV/HTML variants); this module sniffs
content type so it can also serve as the Excel router target.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from io import BytesIO, StringIO
from typing import Any

import pandas as pd

from ..models import ParserResult


LOGGER = logging.getLogger(__name__)

# Column aliases: real AMFI SchemeData headers + generic variants.
SCHEME_MASTER_EXCEL_COLUMN_ALIASES = {
    "scheme_code": [
        "code", "scheme code", "schemecode", "scheme_code", "scheme code ",
    ],
    "scheme_name": ["scheme name", "schemename", "scheme_name", "name"],
    "amc_name": [
        "amc", "amc name", "mutual fund", "fund house", "amc_name",
    ],
    "category": [
        "scheme category", "category", "fund category", "scheme_category",
        "fundcategory",
    ],
    "sub_category": [
        "scheme type", "sub category", "subcategory", "sub-category",
        "sub_category", "type",
    ],
    "nav_name": ["scheme nav name", "nav name"],
    "benchmark": ["benchmark", "benchmark index"],
    "launch_date": ["launch date", "launch_date", "date of launch", "launch date "],
    "closure_date": ["closure date", "closure_date", " closure date"],
    "minimum_amount": ["scheme minimum amount", "minimum amount", "min amount"],
    "isin_div_payout": [
        "isin div payout/ isin growthisin div reinvestment",
        "isin div payout/ isin growth",
        "isin growth",
        "isin div payout",
        "isin div payout/ isin growthisin div reinvestment ",
    ],
}

PLAN_OPTION_RE = re.compile(
    r"\b(direct|regular)\b.*?\b(growth|idcw|dividend|payout|reinvestment)\b",
    re.IGNORECASE,
)
OPTION_ONLY_RE = re.compile(r"\b(growth|idcw|dividend|payout|reinvestment)\b", re.IGNORECASE)

DATE_FORMATS = ["%d-%b-%Y", "%d-%b-%y", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"]


def _normalize_col(col: str) -> str:
    """Normalize a header cell: collapse whitespace/newlines, lower-case."""
    return " ".join(str(col).replace("\n", " ").split()).strip().lower()


def _map_scheme_master_columns(df: pd.DataFrame) -> dict[str, str]:
    """Map dataframe columns -> standard field names (portfolio.py style)."""
    col_map: dict[str, str] = {}
    for col in df.columns:
        norm = _normalize_col(str(col))
        mapped = col  # default: keep normalized original
        for target, aliases in SCHEME_MASTER_EXCEL_COLUMN_ALIASES.items():
            if norm in [a.lower() for a in aliases]:
                mapped = target
                break
        else:
            mapped = norm.replace(" ", "_")
        col_map[col] = mapped
    return col_map


def _parse_date(val: Any) -> str | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    # openpyxl may hand back datetime/date objects
    if isinstance(val, (datetime, pd.Timestamp)):
        return val.date().isoformat()
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    s = str(val).strip()
    if not s or s.lower() == "nan":
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _split_plan_option(nav_name: str | None, scheme_name: str) -> tuple[str | None, str | None]:
    """Split plan (Regular/Direct) and option (Growth/IDCW) from a NAV name."""
    text = nav_name or scheme_name or ""
    plan = option = None
    m = PLAN_OPTION_RE.search(text)
    if m:
        plan = m.group(1).title()
        opt = m.group(2).upper()
        option = "IDCW" if opt in ("DIVIDEND", "PAYOUT", "REINVESTMENT") else opt.title()
    else:
        mp = re.search(r"\b(direct|regular)\b", text, re.IGNORECASE)
        if mp:
            plan = mp.group(1).title()
        mo = OPTION_ONLY_RE.search(text)
        if mo:
            o = mo.group(1).upper()
            option = "IDCW" if o in ("DIVIDEND", "PAYOUT", "REINVESTMENT") else o.title()
    return plan, option


def _read_scheme_master_frame(content: bytes | str, file_ext: str) -> tuple[pd.DataFrame, list[str]]:
    """Return (combined_df, warnings). Sniffs CSV vs Excel content."""
    warnings: list[str] = []
    is_bytes = isinstance(content, (bytes, bytearray))
    head = bytes(content[:4]) if is_bytes else b""

    # CSV / text content?
    looks_like_csv = (
        (not is_bytes)
        or head.startswith((b"AMC,", b"Scheme", b'"'))
        or (head[:1].isalpha() and b"," in bytes(content[:200]))
    )
    if looks_like_csv:
        text = content.decode("utf-8", errors="replace") if is_bytes else content
        df = pd.read_csv(StringIO(text), dtype=str, keep_default_na=False)
        return df, warnings

    # Excel: try openpyxl (xlsx), then xlrd (legacy .xls), concatenating all sheets
    frames: list[pd.DataFrame] = []
    sheet_names: list[str] = []
    engines = []
    if file_ext.lower() in (".xls",) or head[:4] == b"\xd0\xcf\x11\xe0":
        engines = ["xlrd", "openpyxl"]
    else:
        engines = ["openpyxl", "xlrd"]
    xl = None
    last_err: Exception | None = None
    for engine in engines:
        try:
            xl = pd.ExcelFile(BytesIO(bytes(content)), engine=engine)
            break
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            xl = None
    if xl is None:
        raise ValueError(f"Failed to read scheme master workbook: {last_err}")
    for sheet_name in xl.sheet_names:
        try:
            frame = xl.parse(sheet_name, dtype=str)
            if frame.empty:
                continue
            frame.attrs["sheet_name"] = sheet_name
            frames.append(frame)
            sheet_names.append(sheet_name)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Sheet {sheet_name}: {exc}")
    if not frames:
        raise ValueError("No parseable sheets in scheme master workbook")
    if len(frames) > 1:
        warnings.append(f"multi-sheet workbook: parsed sheets {sheet_names}")
        combined = pd.concat(frames, ignore_index=True, sort=False)
    else:
        combined = frames[0]
    return combined, warnings


def _clean(value: Any) -> str:
    s = "" if value is None else str(value).strip()
    if s.lower() in ("nan", "none", "-"):
        return ""
    return " ".join(s.split())


def parse_scheme_master_excel(content: bytes | str, metadata: dict[str, Any]) -> ParserResult:
    """Parse an AMFI scheme master workbook or CSV into scheme records."""
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    warnings: list[str] = []
    file_ext = metadata.get("file_ext", ".xlsx")

    try:
        df, sniff_warnings = _read_scheme_master_frame(content, file_ext)
        warnings.extend(sniff_warnings)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"Scheme master parse error: {exc}")
        return ParserResult(
            dataset_type="scheme_master",
            parser_name="scheme_master_excel_v1",
            parser_version="1.0",
            confidence=0.0,
            records=[],
            warnings=warnings,
            errors=errors,
            metadata=metadata,
        )

    col_map = _map_scheme_master_columns(df)

    def _col(target: str):
        return next((k for k, v in col_map.items() if v == target), None)

    code_col = _col("scheme_code")
    name_col = _col("scheme_name")
    amc_col = _col("amc_name")
    cat_col = _col("category")
    sub_col = _col("sub_category")
    nav_col = _col("nav_name")
    launch_col = _col("launch_date")
    closure_col = _col("closure_date")
    isin_col = _col("isin_div_payout")

    if name_col is None:
        errors.append("No scheme_name column detected in scheme master")
        return ParserResult(
            dataset_type="scheme_master",
            parser_name="scheme_master_excel_v1",
            parser_version="1.0",
            confidence=0.0,
            records=[],
            warnings=warnings,
            errors=errors,
            metadata=metadata,
        )

    seen_codes: set[str] = set()
    for idx, row in df.iterrows():
        try:
            scheme_code = _clean(row.get(code_col)) if code_col is not None else ""
            scheme_name = _clean(row.get(name_col))
            if not scheme_name:
                continue
            amc_name = _clean(row.get(amc_col)) if amc_col is not None else ""
            category = _clean(row.get(cat_col)) if cat_col is not None else ""
            sub_category = _clean(row.get(sub_col)) if sub_col is not None else ""
            nav_name = _clean(row.get(nav_col)) if nav_col is not None else ""
            launch_date = _parse_date(row.get(launch_col)) if launch_col is not None else None
            closure_date = _parse_date(row.get(closure_col)) if closure_col is not None else None

            plan, option = _split_plan_option(nav_name, scheme_name)

            record: dict[str, Any] = {
                "scheme_code": scheme_code or None,
                "scheme_name": scheme_name,
                "amc_name": amc_name or None,
                "plan": plan,
                "option": option,
                "category": category or None,
                "sub_category": sub_category or None,
                "scheme_type": sub_category or None,
                "launch_date": launch_date,
                "source_url": metadata.get("source_url", ""),
            }
            if closure_date:
                record["closure_date"] = closure_date
            if isin_col is not None:
                isins_raw = _clean(row.get(isin_col))
                if isins_raw and len(isins_raw) >= 12:
                    found = re.findall(r"[A-Z]{2}[A-Z0-9]{9}\d", isins_raw.upper())
                    if len(found) >= 1:
                        record["isin_div_payout"] = found[0]
                    if len(found) >= 2:
                        record["isin_div_reinvestment"] = found[1]
            records.append(record)
            if scheme_code:
                seen_codes.add(scheme_code)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Row {idx}: {exc}")

    categorized = sum(1 for r in records if r.get("category"))
    extraction_rate = (categorized / len(records)) if records else 0.0
    confidence = round(0.6 + 0.35 * min(extraction_rate, 1.0), 2) if records else 0.0
    LOGGER.info(
        "scheme_master_excel: %d records (%d unique codes), category rate %.2f",
        len(records), len(seen_codes), extraction_rate,
    )

    return ParserResult(
        dataset_type="scheme_master",
        parser_name="scheme_master_excel_v1",
        parser_version="1.0",
        confidence=confidence,
        records=records,
        warnings=warnings,
        errors=errors,
        metadata={**metadata, "category_extraction_rate": extraction_rate},
    )
