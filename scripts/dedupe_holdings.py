#!/usr/bin/env python
"""One-off dedupe of the ``portfolio_holdings`` table (Task A3).

Problem being fixed:
  * The existing unique constraint ``portfolio_holdings_snapshot_security_isin_key``
    on ``(snapshot_id, security_name, isin)`` does NOT enforce uniqueness when
    ``isin`` is NULL (PostgreSQL treats each NULL as distinct), so the same
    security can appear multiple times inside one snapshot.

What this script does (idempotent — safe to re-run):
  1. SAFETY CHECK: looks for foreign keys pointing AT ``portfolio_holdings``.
     If any exist it stops and reports them WITHOUT deleting anything
     (deleting loser rows could orphan child rows). Currently there are none,
     so plain DELETE is safe.
  2. BACKUP FIRST: exports every row of every affected duplicate group to
     ``data/backups/holdings_dedupe_<stamp>.csv`` before any DELETE runs.
     A ``planned_action`` column marks keep vs delete per row.
  3. Duplicates handled:
       a) NULL-isin duplicates: groups on (snapshot_id, security_name)
          WHERE isin IS NULL -> keep latest created_at, delete the rest.
       b) Same non-null isin duplicates: groups on
          (snapshot_id, security_name, isin) WHERE isin IS NOT NULL
          (queried first; currently zero groups) -> same policy if any appear.
     Ties on created_at are broken deterministically by id (DESC).
     Nothing is repointed — no other table references holdings rows.
  4. Creates the complementary partial unique index (does NOT touch the
     existing composite constraint):
       CREATE UNIQUE INDEX IF NOT EXISTS uq_holdings_snapshot_security_null_isin
           ON portfolio_holdings(snapshot_id, security_name) WHERE isin IS NULL;

Usage:
    ./financial_env/bin/python scripts/dedupe_holdings.py            # execute
    ./financial_env/bin/python scripts/dedupe_holdings.py --dry-run  # report only

Deletion policy compliance: nothing is hard-deleted without the backup file
existing on disk first (step 2 runs and is verified before step 3).
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parents[1]
from db_config import mutual_funds_url  # noqa: E402

DEFAULT_DATABASE_URL = mutual_funds_url()

HOLDINGS_COLUMNS = [
    "id",
    "snapshot_id",
    "instrument_id",
    "security_name",
    "isin",
    "sector",
    "asset_class",
    "quantity",
    "market_value",
    "market_value_currency",
    "percentage_to_nav",
    "coupon",
    "maturity_date",
    "rating",
    "metadata_json",
    "created_at",
]

PARTIAL_INDEX_SQL = (
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_holdings_snapshot_security_null_isin "
    "ON portfolio_holdings(snapshot_id, security_name) WHERE isin IS NULL"
)

# Groups of duplicate NULL-isin rows within one snapshot, ranked so the keeper
# is the row with the latest created_at (ties broken by larger id for a
# deterministic winner). rn == 1 is the keeper.
#
# One portable statement covering BOTH duplicate cases:
#   * null_ranked   — duplicate rows with isin IS NULL per (snapshot_id, security_name)
#   * same_ranked   — exact duplicates sharing a non-null isin
# Written as a single top-level WITH so it runs on both PostgreSQL and SQLite.
RANKED_UNION_SQL = """
WITH null_dup_groups AS (
    SELECT snapshot_id, security_name FROM portfolio_holdings
    WHERE isin IS NULL
    GROUP BY snapshot_id, security_name HAVING count(*) > 1
),
same_dup_groups AS (
    SELECT snapshot_id, security_name, isin FROM portfolio_holdings
    WHERE isin IS NOT NULL
    GROUP BY snapshot_id, security_name, isin HAVING count(*) > 1
),
null_ranked AS (
    SELECT CAST(h.id AS CHAR(36)) AS id_str,
           row_number() OVER (
               PARTITION BY h.snapshot_id, h.security_name
               ORDER BY h.created_at DESC, h.id DESC
           ) AS rn
    FROM portfolio_holdings h
    JOIN null_dup_groups d
      ON h.snapshot_id = d.snapshot_id AND h.security_name = d.security_name
    WHERE h.isin IS NULL
),
same_ranked AS (
    SELECT CAST(h.id AS CHAR(36)) AS id_str,
           row_number() OVER (
               PARTITION BY h.snapshot_id, h.security_name, h.isin
               ORDER BY h.created_at DESC, h.id DESC
           ) AS rn
    FROM portfolio_holdings h
    JOIN same_dup_groups d
      ON h.snapshot_id = d.snapshot_id
     AND h.security_name = d.security_name
     AND h.isin = d.isin
    WHERE h.isin IS NOT NULL
)
SELECT r.id_str, r.rn, h.security_name
FROM (
    SELECT id_str, rn FROM null_ranked
    UNION ALL
    SELECT id_str, rn FROM same_ranked
) r
JOIN portfolio_holdings h ON CAST(h.id AS CHAR(36)) = r.id_str
ORDER BY h.security_name, r.rn
"""


def find_inbound_foreign_keys(engine, conn) -> list[dict]:
    """Return FKs on OTHER tables that reference portfolio_holdings.

    Uses information_schema (PostgreSQL). On other dialects (e.g. the SQLite
    test fixture) there is no information_schema — return [] and let tests
    monkeypatch this function to exercise the abort path.
    """
    if engine.dialect.name != "postgresql":
        return []
    rows = conn.execute(
        text(
            """
            SELECT tc.table_name AS child_table,
                   kcu.column_name AS child_column,
                   tc.constraint_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu
              ON ccu.constraint_name = tc.constraint_name
             AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND ccu.table_name = 'portfolio_holdings'
              AND tc.table_name <> 'portfolio_holdings'
            """
        )
    ).mappings()
    return [dict(r) for r in rows]


def count_duplicate_groups(conn) -> int:
    return conn.execute(
        text(
            """
            SELECT count(*) FROM (
                SELECT snapshot_id, security_name FROM portfolio_holdings
                WHERE isin IS NULL
                GROUP BY snapshot_id, security_name HAVING count(*) > 1
            ) d
            """
        )
    ).scalar_one()


def compute_delete_ids(conn) -> tuple[list[str], dict[str, str]]:
    """Compute loser ids for both duplicate cases.

    Returns (delete_ids, action_by_id) where action_by_id maps every row of an
    affected group to 'keep' or 'delete' (used to annotate the backup CSV).
    """
    rows = conn.execute(text(RANKED_UNION_SQL)).all()

    delete_ids: list[str] = []
    action_by_id: dict[str, str] = {}
    for id_str, rn, _name in rows:
        action_by_id[id_str] = "keep" if rn == 1 else "delete"
        if rn != 1:
            delete_ids.append(id_str)
    return delete_ids, action_by_id


def backup_rows(engine, out_path: Path, action_by_id: dict[str, str]) -> int:
    """Export every row of an affected duplicate group to CSV."""
    cols = ", ".join(f"h.{c}" for c in HOLDINGS_COLUMNS)
    # Wrap the ranked union so we can also select the raw columns.
    sql = RANKED_UNION_SQL.replace(
        "SELECT r.id_str, r.rn, h.security_name",
        f"SELECT {cols}, r.rn",
        1,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with engine.connect().execution_options(stream_results=True) as conn:
        result = conn.execute(text(sql))
        with out_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(HOLDINGS_COLUMNS + ["dup_rank", "planned_action"])
            for row in result:
                writer.writerow(
                    [
                        str(v) if v is not None else ""
                        for v in row[:-1]
                    ]
                    + [row[-1], action_by_id[str(row[0])]]
                )
                count += 1
    return count


def run_dedupe(engine, dry_run: bool = False, backup_dir: Path | None = None) -> dict:
    """Dedupe portfolio_holdings + create partial unique index.

    Split out from main() so tests can drive it against a SQLite engine.
    """
    report: dict = {}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = backup_dir or REPO_ROOT / "data" / "backups"

    with engine.connect() as conn:
        # Step 0: FK safety gate.
        inbound_fks = find_inbound_foreign_keys(engine, conn)
        report["inbound_foreign_keys"] = inbound_fks
        report["null_isin_dup_groups"] = count_duplicate_groups(conn)
        same_isin_groups = conn.execute(
            text(
                """
                SELECT count(*) FROM (
                    SELECT snapshot_id, security_name, isin FROM portfolio_holdings
                    WHERE isin IS NOT NULL
                    GROUP BY snapshot_id, security_name, isin HAVING count(*) > 1
                ) d
                """
            )
        ).scalar_one()
        report["same_isin_dup_groups"] = same_isin_groups
        delete_ids, action_by_id = compute_delete_ids(conn)
        report["rows_to_delete"] = len(delete_ids)

    if inbound_fks:
        report["aborted"] = True
        print(
            "ABORT: child tables reference portfolio_holdings — refusing to "
            f"delete. Repoint these first: {inbound_fks}"
        )
        return report

    if not delete_ids:
        print("No duplicate rows found — nothing to do.")
        report["deleted"] = 0

    if delete_ids:
        backup_path = backup_dir / f"holdings_dedupe_{stamp}.csv"
        n_backed = backup_rows(engine, backup_path, action_by_id)
        assert n_backed >= len(delete_ids), "backup missing rows!"
        report["backup_path"] = str(backup_path)
        report["backup_rows"] = n_backed
        print(
            f"Backed up {n_backed} duplicate-group rows "
            f"({len(delete_ids)} marked delete) -> {backup_path}"
        )

        if dry_run:
            report["dry_run"] = True
            print("DRY RUN — no deletes performed.")
            return report

        # Chunked delete to stay well under parameter limits.
        deleted = 0
        chunk = 500
        for i in range(0, len(delete_ids), chunk):
            batch = delete_ids[i : i + chunk]
            placeholders = ", ".join(f":id{j}" for j in range(len(batch)))
            params = {f"id{j}": v for j, v in enumerate(batch)}
            with engine.begin() as conn:
                res = conn.execute(
                    text(
                        "DELETE FROM portfolio_holdings "
                        f"WHERE CAST(id AS CHAR(36)) IN ({placeholders})"
                    ),
                    params,
                )
                deleted += res.rowcount
        report["deleted"] = deleted
        print(f"Deleted {deleted} duplicate loser rows.")

    # Complementary partial unique index (does not replace the composite key).
    with engine.begin() as conn:
        conn.execute(text(PARTIAL_INDEX_SQL))
    print("Ensured partial unique index uq_holdings_snapshot_security_null_isin.")
    report["index_created"] = True
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=None)
    parser.add_argument(
        "--dry-run", action="store_true", help="Report counts without changing anything"
    )
    args = parser.parse_args()

    import os

    database_url = args.database_url or os.environ.get(
        "MUTUAL_FUNDS_DATABASE_URL", DEFAULT_DATABASE_URL
    )
    engine = create_engine(database_url)
    report = run_dedupe(engine, dry_run=args.dry_run)

    if report.get("aborted"):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
