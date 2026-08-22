"""AMFI monthly portfolio disclosure parser.

Handles both layout families observed in ``data/datasets/Monthly Reports October 2024/``:

1. Multi-sheet-per-scheme workbooks (NIMF / ABSL / 360ONE / Axis / PPFAAS /
   Bank of India / Motilal Oswal / quant style):
   one sheet per scheme, optional ``Index`` sheet mapping sheet code -> full
   scheme name, header row located by known column aliases, optional leading
   per-row "code" column that shifts data cells relative to the header.
2. Per-scheme files in a directory (ICICI Prudential style): one single-sheet
   workbook per scheme; use :func:`parse_portfolio_monthly_amfi_directory`.

AMC is detected from metadata, filename tokens, or in-sheet brand keywords.
Scheme boundaries follow section rows (reusing portfolio.py JUNK_ROW_PATTERNS).
``reporting_date`` is parsed from "as on <date>" strings.
"""
from __future__ import annotations

import calendar
import logging
import re
from datetime import date as _date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from ..models import ParserResult
from .portfolio import (
    COLUMN_ALIASES,
    JUNK_ROW_PATTERNS,
    _is_valid_isin,
    _looks_like_credit_rating,
    _map_columns,
    _normalize_record_pct_units,
    _parse_date,
    _read_excel_file,
)

LOGGER = logging.getLogger(__name__)

PARSER_NAME = "portfolio_monthly_amfi"
SOURCE_DATASET = "amfi_monthly"

# Junk rows seen in AMFI monthly workbooks that portfolio.py's patterns miss.
LOCAL_JUNK_PATTERNS = [
    r"^equity & equity related instruments?$",
    r"^debt securities?$",
    r"^list(?:ed|ing).*(?:stock exchanges|exchanges).*",
]
_LOCAL_JUNK_RE = re.compile("|".join(LOCAL_JUNK_PATTERNS), re.IGNORECASE)

_ALL_ALIASES = {a for aliases in COLUMN_ALIASES.values() for a in aliases}
# Squashed (no spaces/punctuation) alias -> canonical field, for fuzzy header
# matches like "Market/Fair Value\n( Rs. in Lacs)" whose parenthesised spacing
# differs from every curated alias.
_SQUASH_RE = re.compile(r"[^a-z0-9%&/]")
_SQUASHED_ALIASES = {_SQUASH_RE.sub("", a): field
                     for field, aliases in COLUMN_ALIASES.items() for a in aliases}


def _match_field(col: str) -> str | None:
    """Map a raw header cell to a canonical field name (exact then fuzzy)."""
    norm = " ".join(col.split()).strip().lower()
    for target, aliases in COLUMN_ALIASES.items():
        if norm in aliases:
            return target
    return _SQUASHED_ALIASES.get(_SQUASH_RE.sub("", norm))
_SECTION_HEADER_REGEX = re.compile("|".join(JUNK_ROW_PATTERNS), re.IGNORECASE)

# End-of-portfolio markers (mirrors portfolio.py)
_END_MARKERS = ("grand total", "net receivable", "portfolio characteristics",
                "derivative", "yield to maturity", "investment performance")

# Filename token -> canonical AMC name
_FILENAME_AMC_MAP: list[tuple[str, str]] = [
    ("nimf", "Nippon India Mutual Fund"),
    ("nippon", "Nippon India Mutual Fund"),
    ("adityabirla", "Aditya Birla Sun Life Mutual Fund"),
    ("aditya birla", "Aditya Birla Sun Life Mutual Fund"),
    ("absl", "Aditya Birla Sun Life Mutual Fund"),
    ("icici", "ICICI Prudential Mutual Fund"),
    ("360_one", "360 ONE Mutual Fund"),
    ("360 one", "360 ONE Mutual Fund"),
    ("axis", "Axis Mutual Fund"),
    ("motilal", "Motilal Oswal Mutual Fund"),
    ("ppfas", "Parag Parikh Mutual Fund"),
    ("parag parikh", "Parag Parikh Mutual Fund"),
    ("bank of india", "Bank of India Mutual Fund"),
    ("quant", "Quant Mutual Fund"),
]

