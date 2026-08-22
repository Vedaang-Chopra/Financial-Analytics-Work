"""
Targeted Portfolio Ingestion Script

Uses AMC-specific navigators to directly fetch portfolio disclosure URLs,
download, parse, and upsert into PostgreSQL.
"""

from __future__ import annotations

import logging
import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import requests

# Add project root (parent of scripts/) to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mutual_fund_ingestion.agent.db import get_session_maker, QuarantineRow
from mutual_fund_ingestion.agent.upserts import UpsertManager
from mutual_fund_ingestion.agent.artifact_processor import ArtifactProcessor
from mutual_fund_ingestion.agent.parser import parse_file
from mutual_fund_ingestion.agent.validate import validate_and_filter_records
from mutual_fund_ingestion.agent.icici_navigator import extract_icici_portfolio_urls
from mutual_fund_ingestion.agent.portfolio_navigators import AMC_NAVIGATORS
from utils.http import HttpSettings, build_session

LOGGER = logging.getLogger(__name__)

# AMC-specific portfolio URL patterns
AMC_PORTFOLIO_CONFIGS = {
    "ppfas": {
        "name": "Parag Parikh Mutual Fund",
        "base_url": "https://amc.ppfas.com/downloads/",
        "method": "static_html",
        "file_pattern": "xlsx",
    },
    "mirae_asset": {
        "name": "Mirae Asset Mutual Fund",
        "base_url": "https://www.miraeassetmf.co.in/downloads/portfolio",
        "method": "playwright",
        "file_pattern": "xlsx",
    },
    "dsp": {
        "name": "DSP Mutual Fund",
        "base_url": "https://www.dspim.com/mandatory-disclosures/portfolio-disclosures",
        "method": "static_html",
        "file_pattern": "xlsx",
    },
    "invesco": {
        "name": "Invesco Mutual Fund",
        "base_url": "https://www.invescomutualfund.com/literature-and-form?tab=Fortnightly",
        "method": "playwright",
        "file_pattern": "xlsx",
    },
    "icici_prudential": {
        "name": "ICICI Prudential Mutual Fund",
        "base_url": "https://www.icicipruamc.com/media-center/downloads?currentTabFilter=OtherSchemeDisclosures&&subCatTabFilter=FortnightlyPortfolioDisclosures",
        "method": "playwright",
        "file_pattern": "zip",
        "financial_years": ["2026-2027", "2025-2026"],
    },
    "aditya_birla": {
        "name": "Aditya Birla Sun Life Mutual Fund",
        "base_url": "https://mutualfund.adityabirlacapital.com/portfolio",
        "method": "playwright",
        "file_pattern": "zip",
    },
    "lic": {
        "name": "LIC Mutual Fund",
        "base_url": "https://www.licmf.com/downloads/monthly-portfolio",
        "method": "playwright",
        "file_pattern": "xlsx",
    },
    "axis": {
        "name": "Axis Mutual Fund",
        "base_url": "https://transact.axismf.com/statutory-disclosures",
        "method": "playwright",
        "file_pattern": "xlsx",
    },
    "sbi": {
        "name": "SBI Mutual Fund",
        "base_url": "https://www.sbimf.com/portfolios",
        "method": "network_api",
        "file_pattern": "xlsx",
    },
    "hdfc": {
        "name": "HDFC Mutual Fund",
        "base_url": "https://www.hdfcfund.com/statutory-disclosure/portfolio/monthly-portfolio",
        "method": "static_html",
        "file_pattern": "xlsx",
    },
    "nippon_india": {
        "name": "Nippon India Mutual Fund",
        "base_url": "https://mf.nipponindiaim.com/investor-service/downloads/factsheet-portfolio-and-other-disclosures",
        "method": "static_html",
        "file_pattern": "xls",
    },
    "uti": {
        "name": "UTI Mutual Fund",
        "base_url": "https://www.utimf.com/downloads/consolidate-debt-portfolio-disclosure",
        "method": "network_api",
        "file_pattern": "zip",
    },
    "franklin_templeton": {
        "name": "Franklin Templeton Mutual Fund",
        "base_url": "https://www.franklintempletonindia.com/investor/reports?firstFilter-10",
        "method": "network_api",
        "file_pattern": "xls",
    },
}


def get_mirae_portfolio_urls():  # legacy alias → see portfolio_navigators
    """Deprecated: kept for back-compat. Use portfolio_navigators.AMC_NAVIGATORS."""
    from mutual_fund_ingestion.agent.portfolio_navigators import get_mirae_portfolio_urls as _impl
    return _impl()


