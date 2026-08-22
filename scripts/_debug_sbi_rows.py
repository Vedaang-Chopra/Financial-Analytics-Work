"""Debug: trace SBI-inserted rows (1631) — where are they?"""
import sys
from pathlib import Path

import psycopg2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db_config import mutual_funds_url

DB = mutual_funds_url()
conn = psycopg2.connect(DB)
cur = conn.cursor()

# raw artifacts from sbimf
cur.execute("""
SELECT ra.id, ra.source_url FROM raw_artifacts ra
WHERE ra.source_url ILIKE '%sbimf%' ORDER BY ra.id DESC LIMIT 5
""")
arts = cur.fetchall()
for a in arts:
    print(a)

if arts:
    art_ids = [a[0] for a in arts]
    cur.execute("""
    SELECT count(*) FROM staging_rows WHERE raw_artifact_id IN %s
    """, (tuple(art_ids),))
    print("staging rows:", cur.fetchone())

    # canonical holdings linked to snapshots from these artifacts?
    cur.execute("""
    SELECT ps.id, ps.scheme_id, count(ph.id)
    FROM portfolio_snapshots ps JOIN portfolio_holdings ph ON ph.snapshot_id=ps.id
    GROUP BY 1,2 HAVING count(ph.id) > 100 ORDER BY 3 DESC LIMIT 5
    """)
    print("big snapshots:", cur.fetchall())

# check schemes named like SBI under other AMCs
cur.execute("""
SELECT s.id, s.name, a.normalized_name, count(ps.id)
FROM schemes s LEFT JOIN amcs a ON a.id=s.amc_id
LEFT JOIN portfolio_snapshots ps ON ps.scheme_id=s.id
WHERE s.name ILIKE '%sbi%' GROUP BY 1,2,3 ORDER BY 4 DESC LIMIT 10
""")
print("\nSBI-named schemes:")
for r in cur.fetchall():
    print(r)
conn.close()
