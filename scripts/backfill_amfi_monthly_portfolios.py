"""Backfill AMFI monthly portfolio disclosures into canonical PostgreSQL.

Discovery (verified live): AMFI's Portfolio Disclosure page
https://www.amfiindia.com/online-center/portfolio-disclosure embeds a
per-AMC ``members`` list in its Next.js RSC payload. Each member carries an
``amc_monthly_portfolio_disclosure`` field pointing at the AMC's monthly
portfolio landing page. The fetcher:

1. Fetches the AMFI page and extracts all monthly-portfolio disclosure URLs.
2. For each landing page (optionally limited by --max-pages), extracts direct
   portfolio file links (.xlsx/.xls/.zip).
3. Downloads files sequentially and politely (UA header, >=1s sleep, timeouts).
4. Parses each file with the portfolio_monthly_amfi parser, validates, and
   upserts canonical snapshots/holdings (same path as
   scripts/targeted_portfolio_ingestion.py).

Usage:
    ./financial_env/bin/python scripts/backfill_amfi_monthly_portfolios.py \
        --max-files 2
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

LOGGER = logging.getLogger("backfill_amfi_monthly_portfolios")

AMFI_DISCLOSURE_PAGE = "https://www.amfiindia.com/online-center/portfolio-disclosure"
USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36")
REQUEST_TIMEOUT = 60
POLITE_SLEEP_SECONDS = 1.5
FILE_LINK_RE = re.compile(
    r'href=["\']([^"\']+\.(?:xlsx?|zip)(?:\?[^"\']*)?)["\']', re.IGNORECASE)
MONTH_HINT_RE = re.compile(r"portfol", re.IGNORECASE)
FILE_EXCLUDE_RE = re.compile(r"(aaum|aum|factsheet|nav|kim|sid|term-sheet)", re.IGNORECASE)


def build_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT,
                      "Accept": "text/html,application/xhtml+xml,"
                                "application/vnd.ms-excel,"
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*"})
    return s


def discover_monthly_disclosure_urls(session: requests.Session) -> list[dict]:
    """Extract per-AMC monthly portfolio disclosure URLs from the AMFI page.

    Returns a list of {"mf_name", "amc_name", "url"} dicts, deduped, sorted.
    """
    resp = session.get(AMFI_DISCLOSURE_PAGE, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    html = resp.text
    # RSC flight payloads live in self.__next_f.push([1,"..."]) script tags
    chunks = re.findall(r'self\.__next_f\.push\(\[1,(".*?")\]\)</script>',
                        html, re.S)
    blob = "".join(json.loads(c) for c in chunks) if chunks else html
    members = re.findall(
        r'\{\s*\\?"mf_id\\?"\s*:\s*\\?"(\d+)\\?"\s*,\s*\\?"mf_name\\?"\s*:\s*\\?"([^"\\]+)\\?"'
        r'.*?\\?"amc_monthly_portfolio_disclosure\\?"\s*:\s*\\?"(https?://[^"\\]+)\\?"',
        blob, re.S)
    seen: set[str] = set()
    out: list[dict] = []
    for mf_id, mf_name, url in members:
        url = url.strip().rstrip("/")
        if not url or url in seen or url.endswith("#"):
            continue
        seen.add(url)
        out.append({"mf_id": mf_id, "mf_name": mf_name, "url": url})
    out.sort(key=lambda m: m["mf_name"].lower())
    return out


def discover_file_links(session: requests.Session, landing_url: str) -> list[str]:
    """Extract direct portfolio-file links from an AMC landing page."""
    try:
        resp = session.get(landing_url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except Exception as exc:
        LOGGER.warning("Landing page failed %s: %s", landing_url, exc)
        return []
    links = []
    for m in FILE_LINK_RE.finditer(resp.text):
        href = urljoin(resp.url, m.group(1))
        if MONTH_HINT_RE.search(href) and not FILE_EXCLUDE_RE.search(href):
            links.append(href)
    # Dedupe, preserve order
    seen = set()
    unique = []
    for l in links:
        if l not in seen:
            seen.add(l)
            unique.append(l)
    return unique


def file_type_for_parser(url: str) -> str:
    """Map a URL to the router's amfi_monthly file-type keys."""
    path = urlparse(url).path.lower()
    if path.endswith(".xls"):
        return "amfi_monthly_xls"
    return "amfi_monthly_xlsx"


