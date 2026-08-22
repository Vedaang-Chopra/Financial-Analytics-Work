"""Definitive check: the PPAF July-2026 data IS in canonical tables (84 holdings
for Parag Parikh Arbitrage Fund 2026-07-31). The checksum b0646feba9... just
isn't linked via documents.raw_artifact_id — it was persisted under a different
raw_artifact row (re-download). Test: does checksum appear in documents.checksum
with holdings?"""

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

r = session.execute(text("""
SELECT count(*) FROM documents d
JOIN portfolio_snapshots ps ON ps.document_id = d.id
JOIN portfolio_holdings ph ON ph.snapshot_id = ps.id
WHERE d.checksum = 'b0646feba9e0'
""")).scalar()
print("holdings via documents.checksum=b0646feba9e0:", r)
