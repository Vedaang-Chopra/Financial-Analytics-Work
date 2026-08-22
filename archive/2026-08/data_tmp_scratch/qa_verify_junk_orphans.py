"""Verify orphaned-unmatched schemes are unreferenced before deletion.

For every orphaned scheme NOT linkable by domain-match or name-pattern,
check references from: portfolio_snapshots, nav_history, documents.
Any referenced scheme is kept and reported.
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

from mutual_fund_ingestion.agent.db import (
    AMC, Document, NAVHistory, PortfolioSnapshot, Scheme, get_session_maker,
)
from mutual_fund_ingestion.agent.upserts import _resolve_amc_for_scheme_name

DB = mutual_funds_url()
session = get_session_maker(DB)()

amcs = session.query(AMC).all()
domain_to_amc = {}
for amc in amcs:
    for attr in ("website_url", "source_url"):
        url = getattr(amc, attr)
        if url:
            d = urlparse(url).netloc.lower().replace("www.", "")
            if d:
                domain_to_amc[d] = amc

orphans = session.query(Scheme).filter(Scheme.amc_id.is_(None)).all()

unreferenced_ids = []
referenced = []
for sch in orphans:
    snap = session.execute(
        select(PortfolioSnapshot).where(PortfolioSnapshot.scheme_id == sch.id).limit(1)
    ).scalar_one_or_none()
    matched = False
    if snap and snap.source_url:
        d = urlparse(snap.source_url).netloc.lower().replace("www.", "")
        amc = domain_to_amc.get(d)
        if not amc:
            for kd, ka in domain_to_amc.items():
                if kd in d or d in kd:
                    amc = ka
                    break
        matched = amc is not None
    if not matched:
        matched = _resolve_amc_for_scheme_name(session, sch.scheme_name) is not None
    if matched:
        continue

    # candidate for deletion — verify zero references anywhere
    n_snap = session.execute(
        select(PortfolioSnapshot.id).where(PortfolioSnapshot.scheme_id == sch.id).limit(1)
    ).scalar_one_or_none()
    n_nav = session.execute(
        select(NAVHistory.id).where(NAVHistory.scheme_id == sch.id).limit(1)
    ).scalar_one_or_none()
    n_doc = session.execute(
        select(Document.id).where(Document.scheme_id == sch.id).limit(1)
    ).scalar_one_or_none()
    if n_snap or n_nav or n_doc:
        referenced.append((sch.id, sch.scheme_name, bool(n_snap), bool(n_nav), bool(n_doc)))
    else:
        unreferenced_ids.append(sch.id)

print(f"linkable orphans (will be linked): {len(orphans) - len(unreferenced_ids) - len(referenced)}")
print(f"unmatched BUT referenced (keep): {len(referenced)}")
for r in referenced[:10]:
    print("  REF:", r)
print(f"unmatched and fully unreferenced (safe to delete): {len(unreferenced_ids)}")

with open('data/tmp/orphan_delete_ids.txt', 'w') as f:
    f.write('\n'.join(str(i) for i in unreferenced_ids))
print("ids written to data/tmp/orphan_delete_ids.txt")
session.close()
