"""Classify on-disk runtime files: deletable / in-flight / not-yet-persisted."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from db_config import mutual_funds_url

import sys
from pathlib import Path
sys.path.insert(0, str(Path('.').resolve()))
from sqlalchemy import text
from mutual_fund_ingestion.agent.db import get_session_maker

DB = mutual_funds_url()
session = get_session_maker(DB)()

persisted_urls = set(r[0] for r in session.execute(text("""
SELECT DISTINCT d.source_url
FROM portfolio_snapshots ps
JOIN documents d ON d.id = ps.document_id
JOIN portfolio_holdings ph ON ph.snapshot_id = ps.id
WHERE d.source_url IS NOT NULL
""")).fetchall())
persisted_cs = set(r[0] for r in session.execute(text("""
SELECT DISTINCT d.checksum FROM documents d
JOIN portfolio_snapshots ps ON ps.document_id = d.id
JOIN portfolio_holdings ph ON ph.snapshot_id = ps.id WHERE d.checksum IS NOT NULL
""")).fetchall())
nav_cs = set(r[0] for r in session.execute(text("""
SELECT DISTINCT ra.checksum FROM nav_history nh
JOIN raw_artifacts ra ON ra.id = nh.raw_artifact_id WHERE ra.checksum IS NOT NULL
""")).fetchall())
persisted_cs |= nav_cs

rows = session.execute(text("""
SELECT ra.checksum, ra.source_url, r.status, r.finished_at, r.started_at
FROM raw_artifacts ra JOIN ingestion_runs r ON r.id = ra.run_id
WHERE ra.local_path IS NOT NULL
""")).fetchall()

deletable = inflight = notyet = 0
for cs, url, status, fin, started in rows:
    if cs in persisted_cs or url in persisted_urls:
        deletable += 1
    elif status == "running":
        inflight += 1
    else:
        notyet += 1
print(f"on-disk artifact rows: {len(rows)}")
print(f"  deletable NOW (data persisted): {deletable}")
print(f"  run still 'running': {inflight}")
print(f"  parsed but not yet in canonical tables: {notyet}")

# files on disk that have NO raw_artifacts row at all (orphan scratch)
import os
tracked = set(r[0] for r in session.execute(text(
    "SELECT local_path FROM raw_artifacts WHERE local_path IS NOT NULL")).fetchall())
disk_files = list(Path("data/tmp/mutual_funds/runtime").rglob("*"))
disk_only = [f for f in disk_files if f.is_file() and str(f) not in tracked]
sz = sum(f.stat().st_size for f in disk_only)
print(f"files on disk WITHOUT raw_artifacts tracking: {len(disk_only)} ({sz/1e6:.1f} MB)")
