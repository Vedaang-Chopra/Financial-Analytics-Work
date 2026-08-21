"""Parser router."""
from __future__ import annotations

import logging
from typing import Any

from ..models import ParserResult


LOGGER = logging.getLogger(__name__)

PARSER_ROUTER: dict[tuple[str, str], str] = {
    # NAV parsers
    ("nav_history", "text"): "nav_text",
    ("nav_history", "txt"): "nav_text",
    ("nav_history", "csv"): "nav_csv",
    ("nav_history", "html"): "nav_html",
    ("nav_reference", "text"): "nav_text",
    ("nav_reference", "txt"): "nav_text",
    # AMC parsers
    ("amc_provider_list", "html"): "amc_html",
    # Portfolio parsers
    ("portfolio_disclosure", "xlsx"): "portfolio_excel",
    ("portfolio_disclosure", "xls"): "portfolio_excel",
    ("portfolio_disclosure", "csv"): "portfolio_csv",
    ("portfolio_disclosure", "zip"): "portfolio_zip",
    ("statutory_disclosure", "xlsx"): "portfolio_excel",
    ("statutory_disclosure", "xls"): "portfolio_excel",
    ("statutory_disclosure", "csv"): "portfolio_csv",
    ("statutory_disclosure", "zip"): "portfolio_zip",
    # Scheme master parsers
    ("scheme_master", "csv"): "scheme_master_csv",
    ("scheme_master", "html"): "scheme_master_html",
    # Metadata parsers (Q001)
    ("factsheet", "html"): "metadata_html",
    ("factsheet", "pdf"): "metadata_pdf",
    ("sid", "pdf"): "metadata_pdf",
    ("kim", "pdf"): "metadata_pdf",
    ("ter", "csv"): "ter_csv",
    ("aum_aaum", "csv"): "aum_csv",
}


def route_parser(dataset_type: str, file_type: str | None) -> str:
    if file_type:
        key = (dataset_type, file_type.lower())
        if key in PARSER_ROUTER:
            return PARSER_ROUTER[key]
    return "unknown"


def parse_file(dataset_type: str, file_type: str | None, content: bytes | str, metadata: dict[str, Any]) -> ParserResult:
    parser_name = route_parser(dataset_type, file_type)
    if parser_name == "unknown":
        LOGGER.warning("No parser for dataset_type=%s file_type=%s", dataset_type, file_type)
    else:
        LOGGER.info("Routing to parser=%s for dataset_type=%s file_type=%s", parser_name, dataset_type, file_type)
    if parser_name == "nav_text":
        from .nav import parse_nav_text
        return parse_nav_text(content, metadata)
    elif parser_name == "nav_csv":
        from .nav import parse_nav_csv
        return parse_nav_csv(content, metadata)
    elif parser_name == "nav_html":
        from .nav import parse_nav_html
        return parse_nav_html(content, metadata)
    elif parser_name == "amc_html":
        from .amc import parse_amc_html
        return parse_amc_html(content, metadata)
    elif parser_name == "portfolio_excel":
        from .portfolio import parse_portfolio_excel
        return parse_portfolio_excel(content, metadata)
    elif parser_name == "portfolio_csv":
        from .portfolio import parse_portfolio_csv
        return parse_portfolio_csv(content, metadata)
    elif parser_name == "portfolio_zip":
        from .portfolio import parse_portfolio_zip
        return parse_portfolio_zip(content, metadata)
    elif parser_name == "scheme_master_csv":
        from .scheme_master import parse_scheme_master_csv
        return parse_scheme_master_csv(content, metadata)
    elif parser_name == "scheme_master_html":
        from .scheme_master import parse_scheme_master_html
        return parse_scheme_master_html(content, metadata)
    elif parser_name in ("metadata_html", "metadata_pdf"):
        from .metadata import parse_metadata_html, parse_metadata_pdf
        if parser_name == "metadata_html":
            return parse_metadata_html(content, metadata)
        else:
            return parse_metadata_pdf(content, metadata)
    elif parser_name in ("ter_csv", "aum_csv"):
        from .metadata import parse_tabular_csv
        return parse_tabular_csv(content, metadata, dataset_type=dataset_type)
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