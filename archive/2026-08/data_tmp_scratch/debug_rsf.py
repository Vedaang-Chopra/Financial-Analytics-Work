"""Regular Savings: 118-123% — find what's double counted. Compare DB holdings
against the raw sheet rows with ISINs (ground truth)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from db_config import mutual_funds_url

import sys, io, zipfile
sys.path.insert(0, '.')
import requests, pandas as pd
import psycopg2

url = "https://www.icicipruamc.com/blob/downloads/Files/Fortnightly%20Portfolio%20Disclosures/2026/Fortnightly%20Debt%20Scheme%20Portfolio%20-%2015th%20August%202026.zip"
resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=120)
zf = zipfile.ZipFile(io.BytesIO(resp.content))
d = pd.read_excel(io.BytesIO(zf.read("ICICI Prudential Regular Savings Fund.xlsx")), sheet_name="RSF", header=None)

# ground truth: rows with valid ISIN, sum their pct
isin_vals = d[2]
mask = isin_vals.apply(lambda v: isinstance(v, str) and len(str(v)) == 12 and str(v)[:2].isalpha())
truth = d[mask]
truth_pct = pd.to_numeric(truth[7], errors="coerce")
print("sheet rows with ISIN:", mask.sum(), "| pct sum:", round(truth_pct.sum(), 4))

# DB holdings for that snapshot
conn = psycopg2.connect(mutual_funds_url())
cur = conn.cursor()
cur.execute("""SELECT h.security_name, h.isin, h.percentage_to_nav
FROM portfolio_snapshots ps JOIN schemes s ON s.id=ps.scheme_id
JOIN portfolio_holdings h ON h.snapshot_id=ps.id
WHERE s.scheme_name='ICICI Prudential Regular Savings Fund' AND ps.reporting_date='2026-08-15'""")
rows = cur.fetchall()
db_pct = sum(float(r[2] or 0) for r in rows)
print("DB holdings:", len(rows), "| pct sum:", round(db_pct, 4))

# rows in DB with pct but no ISIN (suspects)
no_isin = [(r[0], float(r[2] or 0)) for r in rows if not r[1]]
print("DB rows without ISIN:", len(no_isin))
for r in no_isin[:15]:
    print("  ", r)
