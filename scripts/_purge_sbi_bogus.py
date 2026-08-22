"""Backup + delete bogus SBI snapshots (scheme 'SCHEME NAME :' label artifact)."""
import csv
from datetime import datetime
import sys
from pathlib import Path

import psycopg2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db_config import mutual_funds_url

DB = mutual_funds_url()
conn = psycopg2.connect(DB)
cur = conn.cursor()

cur.execute("""
SELECT ps.id
FROM portfolio_snapshots ps
JOIN schemes s ON s.id = ps.scheme_id
WHERE lower(s.scheme_name) IN ('scheme name', 'scheme name :', 'name of the scheme')
   OR lower(s.normalized_scheme_name) IN ('scheme_name', 'scheme_name_')
""")
snap_ids = [r[0] for r in cur.fetchall()]
print("bogus snapshots:", len(snap_ids))
if not snap_ids:
    raise SystemExit(0)

# backup holdings
cur.execute("""
SELECT ph.* FROM portfolio_holdings ph WHERE ph.snapshot_id IN %s
""", (tuple(snap_ids),))
cols = [d[0] for d in cur.description]
rows = cur.fetchall()
stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
out = Path(f"data/backups/sbi_bogus_snap_purge_{stamp}.csv")
out.parent.mkdir(exist_ok=True)
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(cols)
    w.writerows(rows)
print(f"backed up {len(rows)} holdings -> {out}")

cur.execute("DELETE FROM portfolio_holdings WHERE snapshot_id IN %s", (tuple(snap_ids),))
print("deleted holdings:", cur.rowcount)
cur.execute("DELETE FROM portfolio_snapshots WHERE id IN %s", (tuple(snap_ids),))
print("deleted snapshots:", cur.rowcount)
conn.commit()
print("committed.")
conn.close()
