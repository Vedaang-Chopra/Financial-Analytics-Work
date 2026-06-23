"""Metadata parsers for factsheet, SID, KIM, TER, AUM documents."""
from __future__ import annotations

import logging
from typing import Any

import pandas as pd
from io import StringIO

from ..models import ParserResult

LOGGER = logging.getLogger(__name__)


def parse_metadata_html(content: bytes | str, metadata: dict[str, Any]) -> ParserResult:
    """Extract document metadata from a factsheet or SID HTML page."""
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")
    records = [{"document_type": metadata.get("dataset_type", "factsheet"),
                "source_url": metadata.get("source_url", ""),
                "raw_html_length": len(content)}]
    return ParserResult(
        dataset_type=metadata.get("dataset_type", "factsheet"),
        parser_name="metadata_html_v1", parser_version="1.0",
        confidence=0.5, records=records, warnings=["metadata_html is a stub parser"],
        errors=[], metadata=metadata,
    )


def parse_metadata_pdf(content: bytes | str, metadata: dict[str, Any]) -> ParserResult:
    """PDF metadata parser stub — returns quarantine-ready result until PDF parsing is implemented."""
    return ParserResult(
        dataset_type=metadata.get("dataset_type", "factsheet"),
        parser_name="metadata_pdf_v1", parser_version="1.0",
        confidence=0.0, records=[],
        warnings=["PDF parsing not yet implemented; file retained for manual review"],
        errors=[], metadata=metadata,
    )


def parse_tabular_csv(content: bytes | str, metadata: dict[str, Any], dataset_type: str = "ter") -> ParserResult:
    """Parse TER or AUM/AAUM tabular CSV."""
    records = []
    errors = []
    try:
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")
        df = pd.read_csv(StringIO(content), dtype=str)
        for _, row in df.iterrows():
            records.append({**row.dropna().to_dict(), "source_url": metadata.get("source_url", "")})
    except Exception as exc:
        errors.append(f"Tabular CSV parse error: {exc}")
    return ParserResult(
        dataset_type=dataset_type, parser_name=f"{dataset_type}_csv_v1", parser_version="1.0",
        confidence=0.6 if records else 0.0, records=records, warnings=[], errors=errors, metadata=metadata,
    )
