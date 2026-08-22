"""Check PPFAS portfolio files on disk: is their data in canonical tables under
a DIFFERENT checksum (re-downloaded file with different bytes, e.g. query-param
variants)? Compare by scheme+reporting_date instead of checksum."""

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

# PPFAS files on disk not persisted by checksum
rows = session.execute(text("""
SELECT ra.id::text, ra.checksum, ra.source_url
FROM raw_artifacts ra
WHERE ra.local_path IS NOT NULL AND ra.checksum IS NOT NULL
  AND ra.source_url LIKE '%ppfas%portfolio-disclosure%'
""")).fetchall()
print("PPFAS disclosure artifacts on disk:", len(rows))

# do documents exist pointing at these source_urls?
n_doc = n_snap = 0
for rid, cs, url in rows:
    doc = session.execute(text("""
        SELECT d.id::text FROM documents d WHERE d.source_url = :u LIMIT 1
    """), {"u": url}).scalar_one_or_none()
    if doc:
        n_doc += 1
        snap = session.execute(text("""
            SELECT count(*) FROM portfolio_holdings ph
            JOIN portfolio_snapshots ps ON ps.id = ph.snapshot_id
            WHERE ps.document_id = :did
        """), {"did": doc}).scalar()
        if snap and snap > 0:
            n_snap += 1
print(f"with documents row: {n_doc}; with holdings via that document: {n_snap}")

# overall: how many PPFAS snapshots exist?
tot = session.execute(text("""
SELECT count(*) FROM portfolio_snapshots ps
JOIN schemes s ON s.id=ps.scheme_id JOIN amcs a ON a.id=s.amc_id
WHERE a.name='PPFAS Mutual Fund'
""")).scalar()
print("total ppfas snapshots:", tot)