# Brand keyword found in scheme names / sheet text -> canonical AMC name
_BRAND_KEYWORD_MAP: list[tuple[str, str]] = [
    ("nippon india", "Nippon India Mutual Fund"),
    ("aditya birla sun life", "Aditya Birla Sun Life Mutual Fund"),
    ("icici prudential", "ICICI Prudential Mutual Fund"),
    ("parag parikh", "Parag Parikh Mutual Fund"),
    ("motilal oswal", "Motilal Oswal Mutual Fund"),
    ("bank of india", "Bank of India Mutual Fund"),
    ("quant mutual fund", "Quant Mutual Fund"),
    ("360 one", "360 ONE Mutual Fund"),
]

_AMC_NAME_STOPWORDS = ("mutual fund", "asset management", "asset management company",
                       "amc name", "back to index", "raif")


def detect_amc(filename: str | None, metadata: dict[str, Any] | None = None,
               context_texts: list[str] | None = None) -> str | None:
    """Detect the AMC name from metadata, filename tokens, or in-sheet text."""
    if metadata:
        hint = metadata.get("amc_name") or metadata.get("amc_hint")
        if hint:
            return str(hint)
    if filename:
        fn = filename.lower()
        for token, amc in _FILENAME_AMC_MAP:
            if token in fn:
                return amc
    for text in context_texts or []:
        low = text.lower().strip()
        for keyword, amc in _BRAND_KEYWORD_MAP:
            if keyword in low:
                return amc
    return None


def _is_junk(name: str) -> bool:
    n = " ".join(name.split()).strip().lower()
    if not n:
        return False
    return bool(_SECTION_HEADER_REGEX.match(n) or _LOCAL_JUNK_RE.match(n))


def _extract_as_on_date(text: str) -> str | None:
    """Extract an ISO date from 'as on'/'as of' strings with many formats."""
    m = re.search(r"as\s+o[nf]\s*:?\s*(.+)", text, re.IGNORECASE)
    if not m:
        # Fallback: any date-like string in the text
        m = re.search(r"(\d{1,2}[\s\-/][A-Za-z]+[\s,\-/]?\d{4}|" 
                      r"[A-Za-z]+\s+\d{1,2},?\s*\d{4})", text)
        if not m:
            return None
        candidate = m.group(1)
    else:
        candidate = m.group(1)
    candidate = candidate.replace(",", ", ").replace("  ", " ").strip()
    fmts = ["%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y",
            "%d-%m-%Y", "%d/%m/%Y", "%d-%B-%Y", "%d-%b-%Y"]
    for f in fmts:
        try:
            return datetime.strptime(candidate, f).date().isoformat()
        except ValueError:
            continue
    return None


def _is_index_sheet(name: str, raw_df: pd.DataFrame) -> bool:
    """True if this sheet looks like a table-of-contents/Index sheet."""
    if re.match(r".*\bindex\b.*", name, re.IGNORECASE):
        return True
    # Heuristic: few columns and no holdings-table aliases anywhere
    if raw_df.shape[1] > 5:
        return False
    flat = {str(v).strip().lower() for v in raw_df.values.ravel() if pd.notna(v)}
    alias_hits = sum(1 for v in flat if v in _ALL_ALIASES)
    return alias_hits == 0


def _build_index_map(raw_df: pd.DataFrame) -> dict[str, str]:
    """Build sheet-code -> full scheme name map from an Index sheet."""
    index_map: dict[str, str] = {}
    for _, row in raw_df.iterrows():
        cells = [str(v).strip() for v in row.values if pd.notna(v) and str(v).strip()]
        if len(cells) < 2:
            continue
        # code = shortest cell that looks like an alphanumeric code (must
        # contain a letter — numeric "Sr No." cells are NOT codes);
        # name = longest other cell
        code_candidates = [c for c in cells
                           if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9\-_]{1,11}", c)
                           and not re.search(r"\d{4}", c)
                           and re.search(r"[A-Za-z]", c)]
        name_candidates = [c for c in cells if c not in code_candidates]
        if not code_candidates or not name_candidates:
            continue
        code = min(code_candidates, key=len)
        name = max(name_candidates, key=len)
        index_map[code.upper()] = " ".join(name.split())
    return index_map


