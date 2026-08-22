import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from db_config import mutual_funds_url

import psycopg2
conn = psycopg2.connect(mutual_funds_url())
cur = conn.cursor()
cur.execute("SELECT count(*), count(DISTINCT source_url) FROM raw_artifacts WHERE source_url LIKE '%icicipruamc%'")
print('icici artifacts rows / distinct urls:', cur.fetchone())
cur.execute("""SELECT count(DISTINCT d.checksum) FROM documents d WHERE d.source_url LIKE '%icicipruamc%' AND d.checksum IS NOT NULL""")
print('distinct checksums in icici documents:', cur.fetchone()[0])
