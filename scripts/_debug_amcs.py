"""Debug: where did SBI/UTI rows land? Check amcs + snapshot counts by amc."""
import sys
from pathlib import Path

import psycopg2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db_config import mutual_funds_url

DB = mutual_funds_url()
conn = psycopg2.connect(DB)
cur = conn.cursor()

cur.execute("SELECT id, normalized_name FROM amcs ORDER BY normalized_name")
for i, n in cur.fetchall():
    print(i, n)

print("\n=== snapshots per amc:")
cur.execute("""
SELECT a.normalized_name, count(DISTINCT ps.id)
FROM amcs a JOIN schemes s ON s.amc_id=a.id
JOIN portfolio_snapshots ps ON ps.scheme_id=s.id
GROUP BY 1 ORDER BY 2 DESC
""")
for r in cur.fetchall():
    print(r)
conn.close()
