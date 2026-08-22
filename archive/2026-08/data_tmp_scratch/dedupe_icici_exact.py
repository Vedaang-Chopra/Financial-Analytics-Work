"""One-off cleanup: dedupe exact-duplicate holdings rows created across the
repeated reparse runs (same snapshot, same name+isin, same pct). Keep min(id).
Backup first."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from db_config import mutual_funds_url

import csv
from pathlib import Path
import psycopg2

conn = psycopg2.connect(mutual_funds_url())
cur = conn.cursor()

# duplicates = same (snapshot, security_name, isin, percentage_to_nav) with >1 row
cur.execute("""
    SELECT count(*) FROM (
      SELECT snapshot_id, security_name, isin, percentage_to_nav
      FROM portfolio_holdings
      GROUP BY 1,2,3,4 HAVING count(*) > 1
    ) t
""")
print("duplicate groups:", cur.fetchone()[0])

cur.execute("""
    SELECT h.id, h.snapshot_id, h.security_name, h.isin, h.percentage_to_nav
    FROM portfolio_holdings h
    JOIN (
      SELECT snapshot_id, security_name, isin, percentage_to_nav,
             min(id::text) AS keep_id
      FROM portfolio_holdings
      GROUP BY 1,2,3,4 HAVING count(*) > 1
    ) d ON d.snapshot_id=h.snapshot_id AND d.security_name=h.security_name
       AND d.isin IS NOT DISTINCT FROM h.isin AND d.percentage_to_nav=h.percentage_to_nav
       AND h.id::text <> d.keep_id
""")
rows = cur.fetchall()
print("rows to delete:", len(rows))

out = Path("data/tmp/backup_exact_dupes_2026-08-22.csv")
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["holding_id", "snapshot_id", "security_name", "isin", "pct"])
    w.writerows(rows)
print("backup:", out)

cur.execute("""
    DELETE FROM portfolio_holdings h
    USING (
      SELECT snapshot_id, security_name, isin, percentage_to_nav,
             min(id::text) AS keep_id
      FROM portfolio_holdings
      GROUP BY 1,2,3,4 HAVING count(*) > 1
    ) d
    WHERE d.snapshot_id=h.snapshot_id AND d.security_name=h.security_name
       AND d.isin IS NOT DISTINCT FROM h.isin AND d.percentage_to_nav=h.percentage_to_nav
       AND h.id::text <> d.keep_id
""")
print("deleted:", cur.rowcount)
conn.commit()

cur.execute("""
SELECT count(*) FILTER (WHERE pct BETWEEN 90 AND 110) ok,
       count(*) FILTER (WHERE pct NOT BETWEEN 90 AND 110) bad
FROM (SELECT ps.id, SUM(h.percentage_to_nav) pct FROM portfolio_snapshots ps
JOIN schemes s ON s.id=ps.scheme_id JOIN amcs a ON a.id=s.amc_id
JOIN portfolio_holdings h ON h.snapshot_id=ps.id
WHERE a.name='ICICI Prudential Mutual Fund' GROUP BY ps.id) t""")
print("icici sanity ok/bad:", cur.fetchone())
conn.close()
