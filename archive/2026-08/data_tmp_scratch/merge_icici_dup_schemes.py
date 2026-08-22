"""One-off: merge duplicate ICICI scheme rows (same normalized name under the
ICICI AMC). Keep the canonical row (with scheme_code, else earliest), move
snapshots/documents to it, delete the losers. Backup first."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from db_config import mutual_funds_url

import csv
from pathlib import Path
import psycopg2

conn = psycopg2.connect(mutual_funds_url())
cur = conn.cursor()

cur.execute("""
    SELECT s.normalized_scheme_name,
           (array_agg(s.id ORDER BY (s.scheme_code IS NULL), s.created_at))[1] AS keep_id,
           array_agg(s.id::text ORDER BY (s.scheme_code IS NULL), s.created_at) AS all_ids
    FROM schemes s
    WHERE s.amc_id = (SELECT id FROM amcs WHERE name = 'ICICI Prudential Mutual Fund')
    GROUP BY s.normalized_scheme_name
    HAVING count(*) > 1
""")
groups = cur.fetchall()
print("dup groups:", len(groups))

merge_plan = []  # (keep_id, [drop_ids])
for name, keep_id, all_ids in groups:
    drops = [i for i in all_ids if i != keep_id]
    merge_plan.append((keep_id, drops))

# backup: all snapshots + scheme rows that will move
out = Path("data/tmp/backup_scheme_merge_icici_2026-08-22.csv")
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["keep_id", "drop_id"])
    for keep_id, drops in merge_plan:
        for d in drops:
            w.writerow([keep_id, d])
print("backup:", out)

moved_snaps = moved_docs = 0
for keep_id, drops in merge_plan:
    for d in drops:
        cur.execute("UPDATE portfolio_snapshots SET scheme_id=%s WHERE scheme_id=%s", (keep_id, d))
        moved_snaps += cur.rowcount
        cur.execute("UPDATE documents SET scheme_id=%s WHERE scheme_id=%s", (keep_id, d))
        moved_docs += cur.rowcount
        cur.execute("UPDATE nav_history SET scheme_id=%s WHERE scheme_id=%s", (keep_id, d))
        for table in ("scheme_coverage", "coverage_alerts"):
            try:
                cur.execute(f"DELETE FROM {table} WHERE scheme_id=%s", (d,))
            except Exception:
                conn.rollback()
        cur.execute("DELETE FROM schemes WHERE id=%s", (d,))
print("snapshots moved:", moved_snaps, "| docs moved:", moved_docs)
conn.commit()

# now delete snapshot duplicates that arose (same scheme_id+date, multiple rows)
cur.execute("""
    SELECT count(*) FROM (
      SELECT scheme_id, reporting_date FROM portfolio_snapshots
      GROUP BY 1,2 HAVING count(*)>1
    ) t
""")
print("dup snapshot groups after merge:", cur.fetchone()[0])
conn.close()
