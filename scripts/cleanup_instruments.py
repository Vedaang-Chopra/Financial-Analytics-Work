#!/usr/bin/env python
"""One-off cleanup of the ``instruments`` table (Task A2).

Problem being fixed:
  * ~206K instrument rows but only ~15K distinct ISINs.
  * Thousands of garbage ISINs (numeric strings like '0.00059...', '-').
  * Duplicate NULL-ISIN instruments sharing the same normalized_name.

What this script does (idempotent — safe to re-run):
  1. BACKUP FIRST: exports every row that will be deleted or repointed to
     CSV under ``data/backups/`` before any DELETE runs.
  2. Repoints ``portfolio_holdings.instrument_id`` away from doomed
     instruments (bad-ISIN rows -> a single placeholder row; duplicate
     losers -> the kept row), so no FK is orphaned.
  3. Deletes instruments whose ISIN fails ^[A-Z]{2}[A-Z0-9]{9}[0-9]$.
  4. Merges duplicate NULL-ISIN instruments with identical normalized_name
     (keeps one per name) and merges any duplicate non-NULL ISINs too,
     which is a precondition for the unique index.
  5. Creates the unique partial index:
       CREATE UNIQUE INDEX IF NOT EXISTS uq_instruments_isin
           ON instruments(isin) WHERE isin IS NOT NULL;

Usage:
    ./financial_env/bin/python scripts/cleanup_instruments.py            # execute
    ./financial_env/bin/python scripts/cleanup_instruments.py --dry-run  # report only

Deletion policy compliance: nothing is hard-deleted without the backup file
existing on disk first (step 1 runs and is verified before step 2+).
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_URL = "postgresql://vlmrouter:vlmrouter@localhost:5432/mutual_funds"

# Canonical ISIN format: 2-letter country code + 9 alphanumeric + 1 check digit
ISIN_REGEX = r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$"

PLACEHOLDER_NAME = "__INVALID_ISIN_REMOVED__"
PLACEHOLDER_NORM = "invalid isin removed"


def _backup_rows(engine, sql: str, params: dict, out_path: Path, columns: list[str]) -> int:
    """Run a SELECT and stream rows to a CSV file. Returns row count."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with engine.connect().execution_options(stream_results=True) as conn:
        result = conn.execute(text(sql), params)
        with out_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(columns)
            for row in result:
                writer.writerow(row)
                count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--dry-run", action="store_true", help="Report counts without changing anything")
    args = parser.parse_args()

    import os

    database_url = args.database_url or os.environ.get(
        "MUTUAL_FUNDS_DATABASE_URL", DEFAULT_DATABASE_URL
    )
    engine = create_engine(database_url)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = REPO_ROOT / "data" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Step 0: current state
    # ------------------------------------------------------------------
    with engine.begin() as conn:
        state = conn.execute(
            text(
                """
                SELECT
                    count(*) AS total,
                    count(*) FILTER (
                        WHERE isin IS NOT NULL AND isin !~ :regex) AS bad_isin,
                    count(*) FILTER (WHERE isin IS NULL) AS null_isin
                FROM instruments
                """
            ),
            {"regex": ISIN_REGEX},
        ).mappings().one()
        dup_null_groups = conn.execute(
            text(
                """
                SELECT count(*) FROM (
                    SELECT normalized_name FROM instruments
                    WHERE isin IS NULL GROUP BY normalized_name HAVING count(*) > 1
                ) t
                """
            )
        ).scalar()
        dup_isin_rows = conn.execute(
            text(
                """
                SELECT coalesce(sum(c - 1), 0) FROM (
                    SELECT isin, count(*) c FROM instruments
                    WHERE isin IS NOT NULL GROUP BY isin HAVING count(*) > 1
                ) t
                """
            )
        ).scalar()
    print("[state] total=%(total)s bad_isin=%(bad_isin)s null_isin=%(null_isin)s "
          "dup_null_groups=%(dup_null_groups)s dup_valid_isin_extra=%(dup_isin_rows)s" % {
              **state, "dup_null_groups": dup_null_groups, "dup_isin_rows": dup_isin_rows})

    if args.dry_run:
        print("[dry-run] no changes made")
        return 0

    doomed_ids_sql = """
        SELECT id FROM instruments
        WHERE isin IS NOT NULL AND isin !~ :regex
        UNION ALL
        SELECT loser.id FROM (
            SELECT id, ROW_NUMBER() OVER (
                PARTITION BY normalized_name ORDER BY created_at, id) AS rn
            FROM instruments WHERE isin IS NULL
        ) loser WHERE rn > 1
        UNION ALL
        SELECT loser.id FROM (
            SELECT id, ROW_NUMBER() OVER (
                PARTITION BY isin ORDER BY created_at, id) AS rn
            FROM instruments WHERE isin IS NOT NULL AND isin ~ :regex
        ) loser WHERE rn > 1
    """

    # ------------------------------------------------------------------
    # Step 1: BACKUP affected instrument rows + holdings referencing them
    # ------------------------------------------------------------------
    inst_backup = backup_dir / f"instruments_cleanup_{stamp}_affected_instruments.csv"
    n_inst = _backup_rows(
        engine,
        f"SELECT i.id, i.isin, i.name, i.normalized_name, i.instrument_type, "
        f"i.issuer, i.sector, i.metadata_json, i.created_at, i.updated_at "
        f"FROM ({doomed_ids_sql}) d JOIN instruments i ON i.id = d.id",
        {"regex": ISIN_REGEX},
        inst_backup,
        ["id", "isin", "name", "normalized_name", "instrument_type", "issuer",
         "sector", "metadata_json", "created_at", "updated_at"],
    )

    hold_backup = backup_dir / f"instruments_cleanup_{stamp}_repointed_holdings.csv"
    n_hold = _backup_rows(
        engine,
        f"SELECT h.id, h.snapshot_id, h.instrument_id, h.security_name, h.isin "
        f"FROM portfolio_holdings h JOIN ({doomed_ids_sql}) d ON d.id = h.instrument_id",
        {"regex": ISIN_REGEX},
        hold_backup,
        ["holding_id", "snapshot_id", "instrument_id", "security_name", "isin"],
    )

    print(f"[backup] {n_inst} instrument rows -> {inst_backup}")
    print(f"[backup] {n_hold} holding rows (to be repointed) -> {hold_backup}")
    if n_inst == 0 and n_hold == 0:
        print("[done] nothing to clean up")
        return 0
    if not inst_backup.exists() or inst_backup.stat().st_size == 0:
        print("[abort] backup verification failed — no deletes performed")
        return 1

    # ------------------------------------------------------------------
    # Steps 2-5: repoint holdings, delete doomed rows, create index
    # ------------------------------------------------------------------
    with engine.begin() as conn:
        # Placeholder instrument that absorbs references to removed garbage rows
        placeholder_id = conn.execute(
            text(
                """
                INSERT INTO instruments (id, isin, name, normalized_name, metadata_json, created_at, updated_at)
                SELECT gen_random_uuid(), NULL, :pname, :pnorm, '{}'::json, now(), now()
                WHERE NOT EXISTS (
                    SELECT 1 FROM instruments WHERE normalized_name = :pnorm
                )
                RETURNING id
                """
            ),
            {"pname": PLACEHOLDER_NAME, "pnorm": PLACEHOLDER_NORM},
        ).scalar()
        if placeholder_id is None:
            placeholder_id = conn.execute(
                text("SELECT id FROM instruments WHERE normalized_name = :pnorm"),
                {"pnorm": PLACEHOLDER_NORM},
            ).scalar_one()

        # 2a. Bad-ISIN rows: repoint their holdings to the placeholder
        res = conn.execute(
            text(
                f"""
                UPDATE portfolio_holdings h SET instrument_id = :ph
                FROM (SELECT id FROM instruments
                      WHERE isin IS NOT NULL AND isin !~ :regex) d
                WHERE h.instrument_id = d.id
                """
            ),
            {"ph": str(placeholder_id), "regex": ISIN_REGEX},
        )
        bad_holds = res.rowcount

        # 2b. Delete bad-ISIN rows
        res = conn.execute(
            text(
                "DELETE FROM instruments WHERE isin IS NOT NULL AND isin !~ :regex"
            ),
            {"regex": ISIN_REGEX},
        )
        deleted_bad = res.rowcount

        # 3. Merge duplicate NULL-ISIN instruments (same normalized_name):
        #    keep one (earliest created), repoint holdings, drop the rest.
        null_dup_cte = """
            WITH ranked AS (
                SELECT id, normalized_name AS join_key, ROW_NUMBER() OVER (
                    PARTITION BY normalized_name ORDER BY created_at, id) AS rn
                FROM instruments WHERE isin IS NULL
                   AND normalized_name <> :pnorm
            ),
            losers AS (SELECT l.id AS loser_id, k.id AS keeper_id
                       FROM ranked l JOIN ranked k ON l.join_key = k.join_key
                       WHERE l.rn > 1 AND k.rn = 1)
        """
        res = conn.execute(
            text(null_dup_cte + """
                UPDATE portfolio_holdings h SET instrument_id = los.keeper_id
                FROM losers los WHERE h.instrument_id = los.loser_id
            """),
            {"pnorm": PLACEHOLDER_NORM},
        )
        null_rep = res.rowcount
        res = conn.execute(
            text(null_dup_cte + " DELETE FROM instruments i USING losers los WHERE i.id = los.loser_id"),
            {"pnorm": PLACEHOLDER_NORM},
        )
        deleted_null_dups = res.rowcount

        # 4. Merge duplicate valid-ISIN rows (precondition for unique index).
        isin_dup_cte = """
            WITH ranked AS (
                SELECT id, isin AS join_key, ROW_NUMBER() OVER (
                    PARTITION BY isin ORDER BY created_at, id) AS rn
                FROM instruments WHERE isin IS NOT NULL AND isin ~ :regex
            ),
            losers AS (SELECT l.id AS loser_id, k.id AS keeper_id
                       FROM ranked l JOIN ranked k ON l.join_key = k.join_key
                       WHERE l.rn > 1 AND k.rn = 1)
        """
        res = conn.execute(
            text(isin_dup_cte + """
                UPDATE portfolio_holdings h SET instrument_id = los.keeper_id
                FROM losers los WHERE h.instrument_id = los.loser_id
            """),
            {"regex": ISIN_REGEX},
        )
        isin_rep = res.rowcount
        res = conn.execute(
            text(isin_dup_cte + " DELETE FROM instruments i USING losers los WHERE i.id = los.loser_id"),
            {"regex": ISIN_REGEX},
        )
        deleted_isin_dups = res.rowcount

        # 5. Unique partial index
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_instruments_isin "
                "ON instruments(isin) WHERE isin IS NOT NULL"
            )
        )

    print(f"[cleanup] deleted {deleted_bad} bad-ISIN instruments "
          f"(repointed {bad_holds} holdings -> placeholder)")
    print(f"[cleanup] merged {deleted_null_dups} duplicate NULL-ISIN instruments "
          f"(repointed {null_rep} holdings)")
    print(f"[cleanup] merged {deleted_isin_dups} duplicate valid-ISIN instruments "
          f"(repointed {isin_rep} holdings)")

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------
    with engine.begin() as conn:
        remaining_bad = conn.execute(
            text("SELECT count(*) FROM instruments "
                 "WHERE isin !~ :regex AND isin IS NOT NULL"),
            {"regex": ISIN_REGEX},
        ).scalar()
        total = conn.execute(text("SELECT count(*) FROM instruments")).scalar()
        distinct_isins = conn.execute(
            text("SELECT count(DISTINCT isin) FROM instruments")).scalar()
        idx = conn.execute(
            text(
                "SELECT indexdef FROM pg_indexes "
                "WHERE tablename='instruments' AND indexname='uq_instruments_isin'"
            )
        ).scalar()
        orphans = conn.execute(
            text(
                "SELECT count(*) FROM portfolio_holdings h "
                "LEFT JOIN instruments i ON i.id = h.instrument_id "
                "WHERE h.instrument_id IS NOT NULL AND i.id IS NULL"
            )
        ).scalar()
    print("[verify] regex-failing ISINs remaining:", remaining_bad)
    print(f"[verify] total instruments now: {total} (distinct ISINs: {distinct_isins})")
    print("[verify] index:", idx)
    print("[verify] orphaned holdings:", orphans)

    ok = remaining_bad == 0 and orphans == 0 and idx is not None
    print("[status]", "DONE" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
