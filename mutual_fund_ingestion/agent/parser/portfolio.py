"""Excel/CSV portfolio disclosure parser."""
from __future__ import annotations

import logging
import re
from datetime import datetime
from io import BytesIO
from typing import Any

import pandas as pd

from ..models import ParserResult


LOGGER = logging.getLogger(__name__)

COLUMN_ALIASES = {
    "security_name": [
        "name of instrument", "security", "company", "name", "instrument", "scrip", 
        "security_name", "name of the instrument / issuer", "name of the instrument",
        "company/issuer/instrument name", "issuer/instrument name", "description"
    ],
    "isin": ["isin", "isin code", "isin no", "isin/ticker", "ticker"],
    "quantity": ["quantity", "no. of shares", "units", "face value", "nos"],
    "market_value": [
        "market value", "value", "market value (rs. in lakhs)", "fair value", "amount",
        "mkt value",
        "market value (rs. in lakhs) (exposure)", 
        "market/fair value (rs. in lakhs)", "market/fair value rs. in lakhs",
        "market/fair value (rs.lakh)", "market/fair value (rs. lakh)",
        "market/fair value lacs", "market/fair value (rs. lacs)",
        "market/fair value (rs. in lacs)", "market/fair value (rs. in lakh)",
        "net receivable/ market value", "net receivable / market value",
        "market value (rs. lakh)", "market value(rs. lakh)",
        "exposure/market value(rs.lakh)", "exposure/market value (rs.lakh)",
        "cost of investment (rs. in lakhs)",
    ],
    "percentage_to_nav": ["% to nav", "% net assets", "percentage", "% of net assets", "percentage to nav", "% to aum", "% to net assets", "percentage to aum", "% of nav"],
    "sector": [
        "industry", "sector", "sector/industry", "industry sector", "business sector",
        "industry / rating", "industry^ / rating", "industry ^/ rating",
    ],
    "rating": ["rating", "credit rating", "rating/industry", "sector/industry", "industry^ / rating", "industry/rating"],
    "maturity_date": ["maturity", "maturity date"],
    "coupon": ["coupon", "coupon rate", "ytm %", "ytc %"],
    "asset_class": ["asset class", "type"],
}


ISIN_REGEX = re.compile(r'^[A-Z]{2}[A-Z0-9]{9}\d$')

SECTION_HEADER_PATTERNS = [
    r'^total$',
    r'^sub[\s-]?total$',
    r'^grand[\s-]?total$',
    r'^direct[\s-]?plan$',
    r'^regular[\s-]?plan$',
    r'^growth$',
    r'^idcw$',
    r'^dividend$',
    r'^monthly[\s-]?idcw$',
    r'^quarterly[\s-]?idcw$',
    r'^annual[\s-]?idcw$',
]

