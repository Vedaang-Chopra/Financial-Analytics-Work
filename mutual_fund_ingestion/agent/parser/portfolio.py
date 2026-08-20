"""Excel/CSV portfolio disclosure parser."""
from __future__ import annotations

import logging
from datetime import datetime
from io import BytesIO
from typing import Any

import pandas as pd

from ..models import ParserResult


LOGGER = logging.getLogger(__name__)

COLUMN_ALIASES = {
    "security_name": ["name of instrument", "security", "company", "name", "instrument", "scrip", "security_name"],
    "isin": ["isin", "isin code", "isin no"],
    "quantity": ["quantity", "no. of shares", "units", "face value", "nos"],
    "market_value": ["market value", "value", "market value (rs. in lakhs)", "fair value", "amount"],
    "percentage_to_nav": ["% to nav", "% net assets", "percentage", "% of net assets", "percentage to nav"],
    "sector": ["industry", "sector", "rating/industry", "sector/industry"],
    "rating": ["rating", "credit rating"],
    "maturity_date": ["maturity", "maturity date"],
    "coupon": ["coupon", "coupon rate"],
    "asset_class": ["asset class", "type"],
}


def _normalize_col(col: str) -> str:
    col_lower = col.strip().lower()
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
    for fmt in ["%d-%b-%Y", "%b %Y", "%Y-%m-%d", "%d/%m/%Y", "%B %Y"]:
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def parse_portfolio_excel(content: bytes | str, metadata: dict[str, Any]) -> ParserResult:
    records = []
    errors = []
    warnings = []
    if isinstance(content, str):
        content = content.encode("utf-8")
    try:
        xlsx = pd.ExcelFile(BytesIO(content))
        for sheet_name in xlsx.sheet_names:
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
                        # Look for scheme name patterns
                        if scheme_name is None and any(kw in cell_str.lower() for kw in ["portfolio", "fund", "scheme"]):
                            scheme_name = cell_str
                        # Look for date patterns
                        if reporting_date is None:
                            for fmt in ["%d-%b-%Y", "%b %Y", "%Y-%m-%d", "%d/%m/%Y", "%B %Y", "%d-%m-%Y"]:
                                try:
                                    reporting_date = datetime.strptime(cell_str, fmt).date().isoformat()
                                    break
                                except ValueError:
                                    continue

            # Re-read with detected header row
            df = pd.read_excel(xlsx, sheet_name=sheet_name, header=header_row_idx, dtype=str)

            # Normalize column names
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
                
                # Use sheet_name as scheme_name if not found
                final_scheme_name = scheme_name or sheet_name
                
                records.append({
                    "security_name": security_name,
                    "isin": isin if isin and isin != "nan" else None,
                    "sector": sector if sector and sector != "nan" else None,
                    "percentage_to_nav": pct_nav,
                    "market_value": float(market_value) if pd.notna(market_value) else None,
                    "sheet_name": sheet_name,
                    "row_number": int(idx),
                    "scheme_name": final_scheme_name,
                    "reporting_date": reporting_date,
                })
    except Exception as exc:
        errors.append("Portfolio parse error: %s" % exc)
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
                            pct_nav = float(str(raw).replace("%%", "").replace(",", "").strip())
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