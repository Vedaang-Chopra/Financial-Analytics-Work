"""One-off: remove ICICI grouping-header rows that the old parser leaked into
canonical holdings (472 rows across 341 snapshots). Backup CSV first, per
project convention."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from db_config import mutual_funds_url

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import psycopg2

conn = psycopg2.connect(mutual_funds_url())
cur = conn.cursor()

cur.execute("""
    SELECT h.id, ps.id, h.security_name, h.isin, h.percentage_to_nav
    FROM portfolio_holdings h
    JOIN portfolio_snapshots ps ON ps.id = h.snapshot_id
    WHERE ps.source_url LIKE '%icicipruamc%'
      AND (h.security_name ILIKE 'non-convertible debentures / bonds'
           OR h.security_name ILIKE 'zero coupon bonds / deep discount bonds')
""")
rows = cur.fetchall()
print("rows to purge:", len(rows))

out = Path("data/tmp/backup_icici_header_rows_2026-08-22.csv")
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["holding_id", "snapshot_id", "security_name", "isin", "percentage_to_nav"])
    w.writerows(rows)
print("backup written:", out)

cur.execute("""
    DELETE FROM portfolio_holdings h
    USING portfolio_snapshots ps
    WHERE ps.id = h.snapshot_id
      AND ps.source_url LIKE '%icicipruamc%'
      AND (h.security_name ILIKE 'non-convertible debentures / bonds'
           OR h.security_name ILIKE 'zero coupon bonds / deep discount bonds')
""")
print("deleted:", cur.rowcount)
conn.commit()

# re-check allocation sanity for icici
cur.execute("""
SELECT count(*) FILTER (WHERE pct BETWEEN 90 AND 110) ok,
       count(*) FILTER (WHERE pct NOT BETWEEN 90 AND 110) bad
FROM (
  SELECT ps.id, SUM(h.percentage_to_nav) pct
  FROM portfolio_snapshots ps
  JOIN schemes s ON s.id = ps.scheme_id
  JOIN amcs a ON a.id = s.amc_id
  JOIN portfolio_holdings h ON h.snapshot_id = ps.id
  WHERE a.name = 'ICICI Prudential Mutual Fund'
  GROUP BY ps.id
) t
""")
print("icici sanity ok/bad after purge:", cur.fetchone())
conn.close()
