"""Parser router."""
from __future__ import annotations

import logging
from typing import Any

from ..models import ParserResult


LOGGER = logging.getLogger(__name__)

PARSER_ROUTER: dict[tuple[str, str], str] = {
    # NAV parsers
    ("nav_history", "text"): "nav_text",
    ("nav_history", "csv"): "nav_csv",
    ("nav_history", "html"): "nav_html",
    ("nav_reference", "text"): "nav_text",
    # AMC parsers
    ("amc_provider_list", "html"): "amc_html",
    # Portfolio parsers
    ("portfolio_disclosure", "xlsx"): "portfolio_excel",
    ("portfolio_disclosure", "xls"): "portfolio_excel",
    ("portfolio_disclosure", "csv"): "portfolio_csv",
    # Scheme master parsers
    ("scheme_master", "csv"): "scheme_master_csv",
    ("scheme_master", "html"): "scheme_master_html",
}


def route_parser(dataset_type: str, file_type: str | None) -> str:
    if file_type:
        key = (dataset_type, file_type.lower())
        if key in PARSER_ROUTER:
            return PARSER_ROUTER[key]
    return "unknown"


def parse_file(dataset_type: str, file_type: str | None, content: bytes | str, metadata: dict[str, Any]) -> ParserResult:
    parser_name = route_parser(dataset_type, file_type)
    if parser_name == "nav_text":
        from .nav import parse_nav_text
        return parse_nav_text(content, metadata)
    elif parser_name == "nav_csv":
        from .nav import parse_nav_csv
        return parse_nav_csv(content, metadata)
    elif parser_name == "amc_html":
        from .amc import parse_amc_html
        return parse_amc_html(content, metadata)
    elif parser_name in ("portfolio_excel", "portfolio_csv"):
        from .portfolio import parse_portfolio_excel
        return parse_portfolio_excel(content, metadata)
    elif parser_name == "scheme_master_csv":
        from .scheme_master import parse_scheme_master_csv
        return parse_scheme_master_csv(content, metadata)
    elif parser_name == "scheme_master_html":
        from .scheme_master import parse_scheme_master_html
        return parse_scheme_master_html(content, metadata)
    return ParserResult(
        dataset_type=dataset_type,
        parser_name="unknown",
        parser_version="1.0",
        confidence=0.0,
        records=[],
        warnings=["No parser found for dataset_type=%s, file_type=%s" % (dataset_type, file_type)],
        errors=[],
        metadata=metadata,
    )