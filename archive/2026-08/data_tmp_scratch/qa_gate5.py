"""Deeper check: for PPFAS disk artifacts, is there a portfolio_snapshot whose
scheme+reporting_date matches what this file would produce? The document join
may miss because snapshots were created under a different raw_artifact row."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from db_config import mutual_funds_url

import sys
from pathlib import Path
sys.path.insert(0, str(Path('.').resolve()))
from sqlalchemy import text
from mutual_fund_ingestion.agent.db import get_session_maker
import re

DB = mutual_funds_url()
session = get_session_maker(DB)()

# PPFAS snapshot dates in DB
dates = set(r[0] for r in session.execute(text("""
SELECT DISTINCT ps.reporting_date FROM portfolio_snapshots ps
JOIN schemes s ON s.id=ps.scheme_id JOIN amcs a ON a.id=s.amc_id
WHERE a.name='PPFAS Mutual Fund'
""")).fetchall())
print("ppfas reporting_dates in DB:", len(dates))

# extract month-year from the on-disk ppfas file urls and check coverage
rows = session.execute(text("""
SELECT ra.checksum, ra.source_url FROM raw_artifacts ra
WHERE ra.local_path IS NOT NULL AND ra.checksum IS NOT NULL
  AND ra.source_url LIKE '%ppfas%portfolio-disclosure%'
  AND (ra.source_url ILIKE '%monthly%' OR ra.source_url ILIKE '%fortnightly%')
""")).fetchall()

MONTHS = dict(zip(["january","february","march","april","may","june","july","august",
                   "september","october","november","december"], range(1,13)))
covered = 0
for cs, url in rows:
    m = re.search(r'(\w+)[-_](\d{4})', url.lower())
    if not m:
        continue
    mon = MONTHS.get(m.group(1))
    if mon and any(d.year == int(m.group(2)) and d.month == mon for d in dates):
        covered += 1
print(f"disk files whose month-year exists in DB: {covered} / {len(rows)}")
