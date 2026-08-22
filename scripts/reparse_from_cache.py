"""Re-parse cached screener HTML to backfill growth_summary + exchange codes.

Offline fix-up after parser repairs (growth ranges-tables, BSE/NSE anchors):
re-runs parse_company_page on data/raw/screener/<slug>/*.html for every stock
already in the DB and re-saves via db.save_payload WITHOUT price_history /
peers, so price_points and peer_rows are untouched. Snapshot + ingestion_run
rows are append-only, so this is history-preserving.

Usage:
  python scripts/reparse_from_cache.py            # all DB stocks with cache
  python scripts/reparse_from_cache.py --dry-run  # report only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text

from screener_ingestion import db, fetch, parse

from db_config import screener_url

DB = screener_url()
CACHE_DIR = "data/raw/screener"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=DB)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--delay", type=float, default=0.0,
                    help="Politeness delay (offline parse needs none)")
    args = ap.parse_args()

    engine = create_engine(args.database_url)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT slug FROM stocks ORDER BY id")).fetchall()
    slugs = [r[0] for r in rows]
    print(f"stocks in DB: {len(slugs)}")

    ok = skipped_no_cache = failed = 0
    growth_rows = codes_found = 0
    for i, slug in enumerate(slugs):
        cached = fetch.latest_cached(slug, CACHE_DIR)
        if cached is None:
            skipped_no_cache += 1
            continue
        try:
            html = cached.read_text(encoding="utf-8")
            payload = parse.parse_company_page(html)
            payload["slug"] = slug
            n_growth = len(payload.get("growth") or [])
            has_codes = bool(payload.get("bse_code") or payload.get("nse_code"))
            if not args.dry_run:
                # price_history/peers intentionally omitted: backfill must not
                # touch price_points or peer_rows
                db.save_payload(args.database_url, payload,
                                peers=None, raw_path=str(cached),
                                price_history=None)
            ok += 1
            growth_rows += n_growth
            codes_found += 1 if has_codes else 0
            if n_growth == 0 or not has_codes:
                print(f"  [{i + 1}] WARN {slug}: growth={n_growth} "
                      f"bse={payload.get('bse_code')} nse={payload.get('nse_code')}")
        except Exception as exc:
            failed += 1
            print(f"  [{i + 1}] FAIL {slug}: {str(exc)[:120]}")
        if args.delay:
            import time
            time.sleep(args.delay)

    mode = "DRY-RUN" if args.dry_run else "saved"
    print(f"\n{mode}: reparsed={ok} no_cache={skipped_no_cache} failed={failed} "
          f"growth_rows_total={growth_rows} with_exchange_codes={codes_found}/{ok}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
