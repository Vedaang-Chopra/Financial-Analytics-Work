import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from db_config import mutual_funds_url

import psycopg2
conn = psycopg2.connect(mutual_funds_url())
cur = conn.cursor()
cur.execute("SELECT count(*), count(*) FILTER (WHERE local_path IS NOT NULL) FROM raw_artifacts WHERE source_url LIKE '%icicipruamc%'")
print('icici artifacts total / with local_path:', cur.fetchone())
cur.execute("SELECT artifact_type, file_type, count(*) FROM raw_artifacts WHERE source_url LIKE '%icicipruamc%' GROUP BY 1,2")
for r in cur.fetchall(): print(r)
cur.execute("SELECT local_path, size_bytes FROM raw_artifacts WHERE source_url LIKE '%icicipruamc%' AND local_path IS NOT NULL LIMIT 5")
for r in cur.fetchall(): print(r)
cur.execute("SELECT count(*) FROM portfolio_snapshots ps JOIN schemes s ON s.id=ps.scheme_id WHERE ps.source_url LIKE '%icicipruamc%'")
print('icici snapshots:', cur.fetchone()[0])
# how many artifacts have files that still exist on disk
cur.execute("SELECT local_path FROM raw_artifacts WHERE source_url LIKE '%icicipruamc%' AND local_path IS NOT NULL")
import os
exists = sum(1 for (p,) in cur.fetchall() if p and os.path.exists(p))
print('icici artifacts with file on disk:', exists)
