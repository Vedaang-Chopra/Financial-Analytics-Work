"""Check whether the NOT-PERSISTED artifacts' source_urls actually have data in
canonical tables under a DIFFERENT raw_artifacts row (dedup re-downloads)."""

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
WITH disk_artifacts AS (
  SELECT id, checksum, source_url FROM raw_artifacts WHERE local_path IS NOT NULL AND checksum IS NOT NULL
),
persisted AS (
  SELECT DISTINCT ra.checksum
  FROM nav_history nh JOIN raw_artifacts ra ON ra.id = nh.raw_artifact_id
  UNION
  SELECT DISTINCT d.checksum
  FROM documents d
  JOIN portfolio_snapshots ps ON ps.document_id = d.id
  JOIN portfolio_holdings ph ON ph.snapshot_id = ps.id
  WHERE d.checksum IS NOT NULL
)
SELECT da.source_url,
       (da.checksum IN (SELECT checksum FROM persisted)) AS cs_persisted,
       EXISTS (
         SELECT 1 FROM documents d2
         JOIN portfolio_snapshots ps2 ON ps2.document_id = d2.id
         WHERE d2.raw_artifact_id = da.id OR d2.source_url = da.source_url
       ) AS url_in_documents,
       EXISTS (
         SELECT 1 FROM nav_history nh2 JOIN raw_artifacts ra2 ON ra2.id = nh2.raw_artifact_id
         WHERE ra2.source_url = da.source_url
       ) AS url_in_nav
FROM disk_artifacts da
LIMIT 20
""")).fetchall()
n_persisted_by_url = 0
for url, csp, urldoc, urlnav in rows:
    status = "SAFE" if (csp or urldoc or urlnav) else "NOT-PERSISTED"
    if status == "SAFE":
        n_persisted_by_url += 1
    print(status, "|", url[:80])
print("safe via any path:", n_persisted_by_url, "/", len(rows))
