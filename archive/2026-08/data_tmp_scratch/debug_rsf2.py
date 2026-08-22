"""Compare DB rows vs sheet rows for RSF: which securities differ?
Sheet ground truth = 96.8% over 133 ISIN rows; DB says 121.5% over 136."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from db_config import mutual_funds_url

import sys, io, zipfile
sys.path.insert(0, '.')
import requests, pandas as pd
import psycopg2
from collections import Counter

url = "https://www.icicipruamc.com/blob/downloads/Files/Fortnightly%20Portfolio%20Disclosures/2026/Fortnightly%20Debt%20Scheme%20Portfolio%20-%2015th%20August%202026.zip"
resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=120)
zf = zipfile.ZipFile(io.BytesIO(resp.content))
d = pd.read_excel(io.BytesIO(zf.read("ICICI Prudential Regular Savings Fund.xlsx")), sheet_name="RSF", header=None)

mask = d[2].apply(lambda v: isinstance(v, str) and len(str(v)) == 12 and str(v)[:2].isalpha())
sheet_isins = set(d[mask][2])
sheet_dupes = Counter(d[mask][2])

conn = psycopg2.connect(mutual_funds_url())
cur = conn.cursor()
cur.execute("""SELECT h.security_name, h.isin, h.percentage_to_nav
FROM portfolio_snapshots ps JOIN schemes s ON s.id=ps.scheme_id
JOIN portfolio_holdings h ON h.snapshot_id=ps.id
WHERE s.scheme_name='ICICI Prudential Regular Savings Fund' AND ps.reporting_date='2026-08-15' AND h.isin IS NOT NULL""")
db_isins = [r[1] for r in cur.fetchall()]
db_counter = Counter(db_isins)

print("sheet distinct isins:", len(sheet_isins), "| db isin rows:", len(db_isins))
extra_in_db = [i for i in db_counter if i not in sheet_isins]
dup_db = {k: v for k, v in db_counter.items() if v > 1}
print("DB isins not on sheet:", extra_in_db)
print("DB duplicated isins:", dup_db)
# sheet-side duplicates (legit multi-lot?)
dup_sheet = {k: v for k, v in sheet_dupes.items() if v > 1}
print("sheet duplicated isins:", len(dup_sheet), list(dup_sheet.items())[:5])
