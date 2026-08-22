"""Debug 2: SBI scheme linkage."""
import sys
from pathlib import Path

import psycopg2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db_config import mutual_funds_url

DB = mutual_funds_url()
conn = psycopg2.connect(DB)
cur = conn.cursor()

cur.execute("""
SELECT column_name FROM information_schema.columns WHERE table_name='schemes' ORDER BY ordinal_position
""")
print("schemes cols:", [r[0] for r in cur.fetchall()])

cur.execute("""
SELECT s.id, s.scheme_name, a.normalized_name
FROM schemes s LEFT JOIN amcs a ON a.id=s.amc_id
WHERE s.scheme_name ILIKE '%sbi%' LIMIT 5
""")
for r in cur.fetchall():
    print(r)

# where do the big snapshots' schemes belong?
cur.execute("""
SELECT ps.id, s.scheme_name, a.normalized_name, count(ph.id)
FROM portfolio_snapshots ps
JOIN schemes s ON s.id=ps.scheme_id
LEFT JOIN amcs a ON a.id=s.amc_id
JOIN portfolio_holdings ph ON ph.snapshot_id=ps.id
GROUP BY 1,2,3 ORDER BY 4 DESC LIMIT 8
""")
print("\nbig snapshots -> amc:")
for r in cur.fetchall():
    print(r)
conn.close()
