"""Debug 4: recent snapshots + SBI record fields."""
import sys
from pathlib import Path

import psycopg2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db_config import mutual_funds_url

DB = mutual_funds_url()
conn = psycopg2.connect(DB)
cur = conn.cursor()

cur.execute("""
SELECT column_name FROM information_schema.columns WHERE table_name='portfolio_snapshots' ORDER BY ordinal_position
""")
print("snap cols:", [r[0] for r in cur.fetchall()])

cur.execute("""
SELECT count(*) FROM staging_rows sr
JOIN raw_artifacts ra ON ra.id = sr.raw_artifact_id
WHERE ra.source_url ILIKE '%sbimf%' AND sr.dataset_type='portfolio_disclosure'
""")
print("sbi staging rows:", cur.fetchone())

# inspect a sample staged SBI record's parsed fields
cur.execute("""
SELECT sr.parsed_fields_json FROM staging_rows sr
JOIN raw_artifacts ra ON ra.id = sr.raw_artifact_id
WHERE ra.source_url ILIKE '%sbimf%' LIMIT 3
""")
import json
for (j,) in cur.fetchall():
    print(json.dumps(j, default=str)[:400])

# snapshots created today
cur.execute("""
SELECT count(*) FROM portfolio_snapshots WHERE created_at > now() - interval '2 hours'
""")
print("snapshots last 2h:", cur.fetchone())
conn.close()