def process_file(url: str, amc_name: str, run_id: str, session: requests.Session,
                 session_maker, upsert_manager, stats: dict) -> int:
    """Download -> parse -> validate -> upsert canonical (mirrors
    targeted_portfolio_ingestion.download_and_parse but forces the
    portfolio_monthly_amfi parser)."""
    from mutual_fund_ingestion.agent.db import QuarantineRow, RawArtifact, StagingRow
    from mutual_fund_ingestion.agent.parser import parse_file
    from mutual_fund_ingestion.agent.validate import validate_and_filter_records

    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        content = resp.content
        content_type = resp.headers.get("Content-Type", "")
        stats["files_downloaded"] += 1
        LOGGER.info("Downloaded %s: %d bytes (%s)", url, len(content), content_type)

        file_type = file_type_for_parser(url)
        metadata = {"source_url": url, "amc_name": amc_name, "run_id": run_id}
        result = parse_file("portfolio_disclosure", file_type, content, metadata)
        LOGGER.info("Parser %s: %d records (confidence=%.2f), %d errors",
                    result.parser_name, len(result.records), result.confidence,
                    len(result.errors))
        if not result.records:
            stats["files_no_records"] += 1
            return 0
        stats["artifacts_parsed"] += 1

        sess = session_maker()
        try:
            raw_artifact = RawArtifact(
                run_id=uuid.UUID(run_id),
                source_url=url,
                artifact_type="file",
                file_type=file_type,
                content_type=content_type,
                size_bytes=len(content),
            )
            sess.add(raw_artifact)
            sess.flush()

            for i, record in enumerate(result.records):
                sess.add(StagingRow(
                    run_id=uuid.UUID(run_id),
                    raw_artifact_id=raw_artifact.id,
                    dataset_type="portfolio_disclosure",
                    sheet_name=record.get("sheet_name"),
                    row_number=i + 1,
                    raw_row_json=record,
                    parsed_fields_json=record,
                    parser_name=result.parser_name,
                    parser_confidence=result.confidence,
                ))
            sess.flush()
            stats["rows_staged"] += len(result.records)

            upsert_manager.set_run_id(run_id)
            valid_records, quarantined_records, snapshot_warnings = \
                validate_and_filter_records(result, run_id, return_warnings=True)
            LOGGER.info("Validation %s: %d valid, %d quarantined",
                        url, len(valid_records), len(quarantined_records))

            for q in quarantined_records:
                upsert_manager.write_validation_result(
                    sess, entity_type="portfolio_disclosure",
                    check_name="schema_validation", severity="error",
                    status="failed",
                    message=q.get("reason", "validation failed"))
                sess.add(QuarantineRow(
                    run_id=uuid.UUID(run_id),
                    raw_artifact_id=raw_artifact.id,
                    dataset_type="portfolio_disclosure",
                    reason=q.get("reason", "unknown"),
                    raw_data_json=q.get("raw_data_json"),
                    parser_error=q.get("parser_error"),
                    retryable=q.get("retryable", False),
                ))
                stats["rows_quarantined"] += 1
            for w in snapshot_warnings:
                upsert_manager.write_validation_result(
                    sess, entity_type="portfolio_disclosure",
                    check_name=w.get("check_name", "snapshot_pct_sum"),
                    severity=w.get("severity", "warn"),
                    status=w.get("status", "warning"),
                    message=w.get("message"))
                stats["snapshot_warnings"] += 1

            upsert_manager.upsert_canonical(
                sess, valid_records, "portfolio_disclosure",
                raw_artifact.id, url, stats, amc_name=amc_name)

            # Provenance stamp: persist source_dataset=amfi_monthly onto the
            # canonical snapshots this file just upserted. portfolio_snapshots
            # has no source_dataset column and its metadata_json is a plain
            # `json` column, so merge through ::jsonb and cast back. Merge-only
            # (||) — never wipes existing keys. History-preserving.
            sess.execute(text(
                "UPDATE portfolio_snapshots ps "
                "SET metadata_json = ("
                "  COALESCE(ps.metadata_json, '{}'::json)::jsonb"
                "  || jsonb_build_object("
                "    'source_dataset', 'amfi_monthly',"
                "    'source_run_id', :run_id,"
                "    'provenance_source_url', :src_url)"
                ")::json "
                "FROM documents d "
                "WHERE ps.document_id = d.id "
                "  AND d.raw_artifact_id = :artifact_id"),
                {"run_id": run_id, "src_url": url,
                 "artifact_id": raw_artifact.id})

            sess.commit()
            return len(valid_records)
        finally:
            sess.close()
    except Exception as exc:
        LOGGER.error("Failed to process %s: %s", url, exc)
        stats["errors"] += 1
        return -1


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--database-url", default=None,
                    help="Overrides MF_DATABASE_URL/api.env resolution (db_config.py)")
    ap.add_argument("--max-pages", type=int, default=3,
                    help="Max AMC landing pages to scan for file links")
    ap.add_argument("--max-files", type=int, default=2,
                    help="Max portfolio files to download and ingest")
    ap.add_argument("--per-page", type=int, default=0,
                    help="Max files taken from any single landing page (0 = no cap)")
    ap.add_argument("--members-start", type=int, default=0,
                    help="Start index into the sorted AMC member list (chunking)")
    ap.add_argument("--members-end", type=int, default=0,
                    help="Exclusive end index into the sorted member list (0 = through last)")
    ap.add_argument("--state-file", default=None,
                    help="JSON checkpoint of completed URLs; completed URLs are "
                         "skipped on resume so chunks can be re-run safely")
    ap.add_argument("--sleep", type=float, default=POLITE_SLEEP_SECONDS)
    ap.add_argument("--log-level", default="INFO")
    args = ap.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level.upper()),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    from mutual_fund_ingestion.agent.db import IngestionRun, get_session_maker
    from mutual_fund_ingestion.agent.upserts import UpsertManager

    session = build_session()

    # Step 1: discovery from AMFI monthly reports page
    LOGGER.info("Discovering monthly portfolio disclosure URLs from %s",
                AMFI_DISCLOSURE_PAGE)
    try:
        members = discover_monthly_disclosure_urls(session)
    except Exception as exc:
        LOGGER.error("AMFI DISCOVERY FAILED (honest failure, no fabrication): %s", exc)
        members = []
    LOGGER.info("Discovered %d AMC monthly-portfolio disclosure URLs", len(members))
    for m in members[:10]:
        LOGGER.info("  %s -> %s", m["mf_name"], m["url"])
    if not members:
        LOGGER.error("No disclosure URLs discovered — aborting before download step.")
        sys.exit(2)
    total_members = len(members)
    members = members[args.members_start:args.members_end or None]
    LOGGER.info("Member slice [%d:%s]: %d of %d AMCs in this chunk",
                args.members_start, args.members_end or "end",
                len(members), total_members)

    # Resume state: URLs already successfully ingested by a previous chunk.
    state_path = Path(args.state_file) if args.state_file else None
    done_urls: set[str] = set()
    if state_path and state_path.exists():
        try:
            done_urls = set(json.loads(state_path.read_text()).get("done", []))
            LOGGER.info("Resume state: %d URLs already completed", len(done_urls))
        except Exception as exc:
            LOGGER.warning("Could not read state file %s: %s — starting fresh",
                           state_path, exc)

    time.sleep(args.sleep)

    # Step 2: collect file links from the first --max-pages landing pages
    file_jobs: list[tuple[str, str]] = []
    for m in members:
        if args.max_files and len(file_jobs) >= args.max_files:
            break
        if args.max_pages and len({u for u, _ in file_jobs}) >= args.max_pages:
            break
        links = discover_file_links(session, m["url"])
        LOGGER.info("Landing page %s (%s): %d file links", m["url"], m["mf_name"], len(links))
        taken = 0
        for link in links:
            if link in done_urls:
                continue
            if args.max_files and len(file_jobs) >= args.max_files:
                break
            if args.per_page and taken >= args.per_page:
                break
            file_jobs.append((link, m["mf_name"]))
            taken += 1
        time.sleep(args.sleep)

    if not file_jobs:
        LOGGER.error("No downloadable portfolio files found on scanned landing pages.")
        sys.exit(3)
    LOGGER.info("Will ingest %d files", len(file_jobs))

    # Step 3: ingestion run + upsert loop
    from db_config import mutual_funds_url

    session_maker = get_session_maker(args.database_url or mutual_funds_url())
    upsert_manager = UpsertManager()
    run_id = str(uuid.uuid4())
    sess = session_maker()
    try:
        sess.add(IngestionRun(
            id=uuid.UUID(run_id),
            started_at=datetime.now(timezone.utc),
            status="running",
            config_json={"max_pages": args.max_pages, "max_files": args.max_files,
                         "source": "amfi_monthly_portfolios"},
        ))
        sess.commit()
    finally:
        sess.close()

    stats = {"files_downloaded": 0, "artifacts_parsed": 0, "rows_staged": 0,
             "rows_quarantined": 0, "snapshot_warnings": 0, "errors": 0,
             "files_no_records": 0}
    pending_jobs = [(u, a) for (u, a) in file_jobs if u not in done_urls]
    LOGGER.info("Will ingest %d files (%d skipped as already done)",
                len(pending_jobs), len(file_jobs) - len(pending_jobs))
    for i, (url, amc) in enumerate(pending_jobs, 1):
        LOGGER.info("Processing %d/%d: %s", i, len(pending_jobs), url)
        rc = process_file(url, amc, run_id, session, session_maker,
                          upsert_manager, stats)
        # Checkpoint successful ingests (>=0). Errors (-1) stay pending so a
        # re-run of the chunk retries them.
        if rc >= 0:
            done_urls.add(url)
            if state_path:
                state_path.parent.mkdir(parents=True, exist_ok=True)
                state_path.write_text(json.dumps({"done": sorted(done_urls)}))
        time.sleep(args.sleep)

    sess = session_maker()
    try:
        run = sess.query(IngestionRun).filter(
            IngestionRun.id == uuid.UUID(run_id)).first()
        if run:
            run.finished_at = datetime.now(timezone.utc)
            run.status = "completed" if stats["errors"] == 0 else "completed_with_errors"
            run.files_seen = stats["files_downloaded"]
            run.rows_inserted = stats.get("rows_inserted", 0)
            run.rows_rejected = stats["errors"]
            run.error_summary = {"errors": stats["errors"]}
            sess.commit()
    finally:
        sess.close()

    LOGGER.info("=" * 60)
    LOGGER.info("BACKFILL COMPLETE: %s", json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
