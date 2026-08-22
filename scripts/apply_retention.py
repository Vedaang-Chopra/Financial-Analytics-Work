"""Delete-after-ingest retention: remove raw downloaded files only when provably persisted.

Safety gate (hard): a local artifact file may be deleted only when ALL of:
  1. raw_artifacts.checksum is recorded, AND that checksum's parsed rows reached
     canonical tables (nav_history via raw_artifact_id, or portfolio_snapshots ->
     portfolio_holdings via documents.raw_artifact_id)  [see
     mutual_fund_ingestion.agent.artifact_storage.check_persistence_gate]
  2. Its ingestion run finished before this script's cutoff timestamp (never touch
     artifacts belonging to runs still in flight).
  3. The on-disk file is at least --min-age-minutes old (default 30).

Also cleans unreferenced repo-root test_*.db / log_test.db SQLite litter (each
filename is grepped against tests/ and scripts/ first; referenced files are kept).

Dry-run by default. Use --apply to actually delete. Backup CSVs of everything
deleted are written under data/tmp/ before any deletion.
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import re
import shutil
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from mutual_fund_ingestion.agent.artifact_storage import (  # noqa: E402
    check_persistence_gate,
    load_retention_candidates,
)
from mutual_fund_ingestion.agent.db import get_session_maker  # noqa: E402

LOGGER = logging.getLogger(__name__)

from db_config import mutual_funds_url  # noqa: E402

DEFAULT_DATABASE_URL = mutual_funds_url()
RUNTIME_DIR = REPO_ROOT / "data/tmp/mutual_funds/runtime"
BACKUP_DIR = REPO_ROOT / "data/tmp"

TEST_DB_PATTERN = re.compile(r"^(test_[A-Za-z0-9_.-]*\.db(-journal)?|log_test\.db)$")

# Canonical row counts must not change across cleanup.
CANONICAL_COUNTS_SQL = """
SELECT 'portfolio_holdings', count(*) FROM portfolio_holdings
UNION ALL SELECT 'portfolio_snapshots', count(*) FROM portfolio_snapshots
UNION ALL SELECT 'nav_history', count(*) FROM nav_history
UNION ALL SELECT 'staging_rows', count(*) FROM staging_rows
UNION ALL SELECT 'raw_artifacts', count(*) FROM raw_artifacts
"""


def canonical_counts(session) -> dict[str, int]:
    from sqlalchemy import text

    return {row[0]: row[1] for row in session.execute(text(CANONICAL_COUNTS_SQL))}


def du_bytes(path: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += (Path(root) / name).stat().st_size
            except OSError:
                pass
    return total


def find_test_db_files() -> list[Path]:
    return sorted(
        p for p in REPO_ROOT.iterdir()
        if p.is_file() and TEST_DB_PATTERN.match(p.name)
    )


def referenced_test_db_names() -> set[str]:
    """Filenames matching TEST_DB_PATTERN referenced anywhere in tests/ or scripts/."""
    refs: set[str] = set()
    scan_roots = [REPO_ROOT / "tests", REPO_ROOT / "scripts"]
    for root in scan_roots:
        if not root.exists():
            continue
        for py in root.rglob("*.py"):
            try:
                text_src = py.read_text(errors="replace")
            except OSError:
                continue
            for match in TEST_DB_PATTERN.finditer(text_src):
                refs.add(match.group(0))
    return refs


def classify_test_dbs(min_age: timedelta) -> tuple[list[Path], list[Path], list[Path]]:
    """Returns (deletable, blocked_referenced, blocked_too_young)."""
    now = datetime.now(timezone.utc)
    refs = referenced_test_db_names()
    deletable, ref_blocked, young_blocked = [], [], []
    for path in find_test_db_files():
        if path.name in refs:
            ref_blocked.append(path)
            continue
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        if now - mtime < min_age:
            young_blocked.append(path)
            continue
        deletable.append(path)
    return deletable, ref_blocked, young_blocked


def prune_empty_dirs(runtime_dir: Path) -> list[Path]:
    """Bottom-up removal of directories left completely empty after file deletion."""
    removed: list[Path] = []
    if not runtime_dir.exists():
        return removed
    for dirpath, dirnames, filenames in os.walk(runtime_dir, topdown=False):
        d = Path(dirpath)
        if d == runtime_dir:
            continue
        try:
            if not any(d.iterdir()):
                d.rmdir()
                removed.append(d)
        except OSError as exc:
            LOGGER.warning("Could not remove empty dir %s: %s", d, exc)
    return removed


def write_backup_csv(rows: list[dict], path: Path) -> None:
    if not rows:
        return
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def human(nbytes: int) -> str:
    value = float(nbytes)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f}{unit}"
        value /= 1024
    return f"{value:.1f}GB"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL))
    parser.add_argument("--runtime-dir", type=Path, default=RUNTIME_DIR)
    parser.add_argument("--min-age-minutes", type=float, default=30.0)
    parser.add_argument("--skip-test-dbs", action="store_true", help="Do not clean repo-root test_*.db litter")
    parser.add_argument("--apply", action="store_true", help="Actually delete (default: dry-run)")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)

    logging.basicConfig(level=getattr(logging, args.log_level.upper()),
                        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s")

    mode = "APPLY" if args.apply else "DRY-RUN"
    cutoff = datetime.now(timezone.utc)
    min_age = timedelta(minutes=args.min_age_minutes)
    print(f"[{mode}] cutoff={cutoff.isoformat()} min_age={args.min_age_minutes}m")

    session_maker = get_session_maker(args.database_url)
    session = session_maker()
    before_counts = canonical_counts(session)
    print(f"Canonical counts BEFORE: {before_counts}")

    gate = check_persistence_gate(session)
    if isinstance(gate, tuple):
        persisted, persisted_urls = gate
    else:  # older signature returned checksums only
        persisted, persisted_urls = gate, set()
    print(
        f"Persistence gate: {len(persisted)} checksums + {len(persisted_urls)} "
        "source-urls confirmed in canonical tables"
    )

    candidates = load_retention_candidates(
        session, persisted_checksums=persisted, finished_before=cutoff,
        min_age=min_age, persisted_urls=persisted_urls
    )
    eligible = [c for c in candidates if c["local_path"] and not c["blocked_reasons"]]
    eligible = [c for c in eligible if Path(c["local_path"]).exists()]
    blocked = [c for c in candidates if c["blocked_reasons"]]

    elig_bytes = sum(c.get("disk_size_bytes", 0) for c in eligible)
    print(f"\nArtifact files: {len(eligible)} deletable ({human(elig_bytes)}), "
          f"{len(blocked)} blocked")

    reason_totals: dict[str, int] = {}
    for c in blocked:
        for reason in c["blocked_reasons"]:
            reason_totals[reason] = reason_totals.get(reason, 0) + 1
    print("Blocked reasons:", reason_totals or "none")

    # --- non-disclosure scratch (crawler bycatch: PDFs, notices, screenshots) ---
    scratch = [
        c for c in candidates
        if c["blocked_reasons"] and c["local_path"] and Path(c["local_path"]).exists()
        and c.get("source_url")
        and not any(k in str(c["source_url"]).lower() for k in ("portfolio", "disclosure"))
        and "file_missing_on_disk" not in c["blocked_reasons"]
        and "run_still_running_or_unfinished" not in c["blocked_reasons"]
        and "run_finished_after_cutoff" not in c["blocked_reasons"]
    ]
    scratch_bytes = sum(Path(c["local_path"]).stat().st_size for c in scratch if Path(c["local_path"]).exists())
    print(f"\nNon-disclosure scratch (never parsed, not needed): {len(scratch)} files ({human(scratch_bytes)})")

    # --- test db litter -----------------------------------------------------
    test_deletable, test_ref_blocked, test_young_blocked = ([], [], [])
    if not args.skip_test_dbs:
        test_deletable, test_ref_blocked, test_young_blocked = classify_test_dbs(min_age)
        test_bytes = sum(p.stat().st_size for p in test_deletable)
        print(f"\nRepo-root SQLite litter: {len(test_deletable)} deletable ({human(test_bytes)}), "
              f"{len(test_ref_blocked)} referenced (kept), {len(test_young_blocked)} too young (kept)")
        for p in test_ref_blocked:
            print(f"  KEPT (referenced in tests//scripts/): {p.name}")
        for p in test_young_blocked:
            print(f"  KEPT (younger than {args.min_age_minutes}m): {p.name}")

    if not args.apply:
        print("\n--- DRY RUN: would delete ---")
        for c in sorted(eligible, key=lambda x: x["local_path"]):
            print(f"  DEL {human(c.get('disk_size_bytes', 0)):>9}  {c['local_path']}")
        for p in test_deletable:
            print(f"  DEL {human(p.stat().st_size):>9}  {p.name} (repo-root sqlite litter)")
        for c in scratch:
            print(f"  DEL {human(Path(c['local_path']).stat().st_size):>9}  {c['local_path']} (non-disclosure scratch)")
        runtime_before = du_bytes(args.runtime_dir)
        data_before = du_bytes(REPO_ROOT / "data")
        print(f"\ndata/tmp/mutual_funds/runtime currently {human(runtime_before)}; data/ {human(data_before)}")
        print("Dry run complete — rerun with --apply to delete.")
        return 0

    # ---------------- APPLY ----------------
    stamp = cutoff.strftime("%Y%m%d_%H%M%S")
    runtime_before = du_bytes(args.runtime_dir)
    data_before = du_bytes(REPO_ROOT / "data")

    backup_rows = [
        {
            "category": "raw_artifact",
            "path": c["local_path"],
            "checksum": c["checksum"],
            "size_bytes": c.get("disk_size_bytes", 0),
            "raw_artifact_id": str(c["id"]),
            "run_finished_at": str(c["run_finished_at"]),
        }
        for c in eligible
    ] + [
        {"category": "non_disclosure_scratch", "path": c["local_path"], "checksum": c.get("checksum") or "",
         "size_bytes": Path(c["local_path"]).stat().st_size if Path(c["local_path"]).exists() else 0,
         "raw_artifact_id": str(c["id"]), "run_finished_at": str(c["run_finished_at"])}
        for c in scratch
    ] + [
        {"category": "repo_root_sqlite_litter", "path": str(p), "checksum": "",
         "size_bytes": p.stat().st_size, "raw_artifact_id": "", "run_finished_at": ""}
        for p in test_deletable
    ]
    backup_path = BACKUP_DIR / f"retention_deleted_{stamp}.csv"
    write_backup_csv(backup_rows, backup_path)
    print(f"\nBackup list written: {backup_path}")

    deleted_files, deleted_bytes = 0, 0
    for c in eligible:
        path = Path(c["local_path"])
        try:
            size = path.stat().st_size
            path.unlink()
            meta = path.with_suffix(path.suffix + ".meta.json")
            if meta.exists():
                meta.unlink()
            # Mark row as no longer locally retained (metadata stays for audit).
            from sqlalchemy import text
            session.execute(
                text("UPDATE raw_artifacts SET retained = FALSE WHERE id = CAST(:aid AS uuid)"),
                {"aid": str(c["id"])},
            )
            session.commit()
            deleted_files += 1
            deleted_bytes += size
        except OSError as exc:
            session.rollback()
            LOGGER.warning("Failed to delete %s: %s", path, exc)

    scratch_files, scratch_deleted_bytes = 0, 0
    for c in scratch:
        path = Path(c["local_path"])
        try:
            size = path.stat().st_size
            path.unlink()
            from sqlalchemy import text as _text
            session.execute(
                _text("UPDATE raw_artifacts SET retained = FALSE WHERE id = CAST(:aid AS uuid)"),
                {"aid": str(c["id"])},
            )
            session.commit()
            scratch_files += 1
            scratch_deleted_bytes += size
        except OSError as exc:
            session.rollback()
            LOGGER.warning("Failed to delete scratch %s: %s", path, exc)
    print(f"Deleted artifact files: {deleted_files} ({human(deleted_bytes)})")
    print(f"Deleted non-disclosure scratch: {scratch_files} ({human(scratch_deleted_bytes)})")

    pruned = prune_empty_dirs(args.runtime_dir)
    print(f"Pruned empty run dirs: {len(pruned)}")

    t_deleted, t_bytes = 0, 0
    for p in test_deletable:
        try:
            size = p.stat().st_size
            p.unlink()
            t_deleted += 1
            t_bytes += size
        except OSError as exc:
            LOGGER.warning("Failed to delete %s: %s", p, exc)
    print(f"Deleted repo-root sqlite litter files: {t_deleted} ({human(t_bytes)})")

    after_counts = canonical_counts(session)
    print(f"Canonical counts AFTER:  {after_counts}")
    deltas = {k: after_counts[k] - before_counts[k] for k in before_counts}
    if any(v != 0 for v in deltas.values()):
        print(f"!!! NON-ZERO DB DELTAS: {deltas}")

    runtime_after = du_bytes(args.runtime_dir)
    data_after = du_bytes(REPO_ROOT / "data")
    print(f"data/tmp/mutual_funds/runtime: {human(runtime_before)} -> {human(runtime_after)}")
    print(f"data/: {human(data_before)} -> {human(data_after)}")
    print(f"Done ({mode}). Backup CSV: {backup_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