def _scheme_name_from_rows(raw_df: pd.DataFrame, header_idx: int) -> str | None:
    """Find scheme name in rows above the header.

    Pass 1 prefers cells containing fund/scheme/ETF keywords; pass 2 accepts
    any sufficiently descriptive cell (ICICI FMP files name schemes like
    "ICICI Prudential Fixed Maturity Plan - Series 85 - ..." with no keyword).
    """
    fallback = None
    keyword_hits = []
    for i in range(min(header_idx, len(raw_df))):
        for cell in raw_df.iloc[i].values:
            if pd.isna(cell):
                continue
            s = " ".join(str(cell).split())
            low = s.lower()
            if not s or len(s) > 300 or len(s) < 8:
                continue
            if any(sw in low for sw in _AMC_NAME_STOPWORDS):
                continue
            if "portfolio" in low or "as on" in low or "as of" in low:
                continue
            # Known non-scheme labels (risk meters, labelling blocks) — only
            # disqualify FALLBACK candidates; real scheme names like
            # "... Nifty 5 yr Benchmark G-SEC ETF" carry keywords.
            has_kw = any(kw in low for kw in ("fund", "scheme", "etf", "fof"))
            # Risk-o-meter legend rows: "A-I - A Scheme with Relatively Low ..."
            if re.match(r"^[A-Z]{1,3}\s*[-–—]\s+", s) or "a scheme with" in low:
                continue
            if not has_kw and any(lbl in low for lbl in ("product labelling", "risk-o-meter",
                                                         "riskometer", "benchmark",
                                                         "labelling", "risk",
                                                         "potential risk class")):
                continue
            # Space-less cells are sheet codes (e.g. "AXISEFOF"), not names —
            # even when a keyword hides inside them ("axisefof" contains "fof").
            if " " not in s:
                continue
            # Descriptive sub-lines: "(An open ended ... fund)", "• objective
            # bullets" — never the scheme name itself.
            if s[0] in "(•*-\"'" or s.startswith("''"):
                continue
            if has_kw:
                keyword_hits.append(s)
            elif fallback is None:
                fallback = s.split(" (")[0].strip() or s
    if keyword_hits:
        # First hit in document order wins: row0 of every observed layout
        # carries the true scheme name; later, longer rows can be comparison
        # tables or legends referencing OTHER funds.
        best = keyword_hits[0]
        return best.split(" (")[0].strip() or best
    return fallback


def _reporting_date_from_rows(raw_df: pd.DataFrame, header_idx: int) -> str | None:
    for i in range(min(header_idx + 1, len(raw_df))):
        for cell in raw_df.iloc[i].values:
            if pd.isna(cell):
                continue
            s = str(cell)
            d = _extract_as_on_date(s)
            if d:
                return d
            d = _parse_date(s.strip()) if "as on" in s.lower() or "as of" in s.lower() else None
            if d:
                return d
    return None


def _find_header_row(raw_df: pd.DataFrame) -> int:
    """First row where >= 2 cells match known column aliases."""
    for i, row in raw_df.iterrows():
        cells = [str(v).strip().lower() for v in row.values
                 if pd.notna(v) and str(v).strip()]
        hits = sum(1 for c in cells if c in _ALL_ALIASES)
        if hits >= 2:
            return int(i)
    return -1


def _detect_column_offset(raw_df: pd.DataFrame, col_map_by_pos: dict[int, str],
                          header_isin_pos: int | None, start_row: int) -> int:
    """Detect the shift between header positions and actual data positions.

    Some workbooks (Axis, 360 ONE) prefix each data row with a short scheme-code
    cell that has no header entry, shifting every data field right by one.
    """
    if header_isin_pos is None:
        return 0
    for i in range(start_row + 1, min(start_row + 40, len(raw_df))):
        for j, v in enumerate(raw_df.iloc[i].values):
            if pd.notna(v) and _is_valid_isin(str(v).strip()):
                return j - header_isin_pos
    return 0


def _to_float(val: Any) -> float | None:
    if val is None or (not isinstance(val, str) and pd.isna(val)):
        return None
    if isinstance(val, str):
        cleaned = val.replace("%", "").replace(",", "").strip()
        if cleaned.lower() in ("nil", "", "nan", "-"):
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    try:
        return float(str(val).replace(",", ""))
    except (ValueError, TypeError):
        return None


