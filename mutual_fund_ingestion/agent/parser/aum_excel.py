"""AMFI Average-AUM parsers.

Two verified sources (recon 2026-08-22):

1. **Scheme-wise AAUM** — AMFI's ``Average AUM`` page
   (https://www.amfiindia.com/aum-data/average-aum) is backed by a JSON
   API that also serves an Excel render::

       GET /api/average-aum-schemewise?strType=Typewise|Categorywise
                                    &fyId=<n>&periodId=<n>&MF_ID=<0=all>
       GET ...&excel=true   -> application/vnd.openxmlformats-...sheet

   Data are **quarterly** periods (e.g. "January - March 2026") with one
   row per scheme plan/option keyed by **AMFI scheme code**, values in
   **₹ LAKH** (the workbook title row reads "… (Rs in Lakhs)"; unit
   verified 2026-08-22 against public AMC totals — e.g. PPFAS MF total
   15,232,816 raw = ₹1.52 lakh crore, SBI Nifty 50 ETF 21,078,307 raw =
   ₹2.11 lakh crore) split across two columns:
     - "Excluding Fund of Funds - Domestic but including Fund of
        Funds - Overseas"
     - "Fund Of Funds - Domestic"
   We convert to ₹ crore (÷100) and emit ``avg_aum_cr`` as the
   **total** (sum of both columns) plus the raw components, because
   conviction weighting wants all managed money behind a holding.

   NOTE the legacy ``am{mon}{yyyy}repo.xls`` family is denominated in
   ₹ CRORE (its Liquid Fund category value ≈ ₹7.3e5 cr matches known
   industry figures), unlike these APIs — each parser handles its own
   source's unit.

2. **Legacy industry monthly workbook** — the
   ``https://portal.amfiindia.com/spages/am{mon}{yyyy}repo.xls`` family
   (.pdf twin also exists). These contain **industry-aggregate,
   category-level** rows only (Overnight Fund, Liquid Fund, ...) with
   NO AMC names and NO scheme codes. The parser emits them honestly as
   ``amc_name=None, amfi_scheme_code=None`` records flagged
   ``industry_level=True`` in result metadata; they cannot be joined to
   individual schemes and exist here for trend context only.

month_start convention: first day of the reporting period's opening
month (monthly source "July 2026" -> 2026-07-01; quarterly "January -
March 2026" -> 2026-01-01). This matches the UNIQUE (scheme_id,
month_start) idempotency key on scheme_aum_history.
"""
from __future__ import annotations

import calendar
import logging
import re
from datetime import date
from io import BytesIO
from typing import Any

import pandas as pd

from ..models import ParserResult


LOGGER = logging.getLogger(__name__)

DATASET_TYPE = "scheme_aum"
SCHEMEWISE_PARSER_NAME = "aum_excel_schemewise_v1"
INDUSTRY_PARSER_NAME = "aum_excel_industry_repo_v1"

# AMFI schemewise API (verified 2026-08-22).
AMFI_BASE_URL = "https://www.amfiindia.com"
AMFI_SCHEMEWISE_API_URL = (
    AMFI_BASE_URL
    + "/api/average-aum-schemewise?strType={str_type}&fyId={fy_id}"
      "&periodId={period_id}&MF_ID={mf_id}"
)

MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
MONTHS.update({m.lower(): i for i, m in enumerate(calendar.month_abbr) if m})

_PERIOD_RE = re.compile(
    r"^\s*([A-Za-z]+)(?:\s*[-–]\s*([A-Za-z]+))?\s+(\d{4})\s*$"
)
_MONTH_YEAR_RE = re.compile(r"for\s+the\s+month\s+of\s+([A-Za-z]+)[^0-9]*(\d{4})", re.IGNORECASE)
_TOTAL_ROW_RE = re.compile(r"\btotal\b", re.IGNORECASE)


# AMFI schemewise API values are declared "(Rs in Lakhs)" in the workbook
# title; verified against public AMC totals 2026-08-22. Convert to crore.
SCHEMEWISE_LAKH_TO_CRORE = 100.0


def period_to_month_start(label: str | None) -> str | None:
    """Map an AMFI period label to the ISO date of its opening month.

    >>> period_to_month_start("January - March 2026")
    '2026-01-01'
    >>> period_to_month_start("April - June 2025")
    '2025-04-01'
    >>> period_to_month_start("July 2026")
    '2026-07-01'
    """
    if not label:
        return None
    m = _PERIOD_RE.match(str(label))
    if not m:
        # Tolerate surrounding prose, e.g. workbook title rows like
        # "Average Assets under Management (AAUM) for January - March 2026".
        m = _PERIOD_RE.search(str(label))
    if not m:
        return None
    first_mon = MONTHS.get(m.group(1).lower())
    year = int(m.group(3))
    if not first_mon:
        return None
    return date(year, first_mon, 1).isoformat()


