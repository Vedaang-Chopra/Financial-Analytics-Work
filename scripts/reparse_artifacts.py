#!/usr/bin/env python
"""Re-ingest artifacts that have rows in raw_artifacts but no canonical data.

Phase A3 tool. For each raw_artifacts row matching a host filter:
  - skip if checksum already has documents/snapshots (dedup)
  - re-download from source_url (blobs were never persisted locally)
  - parse via parse_file('portfolio_disclosure', ...)
  - validate -> quarantine -> upsert_canonical (same path as targeted ingestion)

Polite crawling: sequential, --delay seconds between fetches.

Usage:
  python scripts/reparse_artifacts.py --database-url URL \
      --host icicipruamc.com [--max-files 5] [--dry-run] [--delay 2]
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import requests
from sqlalchemy import func

from mutual_fund_ingestion.agent.db import (
    Document,
    PortfolioSnapshot,
    RawArtifact,
    QuarantineRow,
    get_session_maker,
)
from mutual_fund_ingestion.agent.parser import parse_file
from mutual_fund_ingestion.agent.upserts import UpsertManager
from mutual_fund_ingestion.agent.validate import validate_and_filter_records

LOGGER = logging.getLogger("reparse_artifacts")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description="Re-download + parse raw_artifacts entries")
    ap.add_argument("--database-url", required=True)
    ap.add_argument("--host", required=True, help="source_url host substring filter")
    ap.add_argument("--max-files", type=int, default=0, help="0 = all")
    ap.add_argument("--dry-run", action="store_true", help="report only, fetch nothing")
    ap.add_argument("--delay", type=float, default=2.0, help="seconds between requests")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    session = get_session_maker(args.database_url)()
    upsert_manager = UpsertManager()

    # quarantine_rows.raw_artifact_id / run_id carry FKs — register a real run
    from mutual_fund_ingestion.agent.db import IngestionRun

    run = IngestionRun(
        status="running",
        config_json={"tool": "reparse_artifacts", "host": args.host,
                     "max_files": args.max_files},
    )
    session.add(run)
    session.commit()
    run_id = str(run.id)

    artifacts = (
        session.query(RawArtifact)
        .filter(RawArtifact.source_url.ilike(f"%{args.host}%"))
        .order_by(RawArtifact.fetch_timestamp)
        .all()
    )
    LOGGER.info("%d artifacts match host=%r", len(artifacts), args.host)
    if args.max_files:
        artifacts = artifacts[: args.max_files]

    stats = {"fetched": 0, "parse_ok": 0, "parse_empty": 0, "fetch_failed": 0,
             "rows_upserted": 0, "rows_quarantined": 0, "snapshots_after": 0}

    # checksums that already produced documents (idempotency guard)
    known = {c for (c,) in session.query(Document.checksum).filter(
        Document.checksum.isnot(None)).all() if c}

    for art in artifacts:
        url = art.source_url
        if art.checksum and str(art.checksum) in known:
            LOGGER.info("SKIP (checksum known): %s", url)
            continue

        if args.dry_run:
            LOGGER.info("[DRY] would fetch %s", url)
            continue

        try:
            resp = requests.get(url, headers=HEADERS, timeout=120)
            if resp.status_code == 403:
                LOGGER.error("403 Forbidden (profile as blocked, not retrying): %s", url)
                stats["fetch_failed"] += 1
                continue
            resp.raise_for_status()
        except Exception as exc:
            LOGGER.error("FETCH FAILED %s: %s", url, exc)
            stats["fetch_failed"] += 1
            continue

        content = resp.content
        checksum = sha256(content)
        if checksum in known:
            LOGGER.info("SKIP (re-fetched checksum known): %s", url)
            continue
        known.add(checksum)
        stats["fetched"] += 1

        from utils.url_utils import file_type_from_url
        file_type = file_type_from_url(url) or art.file_type or "zip"
        metadata = {"source_url": url, "amc_name": "ICICI Prudential Mutual Fund",
                    "file_ext": Path(url.split("?")[0]).suffix or ".zip"}
        result = parse_file("portfolio_disclosure", file_type, content, metadata)
        LOGGER.info("parsed %d records from %s", len(result.records), url)

        if not result.records:
            stats["parse_empty"] += 1
            continue
        stats["parse_ok"] += 1

        valid, quarantined, warnings = validate_and_filter_records(result, run_id,
                                                                   return_warnings=True)
        # update the artifact row's checksum now that we have the bytes
        art.checksum = checksum
        art.size_bytes = len(content)

        upsert_manager.set_run_id(run_id)
        for q in quarantined:
            session.add(QuarantineRow(
                run_id=uuid.UUID(run_id), raw_artifact_id=art.id,
                dataset_type="portfolio_disclosure",
                reason=q.get("reason", "unknown"),
                raw_data_json=q.get("raw_data_json"),
                parser_error=q.get("parser_error"),
                retryable=False,
            ))
        stats["rows_quarantined"] += len(quarantined)

        upsert_manager.upsert_canonical(
            session, valid, "portfolio_disclosure", art.id, url, {},
            checksum=checksum, amc_name="ICICI Prudential Mutual Fund",
        )
        stats["rows_upserted"] += len(valid)
        session.commit()
        time.sleep(args.delay)

    n_snap = session.query(PortfolioSnapshot).join(
        RawArtifact, PortfolioSnapshot.source_url == RawArtifact.source_url
    ).filter(RawArtifact.source_url.ilike(f"%{args.host}%")).count()
    stats["snapshots_after"] = n_snap
    run.status = "completed"
    run.finished_at = func.now()
    run.rows_inserted = stats["rows_upserted"]
    run.rows_rejected = stats["rows_quarantined"]
    run.error_summary = {k: v for k, v in stats.items()}
    session.commit()
    print(stats)
    session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
