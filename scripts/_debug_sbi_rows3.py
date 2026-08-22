"""Debug 3: SBI canonical rows."""
import sys
from pathlib import Path

import psycopg2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db_config import mutual_funds_url

DB = mutual_funds_url()
conn = psycopg2.connect(DB)
cur = conn.cursor()

cur.execute("""
SELECT count(*) FROM portfolio_snapshots ps JOIN schemes s ON s.id=ps.scheme_id
JOIN amcs a ON a.id=s.amc_id WHERE a.normalized_name='sbi'
""")
print("sbi snapshots:", cur.fetchone())

cur.execute("""
SELECT ps.id, s.scheme_name, ps.reporting_date
FROM portfolio_snapshots ps JOIN schemes s ON s.id=ps.scheme_id
JOIN amcs a ON a.id=s.amc_id WHERE a.normalized_name='sbi' LIMIT 5
""")
for r in cur.fetchall():
    print(r)

# any snapshot referencing schemes with 'SBI' in name under other AMCs?
cur.execute("""
SELECT a.normalized_name, count(*)
FROM portfolio_snapshots ps JOIN schemes s ON s.id=ps.scheme_id
LEFT JOIN amcs a ON a.id=s.amc_id
WHERE s.normalized_scheme_name ILIKE '%sbi%' OR s.scheme_name ILIKE '%sbi%'
GROUP BY 1
""")
print("snapshots on SBI-named schemes by amc:", cur.fetchall())

# quarantine for the sbi runs?
cur.execute("""
SELECT reason, count(*) FROM quarantine_rows q
WHERE q.raw_data_json::text ILIKE '%sbimf%' GROUP BY 1 ORDER BY 2 DESC LIMIT 5
""")
try:
    print("quarantine:", cur.fetchall())
except Exception as e:
    print("q err", e)

# validation results errors mentioning sbi
cur.execute("""
SELECT message, count(*) FROM validation_results
WHERE message ILIKE '%sbi%' AND severity IN ('error','failed') GROUP BY 1 ORDER BY 2 DESC LIMIT 5
""")
print("val errors:", cur.fetchall())
conn.close()
