"""QA: simulate populate_scheme_amc linking strategies against live DB (no writes).

Strategies tested:
  S1: snapshot.source_url domain -> amcs.website_url/source_url domain map
  S2: name-pattern resolution (_resolve_amc_for_scheme_name)
Reports how many of the 2,505 orphaned schemes each strategy would link.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from db_config import mutual_funds_url

import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import select

from mutual_fund_ingestion.agent.db import AMC, PortfolioSnapshot, Scheme, get_session_maker
from mutual_fund_ingestion.agent.upserts import _resolve_amc_for_scheme_name

DB = mutual_funds_url()
session = get_session_maker(DB)()

amcs = session.query(AMC).all()
print(f"AMCs in table: {len(amcs)}")
domain_to_amc = {}
for amc in amcs:
    for attr in ("website_url", "source_url"):
        url = getattr(amc, attr)
        if url:
            d = urlparse(url).netloc.lower().replace("www.", "")
            if d:
                domain_to_amc[d] = amc

orphans = session.query(Scheme).filter(Scheme.amc_id.is_(None)).all()
print(f"orphaned schemes: {len(orphans)}")

s1_ok = s2_ok = s12_ok = none_ok = 0
unmatched_sample = []
for sch in orphans:
    # S1: any snapshot source_url domain match
    snap = session.execute(
        select(PortfolioSnapshot)
        .where(PortfolioSnapshot.scheme_id == sch.id)
        .limit(1)
    ).scalar_one_or_none()
    hit1 = False
    if snap and snap.source_url:
        d = urlparse(snap.source_url).netloc.lower().replace("www.", "")
        amc = domain_to_amc.get(d)
        if not amc:
            for kd, ka in domain_to_amc.items():
                if kd in d or d in kd:
                    amc = ka
                    break
        if amc is not None:
            hit1 = True
    hit2 = _resolve_amc_for_scheme_name(session, sch.scheme_name) is not None
    if hit1:
        s1_ok += 1
    if hit2:
        s2_ok += 1
    if hit1 or hit2:
        s12_ok += 1
    else:
        none_ok += 1
        if len(unmatched_sample) < 15:
            unmatched_sample.append(sch.scheme_name)

print(f"S1 domain-match would link: {s1_ok}")
print(f"S2 name-pattern would link: {s2_ok}")
print(f"S1|S2 combined: {s12_ok}")
print(f"still unmatched: {none_ok}")
print("sample unmatched:")
for n in unmatched_sample:
    print("  -", n)
session.close()
