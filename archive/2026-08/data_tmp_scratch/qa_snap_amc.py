import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from db_config import mutual_funds_url

import psycopg2
conn = psycopg2.connect(mutual_funds_url())
cur = conn.cursor()
# snapshots with NULL amc: are their schemes linked?
cur.execute("""
SELECT count(*) FROM portfolio_snapshots ps
JOIN schemes s ON s.id = ps.scheme_id
WHERE ps.amc_id IS NULL AND s.amc_id IS NOT NULL
""")
print('null-amc snapshots whose SCHEME is linked:', cur.fetchone()[0])
cur.execute("""
SELECT count(*) FROM portfolio_snapshots ps
JOIN schemes s ON s.id = ps.scheme_id
WHERE ps.amc_id IS NULL AND s.amc_id IS NULL
""")
print('null-amc snapshots whose scheme is also orphaned:', cur.fetchone()[0])