def parse_portfolio_monthly_amfi(content: bytes | str, metadata: dict[str, Any]) -> ParserResult:
    """Parse an AMFI monthly portfolio disclosure workbook (one file)."""
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    warnings: list[str] = []

    if isinstance(content, str):
        content = content.encode("utf-8")
    file_ext = metadata.get("file_ext", ".xlsx")
    source_name = metadata.get("source_file") or \
        (metadata.get("source_url", "") or "").split("/")[-1] or "workbook"
    try:
        xlsx = _read_excel_file(content, file_ext)
    except Exception as exc:
        return ParserResult(
            dataset_type="portfolio_disclosure",
            parser_name=PARSER_NAME,
            parser_version="1.0",
            confidence=0.0,
            records=[],
            warnings=warnings,
            errors=[f"Failed to read workbook {source_name}: {exc}"],
            metadata=metadata,
        )

    # Pass 1: identify Index sheets and build code->scheme-name maps
    sheet_frames: dict[str, pd.DataFrame] = {}
    index_maps: dict[str, dict[str, str]] = {}
    merged_index_map: dict[str, str] = {}
    for sheet_name in xlsx.sheet_names:
        raw_df = pd.read_excel(xlsx, sheet_name=sheet_name, header=None, dtype=str)
        sheet_frames[sheet_name] = raw_df
        if _is_index_sheet(sheet_name, raw_df):
            index_maps[sheet_name] = _build_index_map(raw_df)
            merged_index_map.update(index_maps[sheet_name])

    detected_contexts: list[str] = []
    for sheet_name in xlsx.sheet_names:
        if sheet_name in index_maps:
            continue
        raw_df = sheet_frames[sheet_name]
        try:
            sheet_records = _parse_scheme_sheet(
                xlsx, sheet_name, raw_df, merged_index_map, detected_contexts,
                records, errors, warnings,
            )
        except Exception as exc:
            errors.append(f"Sheet {sheet_name}: parse error: {exc}")
            sheet_records = []

    amc_name = detect_amc(source_name, metadata, detected_contexts + [source_name])
    if amc_name is None:
        warnings.append(f"AMC could not be detected for {source_name}")

    for rec in records:
        rec.setdefault("amc_hint", amc_name) if amc_name else None
        rec["source_dataset"] = SOURCE_DATASET
        rec["source_file"] = source_name

    metadata_out = dict(metadata)
    metadata_out["source_dataset"] = SOURCE_DATASET
    metadata_out["amc_name"] = amc_name

    records = _normalize_record_pct_units(records)
    return ParserResult(
        dataset_type="portfolio_disclosure",
        parser_name=PARSER_NAME,
        parser_version="1.0",
        confidence=0.8 if records else 0.0,
        records=records,
        warnings=warnings,
        errors=errors,
        metadata=metadata_out,
    )