# Junk rows that are not holdings: section markers, metadata labels, sub-headers
JUNK_ROW_PATTERNS = SECTION_HEADER_PATTERNS + [
    r'^\(?[a-z]\)?\s',                       # "(a) ...", "a) ..."
    r'^[(]?(?:un)?listed.*$',                  # listed / unlisted groupings
    r'^others$',                               # catch-all row
    r'^corporate debt market development fund$',
    r'^certificate of deposit$',
    r'^money market instruments?$',
    r'^debt instruments?$',
    r'^securitised debt$',
    r'^ytm.*$',
    r'^yield to maturity$',
    r'^ytc[- ]yield to call$',
    r'^yield to call$',
    r'^average (?:maturity|coupon|yield).*$',
    r'^modified duration.*$',
    r'^portfolio (?:turnover|characteristics).*$',
    r'^net (?:assets|receivable).*$',
    r'^cash & cash equivalents$',
    r'^foreign holdings$',
    r'^treasury bills?$',
    r'^reverse repo$',
    r'^triparty repo$',
    r'^total (?:debt|equity|investments|assets|liabilities).*$',
    r'^grand total$',
    r'^derivative(s)?.*$',
    r'^[=\-_]{3,}$',                           # separator rows
    # --- Observed canonical-data leaks (Task A6) ---
    r'^treps\b.*$',                            # TREPS / reverse-repo cash rows (all variants)
    r'^commercial papers?$',                   # section header (singular + plural)
    r'^certificates? of deposits?$',           # section header
    r'^government securities(?: \((?:central/state|state)\))?$',
    # ^ exact-name header only; rows named "Government Securities" WITH an
    # ISIN are real holdings (ICICI gilt/sovereign sheets) and must survive.
    r'^net current assets?\*?$',               # subtotal row
    r'^total net assets$',                     # subtotal row
    r'^cash & cash equivalent$',               # singular variant of existing plural pattern
    r'^grand total \(aum\)$',
    r'^bond & ncd.?s?$',                       # "BOND & NCD's" grouping
    r'^non-?convertible debentures? / bonds$',  # ICICI debt grouping header (children listed below)
    r'^zero coupon bonds / deep discount bonds$',  # ICICI grouping header
    r'^equity & equity related(?: foreign investments)?$',  # equity grouping headers
    r'^market value includes accrued interest$',
    r'^scheme name:?$',                        # disclosure metadata labels
    r'^as on \(date\)$',
    r'^scheme riskometer$',
    r'^macaulay duration$',                    # duration stats leaked into ISIN column
    r'^residual maturity$',
    r'^description \(if any\)$',
    r'^annualised portfolio ytm\*?:?$',
    r'^benchmark riskometer:.*$',              # "Benchmark Riskometer: <index>" footnotes
    r'^sbi funds management pvt (?:ltd|limited)/fund parent$',
    r'^notes\b.*$',                            # "Notes:", "Notes & symbols :-"
    r'^~.*$',                                  # "~ yield to maturity ...", footnote markers
    r'^\*+.*$',                                # "* in case of semi-annual ytm...", "** non traded..."
    r'^\(\d+\)\s',                             # numbered footnotes "(2) total value ..."
    r'^\d+\.\s+(?:total|net assets)',          # "1.  total value provided ..."
    r'^\^?\s*pursuant to amfi circular.*$',    # YTC footnote rows
    r'^.*aggregate investments by (?:other |the )?schemes',  # inter-scheme footnotes
]

SECTION_HEADER_REGEX = re.compile('|'.join(JUNK_ROW_PATTERNS), re.IGNORECASE)

def _is_valid_isin(isin: str) -> bool:
    """Validate ISIN format (2 letters + 9 alphanumeric + 1 check digit)."""
    if not isin or not isinstance(isin, str):
        return False
    isin = isin.strip().upper()
    return bool(ISIN_REGEX.match(isin))

def _is_section_header(name: str) -> bool:
    """Check if security name is a section header (Total, Sub Total, etc.)."""
    if not name or not isinstance(name, str):
        return False
    name = name.strip().lower()
    return bool(SECTION_HEADER_REGEX.match(name))

def _normalize_col(col: str) -> str:
    # Collapse all whitespace (newlines are common in Excel headers, e.g. "% to Net\n Assets")
    col_lower = " ".join(col.split()).strip().lower()
    for target, aliases in COLUMN_ALIASES.items():
        if col_lower in aliases:
            return target
    return col_lower


def _map_columns(df: pd.DataFrame) -> dict[str, str]:
    col_map = {}
    for col in df.columns:
        mapped = _normalize_col(str(col))
        col_map[col] = mapped
    return col_map


def _parse_date(val: Any) -> str | None:
    if pd.isna(val):
        return None
    s = str(val).strip()
    for fmt in ["%d-%b-%Y", "%b %Y", "%Y-%m-%d", "%d/%m/%Y", "%B %Y", "%d-%m-%Y", "%B %d, %Y", "%b %d, %Y", "%b %d,%Y", "%B %d,%Y"]:
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    # Try to extract date from "Monthly Portfolio Statement as on June 30, 2026" pattern
    import re
    match = re.search(r'as on\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4})', s)
    if match:
        try:
            return datetime.strptime(match.group(1), "%B %d, %Y").date().isoformat()
        except ValueError:
            pass
    # Try "Portfolio as on Aug 15,2026" pattern
    match = re.search(r'portfolio as on\s+(.+)', s, re.IGNORECASE)
    if match:
        date_str = match.group(1).strip()
        # Normalize comma spacing
        date_str = date_str.replace(",", ", ")
        try:
            return datetime.strptime(date_str, "%b %d, %Y").date().isoformat()
        except ValueError:
            pass
    return None