def get_dsp_portfolio_urls():  # legacy alias → see portfolio_navigators
    """Deprecated: kept for back-compat. Use portfolio_navigators.AMC_NAVIGATORS."""
    from mutual_fund_ingestion.agent.portfolio_navigators import get_dsp_portfolio_urls as _impl
    return _impl()


def get_invesco_portfolio_urls():  # legacy alias → see portfolio_navigators
    """Deprecated: kept for back-compat. Use portfolio_navigators.AMC_NAVIGATORS."""
    from mutual_fund_ingestion.agent.portfolio_navigators import get_invesco_portfolio_urls as _impl
    return _impl()


def _reporting_date_from_url(url: str) -> str | None:
    """Derive reporting_date from disclosure filename when the sheet lacks one.

    LIC (and some other AMCs) embed the as-of date only in the filename:
      ...as-on-28-February-2013.xls / ...as-on-October-31,2016.xls
      MONTHLY_PORTFOLIO-30-11-2016.xls / Portfolio-Monthly-31122018.xls
      LIC MF Fortnightly Portfolio_Dec-23.xlsx  (month granularity -> month end)
    Without this fallback upserts.py defaults every record to date.today(),
    collapsing all periods into one snapshot.
    """
    import re
    from calendar import monthrange
    from urllib.parse import unquote

    name = unquote(url.split("?")[0].rsplit("/", 1)[-1])
    months = {}
    for i, m in enumerate(
        ["January", "February", "March", "April", "May", "June", "July",
         "August", "September", "October", "November", "December"], start=1):
        months[m.lower()] = i
        months[m.lower()[:3]] = i
        months[m.lower()[:4]] = i  # sept / june-style variants resolve too

    # "...as-on-28-February-2013" or "...as on October-31,2016"
    m = re.search(r"as[-_ ]?on[-_ ]?(?:([A-Za-z]+)[-_ ]?(\d{1,2}),?-?(\d{4})|(\d{1,2})[-_ ]([A-Za-z]+)[-_ ](\d{4}))", name, re.IGNORECASE)
    if m:
        if m.group(1):
            mon = months.get(m.group(1).lower())
            if mon:
                return date(int(m.group(3)), mon, int(m.group(2))).isoformat()
        else:
            mon = months.get(m.group(5).lower())
            if mon:
                return date(int(m.group(6)), mon, int(m.group(4))).isoformat()

    # "-30-11-2016" style tail before extension
    m = re.search(r"[-_ ](\d{1,2})-(\d{1,2})-(\d{4})(?:[^\d]|$)", name)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
        except ValueError:
            pass

    # "-31122018" compact style before extension/separator
    m = re.search(r"[-_ ](\d{2})(\d{2})(\d{4})(?:\.\w+)?$|[-_ ](\d{2})(\d{2})(\d{4})[-_ ]", name)
    if m:
        d, mo, y = (m.group(1), m.group(2), m.group(3)) if m.group(1) else (m.group(4), m.group(5), m.group(6))
        try:
            return date(int(y), int(mo), int(d)).isoformat()
        except ValueError:
            pass

    # "_Dec-23" / "_Feb-22" month-year granularity -> last day of month
    m = re.search(r"[_ -]([A-Za-z]{3,9})[-_ ](\d{2})(?:\.\w+)?$", name)
    if m:
        mon = months.get(m.group(1).lower()[:3]) or months.get(m.group(1).lower())
        if mon:
            y = 2000 + int(m.group(2))
            return date(y, mon, monthrange(y, mon)[1]).isoformat()
    return None


