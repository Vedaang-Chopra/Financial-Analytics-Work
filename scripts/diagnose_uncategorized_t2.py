#!/usr/bin/env python
"""T2 diagnostic: profile uncategorized schemes vs AMFI rolling scheme master."""
import csv
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.text_utils import normalize_amc_name
from db_config import mutual_funds_url

MASTER = Path("data/raw/mutual_funds/files/amfi_scheme_master_20260822T010444Z.csv")
DB_URL = mutual_funds_url()

rows = list(csv.DictReader(MASTER.open(encoding="utf-8-sig", newline="")))
master_codes = {}
master_norm_names = {}
for r in rows:
    code = r["Code"].strip()
    cat = (r.get("Scheme Category") or "").strip()
    sub = cat.split(" - ", 1)
    if code:
        master_codes[code] = (cat, sub[1] if len(sub) > 1 else None,
                              (r.get("Closure Date") or "").strip())
    nm = normalize_amc_name(r["Scheme Name"].strip())
    master_norm_names.setdefault(nm, (cat, sub[1] if len(sub) > 1 else None))
print(f"master rows={len(rows)} codes={len(master_codes)} norm_names={len(master_norm_names)}")
closed_in_master = sum(1 for v in master_codes.values() if v[2] and v[2] != "01-Jan-1970" and v[2] != "")
print(f"master rows with closure date set: {closed_in_master}")

import sqlalchemy as sa
eng = sa.create_engine(DB_URL)
with eng.connect() as conn:
    res = conn.execute(sa.text(
        "SELECT id::text, scheme_code, scheme_name, normalized_scheme_name, amc_id::text "
        "FROM schemes WHERE category IS NULL"))
    uncat = res.fetchall()

print(f"uncategorized in DB: {len(uncat)}")

by_code = by_name = by_amc_name = 0
amc_names = {}
if uncat:
    amc_ids = {u[4] for u in uncat}
    amap = {}
    with eng.connect() as conn:
        for aid, aname in conn.execute(sa.text("SELECT id::text, name FROM amcs")):
            amap[aid] = aname

code_hits, name_hits = [], []
for sid, code, name, nname, amc_id in uncat:
    if code and code in master_codes:
        by_code += 1
        code_hits.append((name, master_codes[code][0]))
    elif nname in master_norm_names:
        by_name += 1
        name_hits.append(name)

print(f"uncategorized matched BY CODE against master: {by_code}")
print(f"uncategorized matched BY EXACT NORM NAME (not code): {by_name}")

# Why did code matches remain uncategorized? Maybe upsert didn't run over these codes
# because validate failed or parser skipped. Show samples.
for n, c in code_hits[:10]:
    print("  CODE-HIT:", n[:70], "->", c)

# For remaining unmatched, try stripping plan/option tokens then match fund base name
PLAN_RE = re.compile(
    r"\b(direct|regular|institutional|institutional\s+plus|retail|wholesale)\s*(plan)?\b", re.I)
OPT_RE = re.compile(
    r"\b(growth|idcw|dividend(\s+(payout|reinvestment))?|bonus|option|payout|reinvestment|"
    r"annual|monthly|quarterly|weekly|daily|mly|qtrly|half\s*yearly)\b", re.I)

def fund_base(name: str) -> str:
    s = name.lower()
    s = re.sub(r"[(_\-/]", " ", s)
    s = PLAN_RE.sub(" ", s)
    s = OPT_RE.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return normalize_amc_name(s) if s else ""

master_base = {}
for nm, (cat, sub) in master_norm_names.items():
    fb = fund_base(nm)
    if fb:
        master_base.setdefault(fb, (cat, sub))

base_hit = 0
unmatched_samples = Counter()
unmatched_list = []
for sid, code, name, nname, amc_id in uncat:
    if (code and code in master_codes) or (nname in master_norm_names):
        continue
    fb = fund_base(name)
    if fb in master_base:
        base_hit += 1
    else:
        unmatched_list.append((amap.get(amc_id), name))

print(f"uncategorized matched after plan/option STRIP (fund-base): {base_hit}")
print(f"still unmatched: {len(unmatched_list)}")
for amc, n in unmatched_list[:30]:
    print(f"  UNMATCHED [{amc}] {n[:85]}")

# bucket still-unmatched by AMC
cnt = Counter(amc for amc, _ in unmatched_list)
print("\nstill-unmatched by AMC (top 15):")
for amc, c in cnt.most_common(15):
    print(f"  {amc}: {c}")

# how many uncategorized have no scheme_code at all
nocode = sum(1 for _, c, *_ in uncat if not c)
print(f"\nuncategorized with NULL scheme_code: {nocode}")

# consensus_panel distinct scheme coverage baseline
with eng.connect() as conn:
    tot, null_cat = conn.execute(sa.text(
        "SELECT count(DISTINCT ps.scheme_id), "
        "count(DISTINCT ps.scheme_id) FILTER (WHERE s.category IS NULL) "
        "FROM portfolio_snapshots ps JOIN schemes s ON s.id=ps.scheme_id")).fetchone()
    print(f"\npanel-basis proxy (portfolio_snapshots): total distinct schemes={tot}, uncategorized={null_cat}")
