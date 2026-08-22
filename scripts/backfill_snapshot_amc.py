#!/usr/bin/env python3
"""One-off backfill: populate portfolio_snapshots.amc_id from the scheme link.

Task A4. For every portfolio_snapshots row with amc_id IS NULL:
  1. Backup-first convention — export affected rows to
     data/backups/snapshot_amc_backfill_<stamp>.csv before any UPDATE.
  2. Resolve amc_id via portfolio_snapshots -> schemes -> schemes.amc_id.
  3. Fallback (scheme has no amc_id): resolve via the snapshot's source_url
     domain against configs/amc_sources.yaml.
Unresolvable rows are left NULL and reported (never fabricate AMC links).

Usage:
    ./financial_env/bin/python scripts/backfill_snapshot_amc.py [--dry-run]
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import psycopg2  # noqa: E402
import yaml  # noqa: E402

from mutual_fund_ingestion.agent.upserts import _registered_domain  # noqa: E402
from utils.text_utils import normalize_amc_name  # noqa: E402

DSN = "postgresql://vlmrouter:vlmrouter@localhost:5432/mutual_funds"

BACKUP_COLUMNS = [
    "snapshot_id", "scheme_id", "amc_id", "reporting_date",
    "source_url", "parser_version", "validation_status",
]


def export_backup(rows: list[tuple], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(BACKUP_COLUMNS)
        writer.writerows(rows)
    print(f"[backup] exported {len(rows)} affected rows -> {path}")


def amc_id_by_source_url(cur, source_url: str) -> str | None:
    """Resolve AMC id via source URL domain against configs/amc_sources.yaml."""
    try:
        src_domain = _registered_domain(urlparse(source_url).netloc)
    except ValueError:
        return None
    if not src_domain or "." not in src_domain:
        return None
    registry = REPO_ROOT / "configs" / "amc_sources.yaml"
    if not registry.exists():
        return None
    data = yaml.safe_load(registry.read_text(encoding="utf-8")) or {}
    for entry in data.get("sources", []) or []:
        try:
            seed_domain = _registered_domain(urlparse(entry.get("seed_url") or "").netloc)
        except ValueError:
            continue
        if seed_domain != src_domain:
            continue
        amc_name = entry.get("amc_name")
        if not amc_name:
            continue
        cur.execute(
            "SELECT id FROM amcs WHERE normalized_name = %s LIMIT 1",
            (normalize_amc_name(amc_name),),
        )
        row = cur.fetchone()
        if row:
            return row[0]
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    conn = psycopg2.connect(DSN)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT ps.id, ps.scheme_id, s.amc_id, s.scheme_name, ps.source_url
        FROM portfolio_snapshots ps
        LEFT JOIN schemes s ON s.id = ps.scheme_id
        WHERE ps.amc_id IS NULL
        ORDER BY ps.created_at
        """
    )
    null_rows = cur.fetchall()
    print(f"[scan] portfolio_snapshots rows with amc_id IS NULL: {len(null_rows)}")

    # Backup first — even though this is additive-only, keep the convention.
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = REPO_ROOT / "data" / "backups" / f"snapshot_amc_backfill_{stamp}.csv"
    if null_rows:
        cur.execute(
            """
            SELECT ps.id, ps.scheme_id, ps.amc_id, ps.reporting_date,
                   ps.source_url, ps.parser_version, ps.validation_status
            FROM portfolio_snapshots ps
            WHERE ps.amc_id IS NULL
            ORDER BY ps.created_at
            """
        )
        export_backup(cur.fetchall(), backup_path)

    updated = 0
    unresolved: list[str] = []
    for snap_id, scheme_id, scheme_amc_id, scheme_name, source_url in null_rows:
        resolved_id, source = None, None
        if scheme_amc_id is not None:
            resolved_id, source = scheme_amc_id, "scheme_join"
        else:
            resolved_id = amc_id_by_source_url(cur, source_url)
            source = "source_url_domain"
        if resolved_id is None:
            unresolved.append(f"{snap_id}: scheme={scheme_name!r} url={source_url}")
            continue
        if not args.dry_run:
            cur.execute(
                "UPDATE portfolio_snapshots SET amc_id = %s WHERE id = %s",
                (resolved_id, snap_id),
            )
        updated += 1
        print(f"  [update] {snap_id} -> {resolved_id} ({source})")

    if not args.dry_run:
        conn.commit()

    print(f"[backfill] rows updated: {updated}")
    if unresolved:
        print(f"[backfill] rows left NULL ({len(unresolved)}):")
        for detail in unresolved:
            print(f"  - {detail}")

    cur.execute("SELECT count(*) FROM portfolio_snapshots WHERE amc_id IS NULL")
    remaining = cur.fetchone()[0]
    print(f"[verify] SELECT count(*) FROM portfolio_snapshots WHERE amc_id IS NULL -> {remaining}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