def _normalize_pct_to_nav(value: float | None) -> float | None:
    """Normalize percentage-to-NAV to percent units (0-100+).

    Some AMCs (DSP, ICICI, Mirae) disclose as fractions 0-1; others as true
    percents. If the value is clearly a fraction, scale to percent.
    """
    if value is None:
        return None
    if 0.0 < value <= 1.0:
        return round(value * 100.0, 6)
    return value


def _normalize_record_pct_units(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detect whether percentage_to_nav values are fractions (sum ~1) or percents (sum ~100)
    and scale fractions to percents. Grouping key is (sheet_name,) when present so multi-sheet
    workbooks (one scheme per sheet) normalize correctly."""
    from collections import defaultdict
    groups: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
    for r in records:
        groups[(r.get("source_zip_file"), r.get("sheet_name"),)].append(r)
    for group_records in groups.values():
        vals = [r.get("percentage_to_nav") for r in group_records if r.get("percentage_to_nav") is not None]
        if not vals:
            continue
        total = sum(vals)
        max_val = max(vals)
        # Values are disclosed either as fractions (0-1) or true percents (sum ~100).
        # If everything is <= 1.0 it is almost certainly fractional UNLESS the group
        # already totals ~100 (a fully-disclosed percent portfolio of tiny weights).
        # Sheets containing multiple fund blocks sum to k (> 1) while still being
        # fractional, so the old "total <= 1.5" test mis-scaled those files.
        if max_val <= 1.0 and not (90 <= total <= 105):
            for r in group_records:
                v = r.get("percentage_to_nav")
                if v is not None:
                    r["percentage_to_nav"] = round(v * 100.0, 6)
    return records


_CREDIT_RATING_RE = None


def _looks_like_credit_rating(value: str | None) -> bool:
    """True if value resembles a credit rating (CRISIL AAA, ICRA A1+, Sovereign, IND AA+, etc.)."""
    if not value or not isinstance(value, str):
        return False
    import re
    v = value.strip().upper()
    if v in ("SOVEREIGN", "SOV", "GOVERNMENT GUARANTEED", "NOT RATED", "NR"):
        return True
    # Agency prefix + grade pattern
    if re.search(r"\b(CRISIL|ICRA|CARE|IND|BRICKWORK|India Ratings|FITCH|Moody)\b", v):
        return True
    # Standalone grades like AAA, AA+, A1+, BBB-, D
    if re.fullmatch(r"(AAA|AA\+?|AA-|A\+{1,2}|A-|BBB\+?|BBB-|BB\+?|BB-|B\+?|B-|D|A1\+|A2\+|P1|M1|MLD)", v):
        return True
    return False


def _read_excel_file(content: bytes, file_ext: str) -> pd.ExcelFile:
    """Read Excel file with appropriate engine based on extension and content.
    
    Many AMC files have misleading extensions (e.g. .xls that are actually xlsx,
    or xlsx content served without metadata). Sniff the OLE2 magic number for
    true legacy .xls, then try openpyxl, then xlrd.
    """
    # Legacy binary .xls starts with the OLE2 compound document magic (d0 cf 11 e0)
    is_ole2 = isinstance(content, (bytes, bytearray)) and bytes(content[:4]) == b"\xd0\xcf\x11\xe0"
    # Try openpyxl first (handles xlsx and xls files saved in xlsx format)
    try:
        return pd.ExcelFile(BytesIO(content), engine="openpyxl")
    except Exception:
        pass
    # Fall back to xlrd for true .xls files
    if file_ext.lower() == ".xls" or is_ole2:
        try:
            return pd.ExcelFile(BytesIO(content), engine="xlrd")
        except Exception:
            pass
    # Last resort: try openpyxl again without extension check
    try:
        return pd.ExcelFile(BytesIO(content), engine="openpyxl")
    except Exception as exc:
        raise ValueError(f"Failed to read Excel file: {exc}")


def parse_portfolio_excel(content: bytes | str, metadata: dict[str, Any]) -> ParserResult:
    records = []
    errors = []
    warnings = []
    if isinstance(content, str):
        content = content.encode("utf-8")
    # Determine file extension from metadata or default to .xlsx
    file_ext = metadata.get("file_ext", ".xlsx")
    try:
        xlsx = _read_excel_file(content, file_ext)
        for sheet_name in xlsx.sheet_names:
          try:
            # First pass: read without header to find the header row
            raw_df = pd.read_excel(xlsx, sheet_name=sheet_name, header=None, dtype=str)
            if raw_df.empty:
                continue

            # Find header row: first row where >= 2 cells match known column aliases
            header_row_idx = 0
            scheme_name = None
            reporting_date = None
            
            for i, row in raw_df.iterrows():
                normalized_cells = [str(v).strip().lower() for v in row.values if str(v).strip() and str(v).strip().lower() != "nan"]
                known_count = sum(
                    1 for v in normalized_cells
                    if any(v in aliases for aliases in COLUMN_ALIASES.values())
                )
                if known_count >= 2:
                    header_row_idx = int(i)
                    break
                # Extract scheme_name and reporting_date from rows before header
                for cell in row.values:
                    if pd.notna(cell):
                        cell_str = str(cell).strip()
                        # Look for scheme name patterns - prefer more specific names
                        cell_lower = cell_str.lower()
                        is_scheme_like = any(kw in cell_lower for kw in ["fund", "scheme", "etf"]) and "portfolio" not in cell_lower
                        is_portfolio_label = "portfolio" in cell_lower and "fund" not in cell_lower and "scheme" not in cell_lower and "etf" not in cell_lower
                        if scheme_name is None and is_scheme_like:
                            # Skip generic AMC/company names and statement headers (case-insensitive)
                            if not any(skip in cell_lower for skip in [
                                "mutual fund", "asset management", "asset management company",
                                "amc name", "raif",
                            ]) and len(cell_str) < 250:
                                # Store the descriptive part before a parenthetical, if present
                                scheme_name = cell_str.split(" (")[0].strip() or cell_str
                        # Look for date patterns
                        if reporting_date is None:
                            for fmt in ["%d-%b-%Y", "%b %Y", "%Y-%m-%d", "%d/%m/%Y", "%B %Y", "%d-%m-%Y"]:
                                try:
                                    reporting_date = datetime.strptime(cell_str, fmt).date().isoformat()
                                    break
                                except ValueError:
                                    continue
                            # Try to extract date from "Monthly Portfolio Statement as on June 30, 2026" pattern
                            if reporting_date is None:
                                import re
                                match = re.search(r'as on\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4})', cell_str)
                                if match:
                                    try:
                                        reporting_date = datetime.strptime(match.group(1), "%B %d, %Y").date().isoformat()
                                    except ValueError:
                                        pass
                            # Try "Portfolio as on Aug 15,2026" pattern
                            if reporting_date is None:
                                import re
                                match = re.search(r'portfolio as on\s+(.+)', cell_str, re.IGNORECASE)
                                if match:
                                    date_str = match.group(1).strip()
                                    # Normalize comma spacing
                                    date_str = date_str.replace(",", ", ")
                                    try:
                                        reporting_date = datetime.strptime(date_str, "%b %d, %Y").date().isoformat()
                                    except ValueError:
                                        pass
                            # Try "Portfolio As Of - 31 December 2023" pattern (ABSL)
                            if reporting_date is None:
                                match = re.search(r'as of\s*-?\s*(\d{1,2})\s+([A-Za-z]+),?\s+(\d{4})', cell_str, re.IGNORECASE)
                                if match:
                                    try:
                                        day, month, year = match.groups()
                                        reporting_date = datetime.strptime(f"{day} {month} {year}", "%d %B %Y").date().isoformat()
                                    except ValueError:
                                        try:
                                            reporting_date = datetime.strptime(f"{day} {month.title()} {year}", "%d %B %Y").date().isoformat()
                                        except ValueError:
                                            pass

            # Re-read with detected header row
            df = pd.read_excel(xlsx, sheet_name=sheet_name, header=header_row_idx, dtype=str)

            # Normalize column names
            df.columns = [str(c).strip() for c in df.columns]
            col_map = _map_columns(df)
            # Require a real security_name column; otherwise this sheet is not a
            # holdings table (e.g. Axis "Index" table-of-contents sheets).
            sec_col = next((k for k, v in col_map.items() if v == "security_name"), None)
            if sec_col is None:
                LOGGER.debug("Sheet %s: no security_name column detected, skipping", sheet_name)
                continue
            # All known column aliases flattened (to skip repeated header rows)
            _all_aliases = {a for aliases in COLUMN_ALIASES.values() for a in aliases}
            # End-of-portfolio markers: everything after these is notes/derivatives/performance
            _end_markers = ("grand total", "net receivable", "portfolio characteristics",
                            "derivative", "yield to maturity", "investment performance")
            _saw_holding = False
            for idx, row in df.iterrows():
                security_name = str(row.get(sec_col, "")).strip()
                if not security_name or security_name == "nan" or len(security_name) < 2:
                    continue
                # Skip repeated header rows embedded in the data
                if " ".join(security_name.split()).strip().lower() in _all_aliases:
                    continue
                name_lower = " ".join(security_name.split()).strip().lower()
                if any(name_lower.startswith(m) or (m in name_lower and len(name_lower) < 60) for m in _end_markers):
                    # Stop processing this sheet once the portfolio table has ended
                    if _saw_holding:
                        LOGGER.debug("Sheet %s: end of portfolio at row %d (%r)", sheet_name, idx, security_name[:40])
                        break
                    continue
                # Skip section headers (Total, Sub Total, Direct Plan, etc.).
                # Exception: a header-named row carrying a valid ISIN is a real
                # holding (ICICI gilt sheets name sovereign bonds exactly
                # "Government Securities" — the ISIN distinguishes them from
                # the section header, which has none).
                isin_col_early = next((k for k, v in col_map.items() if v == "isin"), None)
                isin_early = str(row.get(isin_col_early, "")).strip() if isin_col_early else ""
                if _is_section_header(security_name) and not _is_valid_isin(isin_early):
                    continue
                pct_nav = None
                for col, mapped in col_map.items():
                    if mapped == "percentage_to_nav":
                        raw = row.get(col, "")
                        if pd.notna(raw):
                            try:
                                pct_nav = float(str(raw).replace("%", "").replace(",", "").strip())
                            except ValueError:
                                pass
                mv_col = next((k for k, v in col_map.items() if v == "market_value"), None)
                market_value_raw = row.get(mv_col, None) if mv_col is not None else None
                # Ensure market_value is a scalar, not a Series
                if hasattr(market_value_raw, 'item'):
                    market_value_raw = market_value_raw.item()
                # Handle "Nil" values
                if isinstance(market_value_raw, str) and market_value_raw.strip().lower() == "nil":
                    market_value = None
                else:
                    try:
                        market_value = float(str(market_value_raw).replace(",", "")) if pd.notna(market_value_raw) else None
                    except (ValueError, TypeError):
                        market_value = None
                isin_col = next((k for k, v in col_map.items() if v == "isin"), None)
                isin = str(row.get(isin_col, "")).strip() if isin_col else ""
                sector_col = next((k for k, v in col_map.items() if v == "sector"), None)
                sector_raw = str(row.get(sector_col, "")).strip() if sector_col else ""
                # Hybrid "Industry/Rating" columns: classify the value
                if _looks_like_credit_rating(sector_raw):
                    rating_val, sector = sector_raw, None
                else:
                    rating_val, sector = None, sector_raw
                
                # Extract debt-specific fields
                rating_col = next((k for k, v in col_map.items() if v == "rating"), None)
                rating = str(row.get(rating_col, "")).strip() if rating_col else ""
                if not rating:
                    rating = rating_val or ""
                
                coupon_col = next((k for k, v in col_map.items() if v == "coupon"), None)
                coupon_raw = row.get(coupon_col, None) if coupon_col is not None else None
                if hasattr(coupon_raw, 'item'):
                    coupon_raw = coupon_raw.item()
                coupon = None
                if coupon_raw is not None and pd.notna(coupon_raw):
                    try:
                        cval = float(str(coupon_raw).replace("%", "").replace(",", "").strip())
                        coupon = cval
                    except (ValueError, TypeError):
                        coupon = None
                
                maturity_col = next((k for k, v in col_map.items() if v == "maturity_date"), None)
                maturity_raw = row.get(maturity_col, None) if maturity_col is not None else None
                maturity_date = _parse_date(maturity_raw) if pd.notna(maturity_raw) else None
                
                asset_class_col = next((k for k, v in col_map.items() if v == "asset_class"), None)
                asset_class = str(row.get(asset_class_col, "")).strip() if asset_class_col else ""
                
                quantity_col = next((k for k, v in col_map.items() if v == "quantity"), None)
                quantity_raw = row.get(quantity_col, None) if quantity_col is not None else None
                if hasattr(quantity_raw, 'item'):
                    quantity_raw = quantity_raw.item()
                if isinstance(quantity_raw, str) and quantity_raw.strip().lower() == "nil":
                    quantity = None
                elif quantity_raw is not None and pd.notna(quantity_raw):
                    try:
                        quantity = float(str(quantity_raw).replace(",", "").strip())
                    except (ValueError, TypeError):
                        quantity = None
                else:
                    quantity = None
                
                # Use sheet_name as scheme_name if not found
                final_scheme_name = scheme_name or sheet_name
                
                # Drop rows with no quantitative data (footnote/label rows that
                # survive section filtering) unless they carry a valid ISIN.
                if (pct_nav is None and market_value is None and quantity is None
                        and not _is_valid_isin(isin)):
                    continue
                _saw_holding = True
                
                records.append({
                    "security_name": security_name,
                    "isin": isin if isin and isin != "nan" else None,
                    "sector": sector if sector and sector != "nan" else None,
                    "rating": rating if rating and rating != "nan" else None,
                    "coupon": coupon,
                    "maturity_date": maturity_date,
                    "asset_class": asset_class if asset_class and asset_class != "nan" else None,
                    "quantity": quantity,
                    "percentage_to_nav": pct_nav,
                    "market_value": market_value,
                    "sheet_name": sheet_name,
                    "row_number": int(idx),
                    "scheme_name": final_scheme_name,
                    "reporting_date": reporting_date,
                })
          except Exception as sheet_exc:
              errors.append(f"Sheet {sheet_name}: parse error: {sheet_exc}")
    except Exception as exc:
        errors.append("Portfolio parse error: %s" % exc)
    records = _normalize_record_pct_units(records)
    return ParserResult(
        dataset_type="portfolio_disclosure",
        parser_name="portfolio_excel_v1",
        parser_version="1.0",
        confidence=0.7 if records else 0.0,
        records=records,
        warnings=warnings,
        errors=errors,
        metadata=metadata,
    )


def parse_portfolio_zip(content: bytes | str, metadata: dict[str, Any]) -> ParserResult:
    """Parse portfolio disclosure from ZIP files containing Excel/CSV files."""
    import zipfile
    import re
    from io import BytesIO
    
    records = []
    errors = []
    warnings = []
    
    if isinstance(content, str):
        content = content.encode("utf-8")
    
    # Extract reporting date from ZIP filename (e.g., "Fortnightly Debt Scheme Portfolio - 15th August 2026.zip")
    zip_filename = metadata.get("source_url", "").split("/")[-1]
    reporting_date = None
    # Pattern: "15th August 2026" or "31st July 2026" etc.
    date_match = re.search(r'(\d{1,2})(?:st|nd|rd|th)\s+([A-Za-z]+)\s+(\d{4})', zip_filename)
    if date_match:
        day, month, year = date_match.groups()
        try:
            reporting_date = datetime.strptime(f"{day} {month} {year}", "%d %B %Y").date().isoformat()
        except ValueError:
            pass
    
    try:
        with zipfile.ZipFile(BytesIO(content), 'r') as zip_file:
            for file_name in zip_file.namelist():
                if file_name.endswith(('.xlsx', '.xls', '.csv')):
                    try:
                        file_content = zip_file.read(file_name)
                        # Recursively parse the extracted file
                        file_metadata = metadata.copy()
                        file_metadata["file_ext"] = file_name[file_name.rfind('.'):]  # Extract extension
                        file_metadata["source_zip_file"] = file_name
                        file_metadata["zip_reporting_date"] = reporting_date
                        
                        # Extract scheme name from filename (e.g., "ICICI Prudential BSE Liquid Rate ETF - IDCW.xlsx")
                        scheme_name = file_name[:file_name.rfind('.')]
                        # Remove common suffixes
                        scheme_name = re.sub(r'\s*[-_]\s*(IDCW|Growth|Direct|Regular|Plan)$', '', scheme_name, flags=re.IGNORECASE)
                        file_metadata["zip_scheme_name"] = scheme_name.strip()
                        
                        # Multi-scheme workbooks: prefer per-sheet scheme names from the
                        # sheet's own header rows over a generic zip filename.
                        file_metadata["prefer_inner_scheme_name"] = True
                        
                        if file_name.endswith('.csv'):
                            result = parse_portfolio_csv(file_content, file_metadata)
                        else:
                            result = parse_portfolio_excel(file_content, file_metadata)
                       
                        if result.records:
                            # Normalize pct units per inner file (each file = one scheme's portfolio)
                            normalized = _normalize_record_pct_units(list(result.records))
                            for record in normalized:
                                record['source_zip_file'] = file_name
                                # Override scheme_name and reporting_date from ZIP metadata.
                                # With prefer_inner_scheme_name (multi-scheme workbooks like
                                # ABSL/ICICI), keep the per-sheet scheme_name detected by the
                                # excel parser and only fall back to the zip filename.
                                if file_metadata.get("prefer_inner_scheme_name"):
                                    if not record.get('scheme_name') or record['scheme_name'] == record.get('sheet_name'):
                                        if file_metadata.get("zip_scheme_name"):
                                            record['scheme_name'] = file_metadata["zip_scheme_name"]
                                    if not record.get('reporting_date') and file_metadata.get("zip_reporting_date"):
                                        record["reporting_date"] = file_metadata["zip_reporting_date"]
                                else:
                                    if file_metadata.get("zip_scheme_name"):
                                        record['scheme_name'] = file_metadata["zip_scheme_name"]
                                    if file_metadata.get("zip_reporting_date"):
                                        record["reporting_date"] = file_metadata["zip_reporting_date"]
                            records.extend(normalized)
                       
                        if result.errors:
                            errors.extend([f"{file_name}: {e}" for e in result.errors])
                        if result.warnings:
                            warnings.extend([f"{file_name}: {w}" for w in result.warnings])
                          
                    except Exception as exc:
                        errors.append(f"Failed to parse {file_name}: {exc}")
                      
    except Exception as exc:
        errors.append(f"ZIP parse error: {exc}")
      
    return ParserResult(
        dataset_type="portfolio_disclosure",
        parser_name="portfolio_zip_v1",
        parser_version="1.0",
        confidence=0.7 if records else 0.0,
        records=records,
        warnings=warnings,
        errors=errors,
        metadata=metadata,
    )


def parse_portfolio_csv(content: bytes | str, metadata: dict[str, Any]) -> ParserResult:
    """Parse portfolio disclosure from CSV (same column schema as Excel)."""
    from io import StringIO
    records = []
    errors = []
    warnings = []
    try:
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")
        df = pd.read_csv(StringIO(content), dtype=str)
        df.columns = [str(c).strip() for c in df.columns]
        col_map = _map_columns(df)
        for idx, row in df.iterrows():
            security_name = str(row.get(next((k for k, v in col_map.items() if v == "security_name"), df.columns[0]) or df.columns[0], "")).strip()
            if not security_name or security_name == "nan" or len(security_name) < 2:
                continue
            pct_nav = None
            for col, mapped in col_map.items():
                if mapped == "percentage_to_nav":
                    raw = row.get(col, "")
                    if pd.notna(raw):
                        try:
                            pct_nav = float(str(raw).replace("%", "").replace(",", "").strip())
                        except ValueError:
                            pass
            mv_col = next((k for k, v in col_map.items() if v == "market_value"), None)
            market_value = row.get(mv_col, None) if mv_col is not None else None
            isin_col = next((k for k, v in col_map.items() if v == "isin"), None)
            isin = str(row.get(isin_col, "")).strip() if isin_col else ""
            sector_col = next((k for k, v in col_map.items() if v == "sector"), None)
            sector = str(row.get(sector_col, "")).strip() if sector_col else ""
            records.append({
                "security_name": security_name,
                "isin": isin if isin and isin != "nan" else None,
                "sector": sector if sector and sector != "nan" else None,
                "percentage_to_nav": pct_nav,
                "market_value": float(market_value) if pd.notna(market_value) else None,
                "row_number": int(idx),
            })
    except Exception as exc:
        errors.append("Portfolio CSV parse error: %s" % exc)
    records = _normalize_record_pct_units(records)
    return ParserResult(
        dataset_type="portfolio_disclosure",
        parser_name="portfolio_csv_v1",
        parser_version="1.0",
        confidence=0.7 if records else 0.0,
        records=records,
        warnings=warnings,
        errors=errors,
        metadata=metadata,
    )