def _month_start_from_any_text(text: str | None) -> str | None:
    """period_to_month_start over free text (title rows, headers)."""
    if not text:
        return None
    for candidate in re.findall(r"[A-Za-z]+(?:\s*[-–]\s*[A-Za-z]+)?\s+\d{4}", text):
        iso = period_to_month_start(candidate)
        if iso:
            return iso
    return None


def _clean(value: Any) -> str:
    s = "" if value is None else str(value).strip()
    if s.lower() in ("nan", "none", "-"):
        return ""
    return " ".join(s.split())


def _to_float(value: Any) -> float | None:
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _result(
    parser_name: str,
    confidence: float,
    records: list[dict[str, Any]],
    warnings: list[str],
    errors: list[str],
    metadata: dict[str, Any],
) -> ParserResult:
    return ParserResult(
        dataset_type=DATASET_TYPE,
        parser_name=parser_name,
        parser_version="1.0",
        confidence=confidence,
        records=records,
        warnings=warnings,
        errors=errors,
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Source 1: scheme-wise AAUM (Excel render or API JSON)
# ---------------------------------------------------------------------------

def _read_excel_frame(content: bytes, file_ext: str) -> tuple[pd.DataFrame, list[str]]:
    """Read the first sheet of a workbook, sniffing engine. Returns (df, warnings)."""
    warnings: list[str] = []
    head = bytes(content[:4])
    engines = ["xlrd", "openpyxl"] if file_ext.lower() == ".xls" or head == b"\xd0\xcf\x11\xe0" else [
        "openpyxl",
        "xlrd",
    ]
    last_err: Exception | None = None
    for engine in engines:
        try:
            xl = pd.ExcelFile(BytesIO(bytes(content)), engine=engine)
            break
        except Exception as exc:  # noqa: BLE001
            last_err = exc
    else:
        raise ValueError(f"Failed to read AUM workbook: {last_err}")
    frame = xl.parse(xl.sheet_names[0], header=None)
    return frame, warnings


def _is_scheme_row(row: list[Any]) -> bool:
    """Scheme data row: integer-like AMFI code in col0, name in col1."""
    code = row[0]
    if code is None or isinstance(code, str):
        return False
    try:
        int(str(code))
    except (TypeError, ValueError):
        return False
    return bool(_clean(row[1] if len(row) > 1 else None))


def parse_amfi_schemewise_aum_excel(content: bytes, metadata: dict[str, Any]) -> ParserResult:
    """Parse the Excel render of AMFI's scheme-wise Average AUM API."""
    warnings: list[str] = []
    errors: list[str] = []
    file_ext = metadata.get("file_ext", ".xlsx")

    try:
        df, read_warnings = _read_excel_frame(content, file_ext)
        warnings.extend(read_warnings)
    except Exception as exc:  # noqa: BLE001
        return _result(
            SCHEMEWISE_PARSER_NAME, 0.0, [], warnings, [f"AUM workbook read error: {exc}"], metadata
        )

    values = df.values.tolist()
    period_label = metadata.get("period_label")
    if not period_label:
        # Title row: "Average Assets under Management (AAUM) for <period> ..."
        for row in values[:6]:
            cell = _clean(row[0] if row else None)
            if cell.lower().startswith("average assets"):
                period_label = cell
                break

    month_start = metadata.get("month_start") or _month_start_from_any_text(period_label or "")
    if not month_start:
        warnings.append(f"Could not derive month_start from period label: {period_label!r}")

    records: list[dict[str, Any]] = []
    current_amc: str | None = None
    for idx, row in enumerate(values):
        amc_candidate = _clean(row[0] if len(row) > 0 else None)
        if amc_candidate and amc_candidate.lower().endswith("mutual fund"):
            current_amc = amc_candidate
            continue
        if not _is_scheme_row(row):
            continue
        scheme_name = _clean(row[1])
        excl_fof = _to_float(row[2] if len(row) > 2 else None)
        fof_dom = _to_float(row[3] if len(row) > 3 else None)
        excl_fof = excl_fof / SCHEMEWISE_LAKH_TO_CRORE if excl_fof is not None else None
        fof_dom = fof_dom / SCHEMEWISE_LAKH_TO_CRORE if fof_dom is not None else None
        total = sum(v for v in (excl_fof, fof_dom) if v is not None) or None
        records.append(
            {
                "amc_name": current_amc,
                "scheme_name": scheme_name,
                "amfi_scheme_code": str(int(str(row[0]))),
                "avg_aum_cr": total,
                "avg_aum_excl_fof_domestic_cr": excl_fof,
                "fof_domestic_cr": fof_dom,
                "month_start": month_start,
                "period_label": period_label,
                "source_url": metadata.get("source_url", ""),
            }
        )

    matched = sum(1 for r in records if r["avg_aum_cr"] is not None and r["amc_name"])
    confidence = round(0.5 + 0.45 * (matched / len(records)), 2) if records else 0.0
    LOGGER.info(
        "schemewise AUM excel: %d records (%d fully attributed), month_start=%s",
        len(records), matched, month_start,
    )
    return _result(
        SCHEMEWISE_PARSER_NAME,
        confidence,
        records,
        warnings,
        errors,
        {
            **metadata,
            "period_label": period_label,
            "month_start": month_start,
            "industry_level": False,
        },
    )


def parse_amfi_schemewise_aum_json(payload: Any, metadata: dict[str, Any]) -> ParserResult:
    """Parse the JSON response of AMFI's scheme-wise Average AUM API.

    Shape (verified 2026-08-22)::

        {"type": "...", "data": [
           {"strMFId": "0", "Mfname": "<AMC>", "SchemeType_Desc": "Open Ended",
            "schemes": [{"SchemeNAVName": ..., "AMFI_Code": 152073,
                         "AverageAumForTheMonth": {"ExcludingFundOfFundsDomesticButIncludingFundOfFundsOverseas": 26.09,
                                                    "FundOfFundsDomestic": 0}}]}]}
    """
    warnings: list[str] = []
    errors: list[str] = []
    funds = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(funds, list):
        return _result(
            SCHEMEWISE_PARSER_NAME, 0.0, [], warnings, ["Unexpected API payload shape"], metadata
        )

    period_label = metadata.get("period_label")
    month_start = metadata.get("month_start") or period_to_month_start(period_label or "")
    if not month_start:
        warnings.append(f"Could not derive month_start from period label: {period_label!r}")

    EXCL_KEY = "ExcludingFundOfFundsDomesticButIncludingFundOfFundsOverseas"
    FOF_KEY = "FundOfFundsDomestic"

    records: list[dict[str, Any]] = []
    for fund in funds:
        amc_name = _clean(fund.get("Mfname")) or None
        for scheme in fund.get("schemes") or []:
            aum = scheme.get("AverageAumForTheMonth") or {}
            excl_fof = _to_float(aum.get(EXCL_KEY))
            fof_dom = _to_float(aum.get(FOF_KEY))
            # API figures are ₹ LAKH (workbook/API title: "Rs in Lakhs");
            # normalize to ₹ crore like the Excel path.
            excl_fof = excl_fof / SCHEMEWISE_LAKH_TO_CRORE if excl_fof is not None else None
            fof_dom = fof_dom / SCHEMEWISE_LAKH_TO_CRORE if fof_dom is not None else None
            total = sum(v for v in (excl_fof, fof_dom) if v is not None) or None
            code = scheme.get("AMFI_Code")
            records.append(
                {
                    "amc_name": amc_name,
                    "scheme_name": _clean(scheme.get("SchemeNAVName")),
                    "amfi_scheme_code": str(code) if code is not None else None,
                    "avg_aum_cr": total,
                    "avg_aum_excl_fof_domestic_cr": excl_fof,
                    "fof_domestic_cr": fof_dom,
                    "month_start": month_start,
                    "period_label": period_label,
                    "source_url": metadata.get("source_url", ""),
                }
            )

    good = sum(1 for r in records if r["amfi_scheme_code"] and r["avg_aum_cr"] is not None)
    confidence = round(0.5 + 0.45 * (good / len(records)), 2) if records else 0.0
    LOGGER.info("schemewise AUM json: %d records (%d usable)", len(records), good)
    return _result(
        SCHEMEWISE_PARSER_NAME,
        confidence,
        records,
        warnings,
        errors,
        {
            **metadata,
            "period_label": period_label,
            "month_start": month_start,
            "industry_level": False,
        },
    )


# ---------------------------------------------------------------------------
# Source 2: legacy industry monthly repo (am{mon}{yyyy}repo.xls family)
# ---------------------------------------------------------------------------

def parse_amfi_industry_aum_excel(content: bytes, metadata: dict[str, Any]) -> ParserResult:
    """Parse the industry-wide monthly AUM workbook (MCR sheet).

    HONEST LIMITATION: these workbooks carry industry aggregates per
    scheme CATEGORY (Overnight Fund, Liquid Fund, ...) — no AMC column,
    no scheme codes. Records therefore have amc_name=None /
    amfi_scheme_code=None and cannot be resolved against schemes; the
    backfill must skip them. They document what IS available from this
    source family without pretending it is per-scheme data.
    """
    warnings: list[str] = []
    errors: list[str] = []
    file_ext = metadata.get("file_ext", ".xls")

    try:
        xl_frame, read_warnings = _read_excel_frame(content, file_ext)
        warnings.extend(read_warnings)
    except Exception as exc:  # noqa: BLE001
        return _result(
            INDUSTRY_PARSER_NAME, 0.0, [], warnings, [f"AUM workbook read error: {exc}"], metadata
        )

    # Prefer the MCR sheet; fall back to whatever we got.
    values = xl_frame.values.tolist()

    month_start = metadata.get("month_start")
    period_label = metadata.get("period_label")
    if not month_start:
        for row in values[:8]:
            cell = _clean(row[0] if row else None)
            m = _MONTH_YEAR_RE.search(cell)
            if m:
                mon = MONTHS.get(m.group(1).lower())
                if mon:
                    year = int(m.group(2))
                    month_start = date(year, mon, 1).isoformat()
                    period_label = f"{m.group(1).title()} {year}"
                    break

    # Find the header row to locate the "Average Net Assets Under Management" column.
    avg_col = 8  # observed default in am{mon}{yyyy}repo.xls MCR sheets
    for row in values[:12]:
        for j, cell in enumerate(row):
            if _clean(cell).lower().startswith("average net assets under management"):
                avg_col = j
                break

    records: list[dict[str, Any]] = []
    for row in values:
        name = _clean(row[1] if len(row) > 1 else None)
        if not name or _TOTAL_ROW_RE.search(name):
            continue
        avg = _to_float(row[avg_col] if len(row) > avg_col else None)
        if avg is None or avg <= 0:
            continue
        records.append(
            {
                "amc_name": None,
                "scheme_name": name,
                "amfi_scheme_code": None,
                "avg_aum_cr": avg,
                "avg_aum_excl_fof_domestic_cr": None,
                "fof_domestic_cr": None,
                "month_start": month_start,
                "period_label": period_label,
                "source_url": metadata.get("source_url", ""),
            }
        )

    confidence = 0.75 if records else 0.0
    LOGGER.info("industry AUM excel: %d category rows, month_start=%s", len(records), month_start)
    meta = {
        **metadata,
        "period_label": period_label,
        "month_start": month_start,
        "industry_level": True,
        "note": (
            "Industry aggregate by scheme category only; no AMC/scheme codes "
            "exist in this source family."
        ),
    }
    return _result(INDUSTRY_PARSER_NAME, confidence, records, warnings, errors, meta)


def parse_amfi_aum_excel(content: bytes, metadata: dict[str, Any]) -> ParserResult:
    """Router: detect which AMFI AUM workbook family this is and parse it."""
    head = bytes(content[:4])
    file_ext = metadata.get("file_ext", "")
    try:
        df_probe, _ = _read_excel_frame(content, file_ext or (".xls" if head == b"\xd0\xcf\x11\xe0" else ".xlsx"))
    except Exception as exc:  # noqa: BLE001
        return _result(SCHEMEWISE_PARSER_NAME, 0.0, [], [], [f"AUM workbook read error: {exc}"], metadata)

    flat = [" ".join(str(c).lower().split()) for c in df_probe.values.ravel()[:400]]
    if any(c.startswith("average assets under management") for c in flat):
        return parse_amfi_schemewise_aum_excel(content, metadata)
    if any("monthly report for the month" in c or c.startswith("sr") for c in flat[:60]):
        return parse_amfi_industry_aum_excel(content, metadata)
    # Default: assume schemewise (it degrades gracefully with 0 records + warning).
    result = parse_amfi_schemewise_aum_excel(content, metadata)
    result.metadata.setdefault(
        "router_note", "Workbook family not recognized; tried schemewise parser."
    )
    return result
