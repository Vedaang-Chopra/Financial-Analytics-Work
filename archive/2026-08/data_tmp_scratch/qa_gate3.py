"""Full classification of the 155 on-disk artifacts: portfolio-disclosure files
whose data IS in canonical tables (safe) vs non-portfolio junk (PDFs, notices —
never parsed, safe to delete as scratch since they're not disclosure data)."""

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

rows = session.execute(text("""
WITH disk AS (
  SELECT id, checksum, source_url FROM raw_artifacts WHERE local_path IS NOT NULL AND checksum IS NOT NULL
),
persisted_cs AS (
  SELECT DISTINCT ra.checksum
  FROM nav_history nh JOIN raw_artifacts ra ON ra.id = nh.raw_artifact_id
  UNION
  SELECT DISTINCT d.checksum
  FROM documents d
  JOIN portfolio_snapshots ps ON ps.document_id = d.id
  JOIN portfolio_holdings ph ON ph.snapshot_id = ps.id
  WHERE d.checksum IS NOT NULL
)
SELECT da.checksum, da.source_url,
       (da.checksum IN (SELECT checksum FROM persisted_cs)) AS persisted,
       (da.source_url ILIKE '%portfolio%' OR da.source_url ILIKE '%disclosure%') AS is_disclosure
FROM disk da
""")).fetchall()

n = len(rows)
safe_persisted = sum(1 for _, _, p, _ in rows if p)
junk = sum(1 for _, _, p, disc in rows if not p and not disc)
junk_disc = [(c, u) for c, u, p, disc in rows if not p and disc]
print(f"total on-disk w/ checksum: {n}")
print(f"persisted (gate-pass): {safe_persisted}")
print(f"non-disclosure junk (pdf/notices): {junk}")
print(f"NOT persisted but IS disclosure-named: {len(junk_disc)}")
for c, u in junk_disc[:10]:
    print("  ", c[:10], u[:90])
