#!/usr/bin/env python
"""Backfill the FULL AMFI NAV history into PostgreSQL.

AMFI's historical endpoint (discovered 2026-08-22):
    https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx?frmdt=DD-Mon-YYYY&todt=DD-Mon-YYYY
  - max 90-day window per request
  - data available from 01-Apr-2006 onwards
  - semicolon text, same 8-column family as NAVAll.txt (layout B)

Strategy:
  - iterate windows from 2006-04-01 to today in <=90-day chunks
  - download, parse with production parser, upsert via UpsertManager
  - idempotent: nav_history has UNIQUE(scheme_code, nav_date); re-runs are safe
  - polite: sequential requests, ~1s sleep between windows

Usage:
  # DB URL resolves via DATABASE_URL/MF_DATABASE_URL env var or api.env (db_config.py)
  ./financial_env/bin/python scripts/backfill_amfi_nav_history.py [--start 2006-04-01]
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import sys
import time
import uuid
from datetime import date, datetime, timedelta

sys.path.insert(0, ".")

import requests

from mutual_fund_ingestion.agent.db import (
    IngestionRun,
    QuarantineRow,
    RawArtifact,
    get_session_maker,
)
from mutual_fund_ingestion.agent.parser import parse_file
from mutual_fund_ingestion.agent.upserts import UpsertManager
from mutual_fund_ingestion.agent.validate import validate_and_filter_records

from db_config import generic_database_url as _generic_db_url  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
LOGGER = logging.getLogger("nav_backfill")

HISTORY_URL = "https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
WINDOW_DAYS = 88          # stay under AMFI's 90-day limit with margin
SLEEP_BETWEEN = 1.0       # polite crawl: 1s between requests


def daterange_windows(start: date, end: date):
    cur = start
    while cur <= end:
        win_end = min(cur + timedelta(days=WINDOW_DAYS - 1), end)
        yield cur, win_end
        cur = win_end + timedelta(days=1)


def fetch_window(session: requests.Session, start: date, end: date) -> bytes | None:
    params = {
        "frmdt": start.strftime("%d-%b-%Y"),
        "todt": end.strftime("%d-%b-%Y"),
    }
    for attempt in range(3):
        try:
            resp = session.get(HISTORY_URL, params=params, headers=HEADERS, timeout=180)
            resp.raise_for_status()
            return resp.content
        except Exception as exc:  # noqa: BLE001
            wait = 2 ** attempt * 5
            LOGGER.warning("Fetch failed for %s..%s (%s); retry in %ss",
                           start, end, exc, wait)
            time.sleep(wait)
    LOGGER.error("Giving up on window %s..%s", start, end)
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2006-04-01", help="Backfill start date (YYYY-MM-DD)")
    ap.add_argument("--end", default=None, help="Backfill end date (default: today)")
    ap.add_argument("--database-url", default=None, help="Overrides DATABASE_URL env")
    args = ap.parse_args()

    import os

    db_url = args.database_url or os.environ.get(
        "DATABASE_URL", ""
    ) or _generic_db_url()

    start_date = date.fromisoformat(args.start)
    end_date = date.fromisoformat(args.end) if args.end else date.today()
    run_id = str(uuid.uuid4())

    session_maker = get_session_maker(db_url)
    upserts = UpsertManager()
    http = requests.Session()

    # record the run
    run_row = IngestionRun(
        id=uuid.UUID(run_id),
        started_at=datetime.now().date() and datetime.utcnow(),
        status="running",
        config_json={
            "pipeline": "amfi_nav_history_backfill",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "source_url": HISTORY_URL,
        },
    )
    s = session_maker()
    s.add(run_row)
    s.commit()
    s.close()

    totals = {"windows": 0, "downloaded": 0, "parsed": 0, "upserted": 0,
              "quarantined": 0, "errors": 0}
    t0 = time.time()

    try:
        for w_start, w_end in daterange_windows(start_date, end_date):
            totals["windows"] += 1
            content = fetch_window(http, w_start, w_end)
            if content is None:
                totals["errors"] += 1
                continue
            totals["downloaded"] += 1

            result = parse_file("nav_history", "text", content,
                                {"source_url": f"{HISTORY_URL}?frmdt={w_start}&todt={w_end}"})
            totals["parsed"] += len(result.records)
            valid: list[dict] = []

            sess = session_maker()
            try:
                artifact = RawArtifact(
                    run_id=uuid.UUID(run_id),
                    source_url=f"{HISTORY_URL}?frmdt={w_start}&todt={w_end}",
                    artifact_type="file",
                    file_type="text",
                    content_type="text/plain",
                    checksum=hashlib.sha256(content).hexdigest(),
                    size_bytes=len(content),
                )
                sess.add(artifact)
                sess.flush()

                # Validate -> quarantine -> canonical (same path as
                # ArtifactProcessor). Zero/invalid NAV rows land in
                # quarantine_rows instead of entering canonical tables.
                upserts.set_run_id(run_id)
                valid, quarantined, snapshot_warnings = validate_and_filter_records(
                    result, run_id, return_warnings=True
                )

                for q in quarantined:
                    upserts.write_validation_result(
                        sess,
                        entity_type="nav_history",
                        check_name="schema_validation",
                        severity="error",
                        status="failed",
                        message=q.get("reason", "validation failed"),
                    )
                    sess.add(QuarantineRow(
                        run_id=uuid.UUID(run_id),
                        raw_artifact_id=artifact.id,
                        dataset_type="nav_history",
                        reason=q.get("reason", "unknown"),
                        raw_data_json=q.get("raw_data_json"),
                        parser_error=q.get("parser_error"),
                        retryable=q.get("retryable", False),
                    ))
                    totals["quarantined"] = totals.get("quarantined", 0) + 1

                # Snapshot-level WARN gate: logged, never drops rows.
                for warning in snapshot_warnings:
                    upserts.write_validation_result(
                        sess,
                        entity_type="nav_history",
                        check_name=warning.get("check_name", "snapshot_pct_sum"),
                        severity=warning.get("severity", "warn"),
                        status=warning.get("status", "warning"),
                        message=warning.get("message"),
                    )

                stats: dict = {}
                upserts.upsert_canonical(
                    sess, valid, "nav_history", artifact.id,
                    f"{HISTORY_URL}", stats,
                )
                sess.commit()
                inserted = stats.get("rows_inserted", stats.get("records_upserted", len(valid)))
                totals["upserted"] += inserted
            except Exception as exc:  # noqa: BLE001
                sess.rollback()
                totals["errors"] += 1
                LOGGER.exception("Upsert failed for %s..%s: %s", w_start, w_end, exc)
            finally:
                sess.close()

            elapsed = time.time() - t0
            LOGGER.info(
                "window %s..%s : parsed=%d valid=%d | total upserted=%d | %.0fs elapsed",
                w_start, w_end, len(result.records), len(valid),
                totals["upserted"], elapsed,
            )
            time.sleep(SLEEP_BETWEEN)
    except KeyboardInterrupt:
        LOGGER.warning("Interrupted — progress so far is committed (idempotent re-run safe).")

    # finalize run row
    s = session_maker()
    run = s.query(IngestionRun).filter(IngestionRun.id == uuid.UUID(run_id)).first()
    if run:
        run.finished_at = datetime.utcnow()
        run.status = "completed" if totals["errors"] == 0 else "completed_with_errors"
        run.files_seen = totals["downloaded"]
        run.rows_inserted = totals["upserted"]
        run.rows_rejected = totals["parsed"] - totals["upserted"]
        run.error_summary = totals
        s.commit()
    s.close()

    LOGGER.info("BACKFILL COMPLETE: %s", totals)
    print(f"\nDONE {totals}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
