"""Acceptance check: snapshots + holdings + pct sums per new AMC."""
import sys
from pathlib import Path

import psycopg2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db_config import mutual_funds_url

DB = mutual_funds_url()
q = """
SELECT a.normalized_name, count(DISTINCT ps.id) AS snapshots, count(ph.id) AS holdings
FROM amcs a
JOIN schemes s ON s.amc_id = a.id
LEFT JOIN portfolio_snapshots ps ON ps.scheme_id = s.id
LEFT JOIN portfolio_holdings ph ON ph.snapshot_id = ps.id
WHERE a.normalized_name ILIKE ANY(ARRAY['%%sbi%%','%%hdfc%%','%%nippon%%','%%uti%%','%%franklin%%','%%kotak%%'])
GROUP BY a.normalized_name ORDER BY a.normalized_name;
"""
q2 = """
SELECT a.normalized_name, ps.id, ps.reporting_date, count(ph.id) AS n,
       sum(ph.percentage_to_nav) AS pct_sum
FROM amcs a
JOIN schemes s ON s.amc_id = a.id
JOIN portfolio_snapshots ps ON ps.scheme_id = s.id
JOIN portfolio_holdings ph ON ph.snapshot_id = ps.id
WHERE a.normalized_name ILIKE ANY(ARRAY['%%sbi%%','%%hdfc%%','%%nippon%%','%%uti%%','%%franklin%%'])
GROUP BY a.normalized_name, ps.id, ps.reporting_date
ORDER BY a.normalized_name, ps.reporting_date DESC
"""
conn = psycopg2.connect(DB)
cur = conn.cursor()
print("=== per-AMC totals:")
cur.execute(q)
for row in cur.fetchall():
    print("  ", row)
print("=== sample snapshot pct sums (top per amc):")
cur.execute(q2)
seen = {}
for name, psid, rd, n, s in cur.fetchall():
    seen.setdefault(name, []).append((str(rd), psid, n, float(s) if s is not None else None))
for name, rows in seen.items():
    ok = [r for r in rows if r[2] >= 10 and r[3] is not None and 90 <= r[3] <= 110]
    print(f"  {name}: snapshots={len(rows)} passing_acceptance={len(ok)} e.g. {ok[:2]}")
conn.close()
