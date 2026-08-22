#!/usr/bin/env python
"""Backfill schemes.category / sub_category from the AMFI scheme master (Task B1).

Source reality check (verified 2026-08):
- AMFI publishes a single ROLLING scheme master snapshot at
    https://portal.amfiindia.com/DownloadSchemeData_Po.aspx?MF=0
  with columns: AMC, Code, Scheme Name, Scheme Type, Scheme Category,
  Scheme Minimum Amount, Launch Date, Closure Date, ISIN columns.
  It covers ALL schemes (open + closed), so one polite fetch populates
  categories for every known scheme code.
- The per-month files on https://www.amfiindia.com/research-information/amfi-monthly
  (https://portal.amfiindia.com/spages/am{mon}{yyyy}repo.xls) are AUM/folio
  REPORTS aggregated by category — they contain no scheme codes, so they are
  not usable for category backfill.
- The old DownloadSchemeMaster_Po.aspx endpoint now returns 404.

Politeness: sequential requests only, browser UA header, 60s timeout,
sleep >= 1s between any repeated requests, retries with backoff (max 3).

Usage:
  python scripts/backfill_scheme_master.py --database-url URL --dry-run
  python scripts/backfill_scheme_master.py --database-url URL          # live
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import requests

from mutual_fund_ingestion.agent.db import get_session_maker
from mutual_fund_ingestion.agent.parser.scheme_master_excel import parse_scheme_master_excel
from mutual_fund_ingestion.agent.scheme_identity import normalize_amc_name
from mutual_fund_ingestion.agent.upserts import UpsertManager
from mutual_fund_ingestion.agent.validate import validate_scheme_master_record

SCHEME_MASTER_URL = "https://portal.amfiindia.com/DownloadSchemeData_Po.aspx?MF=0"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36 FinancialAnalyticsResearch/1.0"
)
REQUEST_TIMEOUT_S = 60
SLEEP_BETWEEN_REQUESTS_S = 2.0
MAX_ATTEMPTS = 3


def fetch_scheme_master(url: str = SCHEME_MASTER_URL) -> tuple[bytes, int]:
    """Polite sequential GET with retry/backoff. Returns (content, status_code)."""
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    last_exc: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT_S)
            if resp.status_code == 200 and resp.content:
                return resp.content, resp.status_code
            last_exc = RuntimeError(f"HTTP {resp.status_code}, {len(resp.content)} bytes")
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
        if attempt < MAX_ATTEMPTS:
            wait = SLEEP_BETWEEN_REQUESTS_S * attempt
            print(f"  attempt {attempt} failed ({last_exc}); backing off {wait:.0f}s")
            time.sleep(wait)
    raise RuntimeError(f"Failed to fetch {url}: {last_exc}")


def save_raw(content: bytes, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = out_dir / f"amfi_scheme_master_{stamp}.csv"
    path.write_bytes(content)
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description="Backfill schemes.category from AMFI scheme master")
    ap.add_argument("--database-url", required=True)
    ap.add_argument("--url", default=SCHEME_MASTER_URL)
    ap.add_argument("--raw-dir", default="data/raw/mutual_funds/files")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    print(f"Fetching AMFI scheme master: {args.url}")
    content, status = fetch_scheme_master(args.url)
    checksum = hashlib.sha256(content).hexdigest()
    print(f"Fetched {len(content)} bytes (HTTP {status}), sha256={checksum[:12]}…")

    raw_path = save_raw(content, Path(args.raw_dir))
    print(f"Raw artifact saved: {raw_path}")

    result = parse_scheme_master_excel(
        content,
        {"source_url": args.url, "file_ext": ".csv"},
    )
    total = len(result.records)
    categorized = sum(1 for r in result.records if r.get("category"))
    print(f"Parsed {total} records ({len(set(r['scheme_code'] for r in result.records if r.get('scheme_code')))} unique codes); "
          f"category extraction rate {categorized / total:.4f}")
    if result.errors:
        print(f"Parser errors: {result.errors[:5]}")

    records = [r for r in result.records if validate_scheme_master_record(r)[0] and r.get("category")]
    print(f"Validated records with category: {len(records)}")

    if args.dry_run:
        print("[DRY-RUN] no database writes performed")
        return 0

    session = get_session_maker(args.database_url)()
    stats: dict = {}
    try:
        UpsertManager().upsert_canonical(
            session,
            records,
            "scheme_master",
            raw_artifact_id=uuid.uuid4(),  # upsert_schemes does not use this FK
            source_url=args.url,
            stats=stats,
        )
        session.commit()
    except Exception:
        session.rollback()
        raise

    # Phase 2: name-based propagation. Defunct schemes (closed FMPs, dead-AMC
    # funds) are absent from every AMFI master we can reach, but their fund
    # siblings often survive. Category/sub_category are fund-level attributes,
    # so propagating them across rows sharing a normalized fund name is sound.
    name_map: dict[str, tuple[str | None, str | None]] = {}
    for r in records:
        key = normalize_amc_name(r["scheme_name"])
        if key and r.get("category") and key not in name_map:
            name_map[key] = (r.get("category"), r.get("sub_category"))
    try:
        from sqlalchemy import select, text

        from mutual_fund_ingestion.agent.db import Scheme

        pending = session.execute(
            select(Scheme).where(Scheme.category.is_(None))
        ).scalars().all()
        propagated = 0
        for scheme in pending:
            hit = name_map.get(scheme.normalized_scheme_name)
            if hit and hit[0]:
                scheme.category = hit[0]
                if hit[1]:
                    scheme.sub_category = hit[1]
                propagated += 1
        session.commit()
        stats["name_propagated"] = propagated

        # Phase 3: DB-internal propagation — schemes ingested from NAV history
        # carry full NAV-style names; sibling rows of the same fund already
        # categorized (from any source) donate their category by normalized name.
        res = session.execute(text(
            "UPDATE schemes s SET category = m.category, sub_category = m.sub_category "
            "FROM schemes m "
            "WHERE s.category IS NULL AND m.category IS NOT NULL "
            "AND s.normalized_scheme_name = m.normalized_scheme_name"
        ))
        session.commit()
        stats["db_name_propagated"] = res.rowcount
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    print(f"[LIVE] upsert stats: {stats}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