def download_and_parse(url: str, amc_name: str, run_id: str, session_maker, upsert_manager: UpsertManager, stats: dict, extra_metadata: dict | None = None) -> int:
    """Download a file, parse it, and upsert records."""
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
    
    try:
        LOGGER.info("Downloading %s", url)
        resp = requests.get(url, headers=headers, timeout=120)
        resp.raise_for_status()
        
        content = resp.content
        content_type = resp.headers.get('Content-Type', '')
        
        # Determine file type from URL (handle query params)
        from utils.url_utils import file_type_from_url
        file_type = file_type_from_url(url) or 'unknown'
        
        LOGGER.info("Downloaded %s: %d bytes, type=%s", url, len(content), file_type)
        stats['files_downloaded'] = stats.get('files_downloaded', 0) + 1
        
        # Parse
        metadata = {'source_url': url, 'amc_name': amc_name, 'run_id': run_id, **(extra_metadata or {})}
        result = parse_file('portfolio_disclosure', file_type, content, metadata)
        
        LOGGER.info("Parser %s returned %d records (confidence=%.2f)", 
                   result.parser_name, len(result.records), result.confidence)
        
        if result.confidence == 0.0 or not result.records:
            LOGGER.warning("No valid records from %s", url)
            return 0

        # Fallback: fill missing reporting_date from the disclosure filename.
        # Without it upserts.py stamps date.today() and all periods collapse
        # into a single snapshot (seen with LIC monthly/fortnightly files).
        url_date = _reporting_date_from_url(url)
        if url_date:
            filled = sum(
                1 for r in result.records
                if not r.get("reporting_date") and not r.get("date")
            )
            if filled:
                for r in result.records:
                    if not r.get("reporting_date") and not r.get("date"):
                        r["reporting_date"] = url_date
                LOGGER.info("Filled reporting_date=%s from filename for %d/%d records (%s)",
                            url_date, filled, len(result.records), url)

        stats['artifacts_parsed'] = stats.get('artifacts_parsed', 0) + 1
        
        # Upsert using a session
        session = session_maker()
        try:
            from mutual_fund_ingestion.agent.db import RawArtifact, StagingRow
            
            # Persist raw artifact
            raw_artifact = RawArtifact(
                run_id=uuid.UUID(run_id),
                source_url=url,
                artifact_type="file",
                file_type=file_type,
                content_type=content_type,
                size_bytes=len(content),
            )
            session.add(raw_artifact)
            session.flush()
            
            # Stage records
            for i, record in enumerate(result.records):
                staging_row = StagingRow(
                    run_id=uuid.UUID(run_id),
                    raw_artifact_id=raw_artifact.id,
                    dataset_type="portfolio_disclosure",
                    sheet_name=record.get("sheet_name"),
                    row_number=i + 1,
                    raw_row_json=record,
                    parsed_fields_json=record,
                    parser_name=result.parser_name,
                    parser_confidence=result.confidence,
                )
                session.add(staging_row)
            
            session.flush()
            stats['rows_staged'] = stats.get('rows_staged', 0) + len(result.records)
            
            # Validate -> quarantine -> canonical (same path as ArtifactProcessor).
            # Invalid rows land in quarantine_rows, never in canonical tables.
            upsert_manager.set_run_id(run_id)
            valid_records, quarantined_records, snapshot_warnings = validate_and_filter_records(
                result, run_id, return_warnings=True
            )
            
            LOGGER.info(
                "Validation for %s: %d valid, %d quarantined, %d snapshot warnings",
                url, len(valid_records), len(quarantined_records), len(snapshot_warnings),
            )
            
            for quarantined in quarantined_records:
                upsert_manager.write_validation_result(
                    session,
                    entity_type="portfolio_disclosure",
                    check_name="schema_validation",
                    severity="error",
                    status="failed",
                    message=quarantined.get("reason", "validation failed"),
                )
                session.add(QuarantineRow(
                    run_id=uuid.UUID(run_id),
                    raw_artifact_id=raw_artifact.id,
                    dataset_type="portfolio_disclosure",
                    reason=quarantined.get("reason", "unknown"),
                    raw_data_json=quarantined.get("raw_data_json"),
                    parser_error=quarantined.get("parser_error"),
                    retryable=quarantined.get("retryable", False),
                ))
                stats['rows_quarantined'] = stats.get('rows_quarantined', 0) + 1
            
            # Snapshot-level WARN gate: pct-to-NAV sums outside bounds are
            # logged to validation_results but never drop rows.
            for warning in snapshot_warnings:
                upsert_manager.write_validation_result(
                    session,
                    entity_type="portfolio_disclosure",
                    check_name=warning.get("check_name", "snapshot_pct_sum"),
                    severity=warning.get("severity", "warn"),
                    status=warning.get("status", "warning"),
                    message=warning.get("message"),
                )
            if snapshot_warnings:
                stats['snapshot_warnings'] = stats.get('snapshot_warnings', 0) + len(snapshot_warnings)
            
            # Upsert only VALID records to canonical tables
            upsert_manager.upsert_canonical(
                session,
                valid_records,
                "portfolio_disclosure",
                raw_artifact.id,
                url,
                stats,
                amc_name=amc_name,
            )
            
            session.commit()
            inserted = stats.get('rows_inserted', 0)
            LOGGER.info("Upserted %d records for %s", inserted, url)
            return inserted
            
        finally:
            session.close()
            
    except Exception as e:
        LOGGER.error("Failed to process %s: %s", url, e)
        stats['errors'] = stats.get('errors', 0) + 1
        return 0


