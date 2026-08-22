#!/usr/bin/env python
"""Backfill the fund-level rollup: create funds + link schemes.fund_id (E1).

One-off but idempotent — safe to re-run; only unlinked schemes are processed.

What it does:
  1. BACKUP FIRST: exports every scheme row that gets linked to
     data/backups/fund_rollup_<stamp>.csv before any UPDATE.
  2. Groups schemes by (amc_id, normalized_base_name) via
     mutual_fund_ingestion.agent.fund_rollup.
  3. Groups with >= 2 members must prove portfolio identity: every pair with a
     shared snapshot quarter must have holding overlap >= 0.90 (overlap
     coefficient on distinct ISINs of the latest shared quarter). Groups with
     no shared quarters merge (nothing contradicts); failing groups stay
     unlinked and are reported as ambiguous (under-merge preferred).
  4. Singletons also get a fund row so future sibling-plan ingests land on an
     existing fund (the upsert path reuses the same resolver).

Merge report printed at the end: funds created, schemes linked, ambiguous.

Usage:
    ./financial_env/bin/python scripts/backfill_fund_rollup.py [--dry-run]
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from datetime import datetime
from itertools import combinations
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import psycopg2  # noqa: E402
import psycopg2.extras  # noqa: E402

from db_config import mutual_funds_url  # noqa: E402
from mutual_fund_ingestion.agent.fund_rollup import (  # noqa: E402
    MIN_HOLDING_OVERLAP,
    base_display_name,
    group_schemes_by_base,
    holding_overlap,
    resolve_group_merge,
)

BACKUP_DIR = REPO_ROOT / "data" / "backups"


def fetch_schemes(cur) -> list[dict]:
    cur.execute(
        """
        SELECT s.id::text, s.scheme_name, s.amc_id::text AS amc_id
        FROM schemes s
        WHERE s.fund_id IS NULL AND s.amc_id IS NOT NULL
        ORDER BY s.amc_id, s.id
        """
    )
    return [dict(r) for r in cur.fetchall()]


def quarter_isins(cur, scheme_ids: list[str]) -> dict[str, dict[str, set[str]]]:
    """Per scheme, per quarter: set of distinct non-null ISINs."""
    placeholders = ", ".join(["%s"] * len(scheme_ids))
    cur.execute(
        f"""
        SELECT ps.scheme_id::text,
               date_trunc('quarter', ps.reporting_date)::date AS qtr,
               array_agg(DISTINCT ph.isin) AS isins
        FROM portfolio_holdings ph
        JOIN portfolio_snapshots ps ON ps.id = ph.snapshot_id
        WHERE ps.scheme_id IN ({placeholders})
          AND ph.isin IS NOT NULL AND btrim(ph.isin) <> ''
        GROUP BY 1, 2
        """,
        tuple(scheme_ids),
    )
    out: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for sid, qtr, isins in cur.fetchall():
        out[sid][qtr] = {i for i in (isins or []) if i}
    return out


def group_overlaps(
    member_ids: list[str], by_scheme: dict[str, dict[str, set[str]]]
) -> list[float | None]:
    """Pairwise overlaps on each pair's latest SHARED quarter."""
    overlaps: list[float | None] = []
    for a, b in combinations(member_ids, 2):
        qa = by_scheme.get(a, {})
        qb = by_scheme.get(b, {})
        shared = sorted(set(qa) & set(qb), reverse=True)
        if not shared:
            overlaps.append(None)  # no shared quarter -> unknown
            continue
        q = shared[0]
        overlaps.append(holding_overlap(qa[q], qb[q]))
    return overlaps


def export_backup(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["scheme_id", "scheme_name", "amc_id", "fund_id"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"[backup] exported {len(rows)} scheme rows -> {path}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--database-url", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    dsn = args.database_url or mutual_funds_url()
    conn = psycopg2.connect(dsn)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    schemes = fetch_schemes(cur)
    print(f"schemes to process (fund_id IS NULL, amc known): {len(schemes)}")
    groups = group_schemes_by_base([dict(s) for s in schemes])

    backup_rows: list[dict] = []
    funds_created = 0
    schemes_linked = 0
    singleton_funds = 0
    ambiguous_groups = 0

    # Pre-fetch quarter ISIN sets for ALL schemes at once (one query).
    all_ids = [s["id"] for s in schemes]
    by_scheme = quarter_isins(cur, all_ids) if all_ids else {}

    for (amc_id, base), members in sorted(groups.items(), key=lambda kv: str(kv[0])):
        member_ids = [m["id"] for m in members]
        display = base_display_name(members[0]["scheme_name"])

        if len(members) >= 2:
            overlaps = group_overlaps(member_ids, by_scheme)
            if not resolve_group_merge(overlaps, MIN_HOLDING_OVERLAP):
                ambiguous_groups += 1
                pretty = [round(o, 3) if o is not None else None for o in overlaps]
                print(f"  AMBIGUOUS (left separate): amc={amc_id} base={base!r} "
                      f"members={len(members)} overlaps={pretty}")
                continue

        if args.dry_run:
            kind = "merge-fund" if len(members) >= 2 else "singleton-fund"
            print(f"  DRY {kind}: amc={amc_id} base={base!r} members={len(member_ids)}")
            funds_created += 1
            schemes_linked += len(member_ids)
            if len(members) == 1:
                singleton_funds += 1
            continue

        # create-or-get fund (idempotent via unique constraint)
        cur.execute(
            """
            INSERT INTO funds (amc_id, base_name, normalized_base_name)
            VALUES (%s::uuid, %s, %s)
            ON CONFLICT (amc_id, normalized_base_name) DO NOTHING
            RETURNING id::text
            """,
            (amc_id, display, base),
        )
        row = cur.fetchone()
        if row is None:
            cur.execute(
                "SELECT id::text FROM funds WHERE amc_id = %s::uuid AND normalized_base_name = %s",
                (amc_id, base),
            )
            row = cur.fetchone()
        fund_id = row["id"]
        funds_created += 1

        for mid in member_ids:
            cur.execute(
                """
                UPDATE schemes SET fund_id = %s::uuid
                WHERE id = %s::uuid AND fund_id IS NULL
                """,
                (fund_id, mid),
            )
            schemes_linked += cur.rowcount
            backup_rows.append({
                "scheme_id": mid,
                "scheme_name": next(m["scheme_name"] for m in members if m["id"] == mid),
                "amc_id": amc_id,
                "fund_id": fund_id,
            })
        if len(members) == 1:
            singleton_funds += 1

    if not args.dry_run:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_backup(backup_rows, BACKUP_DIR / f"fund_rollup_{stamp}.csv")
        conn.commit()

    print("\n=== merge report ===")
    print(f"funds ensured:          {funds_created}")
    print(f"schemes linked:         {schemes_linked}")
    print(f"singleton funds:        {singleton_funds}")
    print(f"ambiguous left alone:   {ambiguous_groups}")

    print("\n=== verify ===")
    cur.execute("SELECT count(*) AS funds_total FROM funds")
    print("funds total:", cur.fetchone()["funds_total"])
    cur.execute(
        "SELECT count(*) AS unlinked FROM schemes WHERE fund_id IS NULL AND amc_id IS NOT NULL"
    )
    print("unlinked with amc:", cur.fetchone()["unlinked"])
    cur.execute(
        """
        SELECT count(*) AS multi FROM (
            SELECT fund_id FROM schemes WHERE fund_id IS NOT NULL
            GROUP BY fund_id HAVING count(*) > 1
        ) t
        """
    )
    print("funds with >1 plan (real merges):", cur.fetchone()["multi"])
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
