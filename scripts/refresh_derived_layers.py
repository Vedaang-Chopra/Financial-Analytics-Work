#!/usr/bin/env python
"""Refresh all derived layers after a mutual_funds ingestion (Task T5 / G7).

Calls the existing production scripts (no SQL duplicated here):

  1. scripts/create_consensus_view.py --refresh
       -> REFRESH MATERIALIZED VIEW consensus_panel
  2. scripts/compute_scheme_overlap.py
       -> TRUNCATE + recompute scheme_overlap

Then records the refresh:
  * if a ``refresh_log`` table exists in mutual_funds, insert a row there;
  * otherwise append one JSON line to
    data/reports/mutual_funds/refresh_log.jsonl with timestamp + row counts.

Usage:
    ./financial_env/bin/python scripts/refresh_derived_layers.py [--skip-overlap]

--skip-overlap refreshes only the materialized view (overlap recompute is
the slow step; useful when only panel inputs changed).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import psycopg2

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from db_config import mutual_funds_url  # noqa: E402

JSONL_LOG = REPO_ROOT / "data" / "reports" / "mutual_funds" / "refresh_log.jsonl"


def run_step(cmd: list[str]) -> str:
    """Run a production script, streaming its output; abort on failure."""
    print(f"$ {' '.join(cmd)}", flush=True)
    result = subprocess.run(
        cmd, cwd=str(REPO_ROOT), capture_output=True, text=True
    )
    out = (result.stdout or "").strip()
    if out:
        print(out)
    if result.returncode != 0:
        err = (result.stderr or "").strip()
        if err:
            print(err, file=sys.stderr)
        raise SystemExit(f"step failed (exit {result.returncode}): {cmd}")
    return out


def count(cur, table: str) -> int:
    cur.execute(f"SELECT count(*) FROM {table}")
    return int(cur.fetchone()[0])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Refresh consensus_panel + scheme_overlap and log it.")
    ap.add_argument("--skip-overlap", action="store_true",
                    help="refresh only consensus_panel (skip scheme_overlap rebuild)")
    args = ap.parse_args(argv)

    py = sys.executable
    run_step([py, str(REPO_ROOT / "scripts" / "create_consensus_view.py"), "--refresh"])

    overlap_rows: int | None = None
    if not args.skip_overlap:
        # --force: compute_scheme_overlap aborts above --max-pairs (default
        # 200K) as a runaway-computation guard. Post-backfill reality is
        # ~380K pairs (~679 schemes in 2026-Q2), legitimate growth — force.
        run_step([py, str(REPO_ROOT / "scripts" / "compute_scheme_overlap.py"), "--force"])

    conn = psycopg2.connect(mutual_funds_url())
    try:
        with conn.cursor() as cur:
            panel_rows = count(cur, "consensus_panel")
            if not args.skip_overlap:
                overlap_rows = count(cur, "scheme_overlap")

            cur.execute(
                """SELECT EXISTS (
                       SELECT 1 FROM information_schema.tables
                       WHERE table_schema = 'public' AND table_name = 'refresh_log'
                   )"""
            )
            row = cur.fetchone()
            has_table = bool(row[0]) if row else False
            ts = datetime.now(timezone.utc).isoformat()

            record = {
                "ts": ts,
                "trigger": "refresh_derived_layers.py",
                "consensus_panel_rows": panel_rows,
                "scheme_overlap_rows": overlap_rows,
                "status": "ok",
            }
            if has_table:
                cur.execute(
                    """INSERT INTO refresh_log (refreshed_at, trigger, consensus_panel_rows,
                                                scheme_overlap_rows, status)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (ts, "refresh_derived_layers.py", panel_rows, overlap_rows, "ok"),
                )
                conn.commit()
                log_target = f"refresh_log table ({ts})"
            else:
                JSONL_LOG.parent.mkdir(parents=True, exist_ok=True)
                with open(JSONL_LOG, "a") as fh:
                    fh.write(json.dumps(record) + "\n")
                log_target = f"{JSONL_LOG} ({ts})"
    finally:
        conn.close()

    print(
        f"REFRESH OK | consensus_panel={panel_rows} rows"
        + (f" | scheme_overlap={overlap_rows} rows" if overlap_rows is not None else "")
        + f" | logged to {log_target}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
