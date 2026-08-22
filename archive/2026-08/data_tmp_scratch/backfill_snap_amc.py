import sys
from pathlib import Path

import psycopg2

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from db_config import mutual_funds_url

conn = psycopg2.connect(mutual_funds_url())
cur = conn.cursor()
cur.execute("""
UPDATE portfolio_snapshots ps
SET amc_id = s.amc_id
FROM schemes s
WHERE ps.scheme_id = s.id AND ps.amc_id IS NULL AND s.amc_id IS NOT NULL
""")
print('snapshots backfilled:', cur.rowcount)
conn.commit()