def ingest_amc(amc_key: str, config: dict, session_maker, upsert_manager: UpsertManager, run_id: str, max_files: int = 20) -> dict:
    """Ingest portfolio data for one AMC."""
    stats = {
        'files_downloaded': 0,
        'artifacts_parsed': 0,
        'rows_staged': 0,
        'rows_inserted': 0,
        'errors': 0,
    }
    
    LOGGER.info("=" * 60)
    LOGGER.info("Starting ingestion for %s (%s)", config['name'], amc_key)
    LOGGER.info("=" * 60)
    
    # Get URLs based on method
    if amc_key == "icici_prudential":
        urls = extract_icici_portfolio_urls(
            financial_years=config.get('financial_years', ["2026-2027", "2025-2026"]),
            headless=True,
        )
        # Flatten
        all_urls = []
        for year_urls in urls.values():
            all_urls.extend(year_urls)
        urls = sorted(all_urls)[:max_files]  # sort: deterministic sampling
    elif amc_key in AMC_NAVIGATORS and AMC_NAVIGATORS[amc_key] is not None:
        navigator = AMC_NAVIGATORS[amc_key]
        urls = sorted(navigator())[:max_files]  # sort: deterministic sampling
    else:
        LOGGER.warning("Unknown AMC: %s", amc_key)
        return stats
    
    LOGGER.info("Found %d portfolio URLs for %s", len(urls), config['name'])
    
    # Process each URL
    for i, url in enumerate(urls):
        LOGGER.info("Processing %d/%d: %s", i + 1, len(urls), url)
        download_and_parse(url, config['name'], run_id, session_maker, upsert_manager, stats)
    
    return stats


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Targeted portfolio ingestion for AMCs")
    parser.add_argument("--database-url", required=True, help="PostgreSQL connection URL")
    parser.add_argument("--amcs", nargs="+", choices=list(AMC_PORTFOLIO_CONFIGS.keys()) + ["all"], 
                       default=["all"], help="AMCs to ingest")
    parser.add_argument("--max-files", type=int, default=20, help="Max files per AMC")
    parser.add_argument("--log-level", default="INFO", help="Log level")
    args = parser.parse_args()
    
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    
    # Database setup
    session_maker = get_session_maker(args.database_url)
    upsert_manager = UpsertManager()
    
    # Create ingestion run record
    run_id = str(uuid.uuid4())
    session = session_maker()
    try:
        from mutual_fund_ingestion.agent.db import IngestionRun
        run = IngestionRun(
            id=uuid.UUID(run_id),
            started_at=datetime.now(timezone.utc),
            status="running",
            config_json={"amcs": args.amcs, "max_files": args.max_files},
        )
        session.add(run)
        session.commit()
    finally:
        session.close()
    
    # Determine which AMCs to process
    if "all" in args.amcs:
        amcs_to_process = list(AMC_PORTFOLIO_CONFIGS.keys())
    else:
        amcs_to_process = args.amcs
    
    total_stats = {
        'files_downloaded': 0,
        'artifacts_parsed': 0,
        'rows_staged': 0,
        'rows_inserted': 0,
        'errors': 0,
    }
    
    for amc_key in amcs_to_process:
        config = AMC_PORTFOLIO_CONFIGS[amc_key]
        try:
            stats = ingest_amc(amc_key, config, session_maker, upsert_manager, run_id, args.max_files)
            for k, v in stats.items():
                total_stats[k] = total_stats.get(k, 0) + v
        except Exception as e:
            LOGGER.error("Failed to ingest %s: %s", amc_key, e)
            total_stats['errors'] = total_stats.get('errors', 0) + 1
    
    # Update run record
    session = session_maker()
    try:
        from mutual_fund_ingestion.agent.db import IngestionRun
        run = session.query(IngestionRun).filter(IngestionRun.id == uuid.UUID(run_id)).first()
        if run:
            run.finished_at = datetime.now(timezone.utc)
            run.status = "completed"
            run.files_seen = total_stats['files_downloaded']
            run.rows_inserted = total_stats['rows_inserted']
            run.rows_rejected = total_stats['errors']
            run.error_summary = {"errors": total_stats['errors']}
            session.commit()
    finally:
        session.close()
    
    LOGGER.info("=" * 60)
    LOGGER.info("INGESTION COMPLETE")
    LOGGER.info("=" * 60)
    LOGGER.info("Files downloaded: %d", total_stats['files_downloaded'])
    LOGGER.info("Artifacts parsed: %d", total_stats['artifacts_parsed'])
    LOGGER.info("Rows staged: %d", total_stats['rows_staged'])
    LOGGER.info("Rows inserted: %d", total_stats['rows_inserted'])
    LOGGER.info("Errors: %d", total_stats['errors'])


if __name__ == "__main__":
    main()