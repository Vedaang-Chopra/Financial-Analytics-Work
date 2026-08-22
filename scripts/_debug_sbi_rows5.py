"""Debug 5: SBI staged records - distinct scheme_name values + sheet names."""
import sys
from pathlib import Path

import psycopg2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db_config import mutual_funds_url

DB = mutual_funds_url()
conn = psycopg2.connect(DB)
cur = conn.cursor()
cur.execute("""
SELECT DISTINCT sr.parsed_fields_json->>'scheme_name', sr.sheet_name
FROM staging_rows sr JOIN raw_artifacts ra ON ra.id=sr.raw_artifact_id
WHERE ra.source_url ILIKE '%sbimf%'
""")
rows = cur.fetchall()
print("distinct (scheme_name, sheet):", len(rows))
for r in rows[:20]:
    print(r)
conn.close()
