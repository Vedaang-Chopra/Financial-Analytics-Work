"""Chunked, resumable ingestion of a stock universe into Postgres.

Reads data/raw/screener/universe_nifty500.csv, keeps progress in
data/raw/screener/ingest_checkpoint.json, ingests one chunk per invocation.

Usage:
  python scripts/ingest_chunk.py --chunk-size 50          # next pending chunk
  python scripts/ingest_chunk.py --chunk-size 100 --limit-first 100   # top 100 only
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text

DB = "postgresql://vlmrouter:vlmrouter@localhost:5432/screener"
UNIVERSE = Path("data/raw/screener/universe_nifty500.csv")
CHECKPOINT = Path("data/raw/screener/ingest_checkpoint.json")
FRESH_HOURS = 24


def load_checkpoint() -> dict:
    if CHECKPOINT.exists():
        return json.loads(CHECKPOINT.read_text())
    return {"completed": {}, "failed": {}, "last_chunk_at": None}


def save_checkpoint(cp: dict) -> None:
    CHECKPOINT.write_text(json.dumps(cp, indent=1))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunk-size", type=int, default=50)
    ap.add_argument("--delay", type=float, default=3.0)
    ap.add_argument("--limit-first", type=int, default=None,
                    help="Only consider the first N universe rows (e.g. top 100)")
    ap.add_argument("--max-chunks", type=int, default=1)
    args = ap.parse_args()

    rows = list(csv.DictReader(open(UNIVERSE)))
    if args.limit_first:
        rows = rows[: args.limit_first]
    slugs = [r["screener_slug"] for r in rows]
    print(f"universe: {len(slugs)} stocks (limit_first={args.limit_first})")

    cp = load_checkpoint()
    engine = create_engine(DB)

    # which slugs still need work?
    def needs_ingest(slug: str) -> bool:
        if slug in cp["completed"] or slug in cp["failed"]:
            return False
        with engine.connect() as conn:
            last = conn.execute(text("""
                SELECT MAX(finished_at) FROM ingestion_runs
                WHERE stock_slug=:s AND status='success'
            """), {"s": slug}).scalar()
        if last and datetime.now(timezone.utc) - last < timedelta(hours=FRESH_HOURS):
            return False
        return True

    pending = [s for s in slugs if needs_ingest(s)]
    already = len(slugs) - len(pending)
    print(f"pending: {len(pending)} (fresh/skipped: {already})")
    if not pending:
        print("ALL DONE for this universe.")
        return 0

    # process up to max_chunks chunks
    sys_path_setup = True
    from screener_ingestion import db, fetch, parse
    from screener_ingestion.cli import fetch_peers_html, ingest_one

    chunks_done = 0
    t0 = time.time()
    while pending and chunks_done < args.max_chunks:
        chunk = pending[: args.chunk_size]
        print(f"\n=== chunk {chunks_done + 1}: {len(chunk)} stocks ===")
        ok = fail = 0
        for i, slug in enumerate(chunk):
            try:
                summary = ingest_one(slug, DB)
                cp["completed"][slug] = {
                    "at": datetime.now(timezone.utc).isoformat(),
                    "items": summary["line_items"],
                    "price_points": summary.get("price_points", 0),
                }
                ok += 1
                print(f"  [{i + 1}/{len(chunk)}] OK   {slug:<14} "
                      f"items={summary['line_items']:<5} prices={summary.get('price_points', 0):<5}")
            except Exception as exc:
                cp["failed"][slug] = {
                    "at": datetime.now(timezone.utc).isoformat(),
                    "error": str(exc)[:300],
                }
                fail += 1
                print(f"  [{i + 1}/{len(chunk)}] FAIL {slug:<14} {str(exc)[:80]}")
                try:
                    db.record_failure(DB, slug, "consolidated", str(exc))
                except Exception:
                    pass
            time.sleep(args.delay)

        cp["last_chunk_at"] = datetime.now(timezone.utc).isoformat()
        save_checkpoint(cp)
        pending = [s for s in pending[args.chunk_size:]]
        chunks_done += 1
        total_done = len(cp["completed"]) + len(cp["failed"])
        print(f"checkpoint saved: {total_done}/{len(slugs)} done "
              f"({ok} ok, {fail} failed this chunk, {time.time() - t0:.0f}s)")

    remaining = len(pending)
    print(f"\nSTATUS: {len(cp['completed'])} completed, {len(cp['failed'])} failed, "
          f"{remaining} remaining of {len(slugs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
