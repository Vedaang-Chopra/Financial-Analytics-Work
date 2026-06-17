"""AMFI Scheme Master CSV parser."""
from __future__ import annotations

import logging
from io import StringIO
from typing import Any

import pandas as pd

from ..models import ParserResult


LOGGER = logging.getLogger(__name__)


# AMFI scheme master CSV column aliases
SCHEME_MASTER_COLUMN_ALIASES = {
    "scheme_code": ["scheme code", "schemecode", "scheme_code", "code"],
    "scheme_name": ["scheme name", "schemename", "scheme_name", "name"],
    "amc_name": ["amc name", "amc", "fund house", "mutual fund", "amc_name"],
    "category": ["category", "fund category", "scheme category", "fund_category", "fundcategory"],
    "sub_category": ["sub category", "sub_category", "sub-category", "type", "subcategory"],
    "scheme_type": ["scheme type", "schemetype", "scheme_type"],
    "benchmark": ["benchmark", "benchmark index"],
}


def _normalize_scheme_master_col(col: str) -> str:
    """Normalize scheme master column name to standard field."""
    col_lower = col.strip().lower().replace(" ", "_").replace("-", "_")
    for target, aliases in SCHEME_MASTER_COLUMN_ALIASES.items():
        if col_lower in aliases:
            return target
    return col_lower


def _map_scheme_master_columns(df: pd.DataFrame) -> dict[str, str]:
    """Map dataframe columns to standard field names."""
    col_map = {}
    for col in df.columns:
        mapped = _normalize_scheme_master_col(str(col))
        col_map[col] = mapped
    return col_map


def parse_scheme_master_csv(content: bytes | str, metadata: dict[str, Any]) -> ParserResult:
    """Parse AMFI scheme master CSV file.
    
    Expected format (AMFI scheme master):
    Scheme Code,Scheme Name,AMC Name,Category,Sub Category,Scheme Type,Benchmark
    """
    records = []
    errors = []
    warnings = []
    
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")
    
    try:
        df = pd.read_csv(StringIO(content))
        col_map = _map_scheme_master_columns(df)
        
        for idx, row in df.iterrows():
            try:
                # Get mapped columns
                scheme_code_col = next((k for k, v in col_map.items() if v == "scheme_code"), None)
                scheme_name_col = next((k for k, v in col_map.items() if v == "scheme_name"), None)
                amc_name_col = next((k for k, v in col_map.items() if v == "amc_name"), None)
                category_col = next((k for k, v in col_map.items() if v == "category"), None)
                sub_category_col = next((k for k, v in col_map.items() if v == "sub_category"), None)
                scheme_type_col = next((k for k, v in col_map.items() if v == "scheme_type"), None)
                benchmark_col = next((k for k, v in col_map.items() if v == "benchmark"), None)
                
                scheme_code = str(row.get(scheme_code_col, "") or "").strip() if scheme_code_col else ""
                scheme_name = str(row.get(scheme_name_col, "") or "").strip() if scheme_name_col else ""
                amc_name = str(row.get(amc_name_col, "") or "").strip() if amc_name_col else ""
                category = str(row.get(category_col, "") or "").strip() if category_col else ""
                sub_category = str(row.get(sub_category_col, "") or "").strip() if sub_category_col else ""
                scheme_type = str(row.get(scheme_type_col, "") or "").strip() if scheme_type_col else ""
                benchmark = str(row.get(benchmark_col, "") or "").strip() if benchmark_col else ""
                
                if not scheme_name:
                    continue
                
                record = {
                    "scheme_code": scheme_code if scheme_code and scheme_code != "nan" else None,
                    "scheme_name": scheme_name,
                    "amc_name": amc_name if amc_name and amc_name != "nan" else None,
                    "category": category if category and category != "nan" else None,
                    "sub_category": sub_category if sub_category and sub_category != "nan" else None,
                    "scheme_type": scheme_type if scheme_type and scheme_type != "nan" else None,
                    "benchmark": benchmark if benchmark and benchmark != "nan" else None,
                    "source_url": metadata.get("source_url", ""),
                }
                records.append(record)
                
            except Exception as exc:
                errors.append(f"Row {idx}: {exc}")
                
    except Exception as exc:
        errors.append(f"CSV parse error: {exc}")
    
    return ParserResult(
        dataset_type="scheme_master",
        parser_name="scheme_master_csv_v1",
        parser_version="1.0",
        confidence=0.85 if records else 0.0,
        records=records,
        warnings=warnings,
        errors=errors,
        metadata=metadata,
    )


def parse_scheme_master_html(content: bytes | str, metadata: dict[str, Any]) -> ParserResult:
    """Parse scheme master from HTML table (fallback)."""
    records = []
    errors = []
    
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")
    
    # Try to parse HTML tables with pandas
    try:
        from io import StringIO
        tables = pd.read_html(StringIO(content))
        for table in tables:
            # Check if this looks like a scheme master table
            cols = [str(c).lower() for c in table.columns]
            if any("scheme" in c and "code" in c for c in cols) or any("scheme" in c and "name" in c for c in cols):
                # This looks like a scheme table
                col_map = _map_scheme_master_columns(table)
                
                for idx, row in table.iterrows():
                    try:
                        scheme_code_col = next((k for k, v in col_map.items() if v == "scheme_code"), None)
                        scheme_name_col = next((k for k, v in col_map.items() if v == "scheme_name"), None)
                        amc_name_col = next((k for k, v in col_map.items() if v == "amc_name"), None)
                        category_col = next((k for k, v in col_map.items() if v == "category"), None)
                        sub_category_col = next((k for k, v in col_map.items() if v == "sub_category"), None)
                        scheme_type_col = next((k for k, v in col_map.items() if v == "scheme_type"), None)
                        benchmark_col = next((k for k, v in col_map.items() if v == "benchmark"), None)
                        
                        scheme_code = str(row.get(scheme_code_col, "") or "").strip() if scheme_code_col else ""
                        scheme_name = str(row.get(scheme_name_col, "") or "").strip() if scheme_name_col else ""
                        amc_name = str(row.get(amc_name_col, "") or "").strip() if amc_name_col else ""
                        category = str(row.get(category_col, "") or "").strip() if category_col else ""
                        sub_category = str(row.get(sub_category_col, "") or "").strip() if sub_category_col else ""
                        scheme_type = str(row.get(scheme_type_col, "") or "").strip() if scheme_type_col else ""
                        benchmark = str(row.get(benchmark_col, "") or "").strip() if benchmark_col else ""
                        
                        if not scheme_name:
                            continue
                        
                        records.append({
                            "scheme_code": scheme_code if scheme_code and scheme_code != "nan" else None,
                            "scheme_name": scheme_name,
                            "amc_name": amc_name if amc_name and amc_name != "nan" else None,
                            "category": category if category and category != "nan" else None,
                            "sub_category": sub_category if sub_category and sub_category != "nan" else None,
                            "scheme_type": scheme_type if scheme_type and scheme_type != "nan" else None,
                            "benchmark": benchmark if benchmark and benchmark != "nan" else None,
                            "source_url": metadata.get("source_url", ""),
                        })
                    except Exception as exc:
                        errors.append(f"Row {idx}: {exc}")
                break
    except Exception as exc:
        errors.append(f"HTML table parse error: {exc}")
    
    return ParserResult(
        dataset_type="scheme_master",
        parser_name="scheme_master_html_v1",
        parser_version="1.0",
        confidence=0.7 if records else 0.0,
        records=records,
        warnings=[],
        errors=errors,
        metadata=metadata,
    )