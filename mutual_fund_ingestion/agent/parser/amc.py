"""AMC provider list HTML parser."""
from __future__ import annotations

import re
from io import StringIO
from typing import Any

import pandas as pd

from ..models import ParserResult


def parse_amc_html(content: bytes | str, metadata: dict[str, Any]) -> ParserResult:
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")
    records = []
    errors = []
    anchor_pattern = re.compile(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
    for match in anchor_pattern.finditer(content):
        href, text = match.groups()
        text_clean = re.sub(r'<[^>]+>', '', text).strip()
        if not text_clean or len(text_clean) < 2:
            continue
        if "mutual fund" in text_clean.lower() or text_clean.endswith(" MF"):
            records.append({
                "name": text_clean,
                "website_url": href if href.startswith("http") else None,
                "source_url": metadata.get("source_url", ""),
            })
    return ParserResult(
        dataset_type="amc_provider_list",
        parser_name="amc_html_v1",
        parser_version="1.0",
        confidence=0.75 if records else 0.0,
        records=records,
        warnings=[],
        errors=errors,
        metadata=metadata,
    )