def _parse_scheme_sheet(xlsx, sheet_name: str, raw_df: pd.DataFrame,
                        index_map: dict[str, str], detected_contexts: list[str],
                        records: list[dict[str, Any]], errors: list[str],
                        warnings: list[str]) -> int:
    """Parse one scheme sheet; appends to ``records``, returns record count."""
    if raw_df.empty:
        return 0
    header_idx = _find_header_row(raw_df)
    if header_idx < 0:
        LOGGER.debug("Sheet %s: no header row found, skipping", sheet_name)
        return 0

    # Column mapping by position from the header row
    header_cells = list(raw_df.iloc[header_idx].values)
    col_map_by_pos: dict[int, str] = {}
    for j, cell in enumerate(header_cells):
        if pd.isna(cell):
            continue
        mapped = _match_field(str(cell))
        if mapped:
            col_map_by_pos[j] = mapped

    def pos_of(field: str) -> int | None:
        for j, m in col_map_by_pos.items():
            if m == field:
                return j
        return None

    offset = _detect_column_offset(
        raw_df, col_map_by_pos, pos_of("isin"), header_idx)

    # Scheme name: Index sheet map first, then in-sheet rows, then sheet title
    scheme_name = index_map.get(sheet_name.upper()) or \
        _scheme_name_from_rows(raw_df, header_idx) or sheet_name
    reporting_date = _reporting_date_from_rows(raw_df, header_idx)

    # Context text for AMC detection (first non-empty rows)
    for i in range(min(header_idx + 1, len(raw_df))):
        for cell in raw_df.iloc[i].values:
            if pd.notna(cell) and str(cell).strip():
                detected_contexts.append(str(cell))

    sec_pos = pos_of("security_name")
    if sec_pos is None:
        warnings.append(f"Sheet {sheet_name}: no security_name column detected")
        return 0

    count_before = len(records)
    saw_holding = False
    for idx in range(header_idx + 1, len(raw_df)):
        row_vals = list(raw_df.iloc[idx].values)

        def val_at(pos: int | None) -> Any:
            if pos is None:
                return None
            shifted = pos + offset
            return row_vals[shifted] if shifted < len(row_vals) else None

        security_name_raw = val_at(sec_pos)
        security_name = " ".join(str(security_name_raw).split()) \
            if security_name_raw is not None and str(security_name_raw) != "nan" else ""
        if not security_name or len(security_name) < 2:
            continue
        if security_name.lower() in _ALL_ALIASES:
            continue
        name_lower = security_name.lower()
        if any(m in name_lower for m in _END_MARKERS) and \
                not re.search(r"\bltd\b|\blimited\b", name_lower):
            if saw_holding:
                LOGGER.debug("Sheet %s: end of portfolio at row %d", sheet_name, idx)
                break
            continue
        isin_raw = val_at(pos_of("isin"))
        isin = str(isin_raw).strip() if isin_raw is not None and str(isin_raw) != "nan" else ""
        valid_isin = _is_valid_isin(isin)
        if _is_junk(security_name) and not valid_isin:
            continue

        pct_nav = _to_float(val_at(pos_of("percentage_to_nav")))
        market_value = _to_float(val_at(pos_of("market_value")))
        quantity = _to_float(val_at(pos_of("quantity")))

        # Drop rows with no quantitative data unless they carry a valid ISIN
        if pct_nav is None and market_value is None and quantity is None and not valid_isin:
            continue
        saw_holding = True

        sector_raw = str(val_at(pos_of("sector")) or "").strip()
        if sector_raw == "nan":
            sector_raw = ""
        rating_col_val = str(val_at(pos_of("rating")) or "").strip()
        if rating_col_val == "nan":
            rating_col_val = ""
        if sector_raw and _looks_like_credit_rating(sector_raw):
            sector, rating = None, sector_raw
        else:
            sector, rating = (sector_raw or None), (rating_col_val or None)

        coupon = _to_float(val_at(pos_of("coupon")))
        maturity_raw = val_at(pos_of("maturity_date"))
        maturity_date = _parse_date(str(maturity_raw).strip()) \
            if maturity_raw is not None and str(maturity_raw) != "nan" else None
        asset_class_raw = val_at(pos_of("asset_class"))
        asset_class = str(asset_class_raw).strip() \
            if asset_class_raw is not None and str(asset_class_raw) != "nan" else None

        records.append({
            "security_name": security_name,
            "isin": isin if valid_isin else None,
            "sector": sector,
            "rating": rating,
            "coupon": coupon,
            "maturity_date": maturity_date,
            "asset_class": asset_class,
            "quantity": quantity,
            "percentage_to_nav": pct_nav,
            "market_value": market_value,
            "sheet_name": sheet_name,
            "row_number": int(idx),
            "scheme_name": scheme_name,
            "reporting_date": reporting_date,
        })
    return len(records) - count_before


def parse_portfolio_monthly_amfi_directory(dir_path: str | Path,
                                           metadata: dict[str, Any] | None = None) -> ParserResult:
    """Parse a directory of per-scheme monthly portfolio files (ICICI style).

    Each ``*.xlsx``/``*.xls`` file in the directory holds one scheme's portfolio.
    """
    metadata = dict(metadata or {})
    dir_path = Path(dir_path)
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    warnings: list[str] = []
    files = sorted(p for p in dir_path.iterdir()
                   if p.suffix.lower() in (".xlsx", ".xls") and not p.name.startswith("~$"))
    for path in files:
        file_metadata = dict(metadata)
        file_metadata["file_ext"] = path.suffix
        file_metadata["source_file"] = path.name
        try:
            content = path.read_bytes()
        except Exception as exc:
            errors.append(f"{path.name}: read error: {exc}")
            continue
        result = parse_portfolio_monthly_amfi(content, file_metadata)
        records.extend(result.records)
        errors.extend([f"{path.name}: {e}" for e in result.errors])
        warnings.extend([f"{path.name}: {w}" for w in result.warnings])

    dir_amc = detect_amc(dir_path.name, metadata,
                         [r.get("amc_hint") or "" for r in records])
    if dir_amc:
        for rec in records:
            rec["amc_hint"] = dir_amc

    metadata_out = dict(metadata)
    metadata_out["source_dataset"] = SOURCE_DATASET
    metadata_out["amc_name"] = dir_amc
    metadata_out["directory"] = str(dir_path)

    return ParserResult(
        dataset_type="portfolio_disclosure",
        parser_name=PARSER_NAME,
        parser_version="1.0",
        confidence=0.8 if records else 0.0,
        records=records,
        warnings=warnings,
        errors=errors,
        metadata=metadata_out,
    )
