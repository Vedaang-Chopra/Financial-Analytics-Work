import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from db_config import mutual_funds_url

import sys
from pathlib import Path
sys.path.insert(0, str(Path('.').resolve()))
from sqlalchemy import text
from mutual_fund_ingestion.agent.db import get_session_maker
from mutual_fund_ingestion.agent.artifact_storage import check_persistence_gate

DB = mutual_funds_url()
session = get_session_maker(DB)()
persisted = check_persistence_gate(session)
print("persisted checksums:", len(persisted))

rows = session.execute(text("""
SELECT ra.id::text, ra.checksum, ra.local_path
FROM raw_artifacts ra
WHERE ra.local_path IS NOT NULL AND ra.checksum IS NOT NULL
LIMIT 12
""")).fetchall()
for rid, cs, lp in rows:
    print(rid[:8], (cs or "")[:10], "PERSISTED" if cs in persisted else "NOT-PERSISTED", "|", (lp or "")[:70])
