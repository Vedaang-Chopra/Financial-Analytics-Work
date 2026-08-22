#!/usr/bin/env python
"""Backfill schemes.amc_id for orphaned schemes (Phase A2).

Strategies, in order:
  1. domain match: portfolio_snapshots.source_url host -> amcs website/source URLs
  2. name pattern: _resolve_amc_for_scheme_name (token/alias matching)

Unmatched schemes are LEFT UNTOUCHED — they are defunct-AMC historical rows
(ABN AMRO, ING, Fortis...) referenced by documents/nav_history. Deleting them
was evaluated and rejected: every unmatched row is still referenced.

Usage:
  python scripts/backfill_scheme_amc.py --database-url URL --dry-run
  python scripts/backfill_scheme_amc.py --database-url URL          # live
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from mutual_fund_ingestion.agent.db import (
    AMC,
    PortfolioSnapshot,
    Scheme,
    get_session_maker,
)
from mutual_fund_ingestion.agent.upserts import _resolve_amc_for_scheme_name


def backfill(database_url: str, dry_run: bool) -> dict[str, int]:
    session = get_session_maker(database_url)()
    stats = {
        "orphaned_total": 0,
        "linked_domain": 0,
        "linked_name": 0,
        "already_matched": 0,
        "unmatched_kept": 0,
    }
    try:
        amcs = session.query(AMC).all()
        domain_to_amc: dict[str, AMC] = {}
        for amc in amcs:
            for attr in ("website_url", "source_url"):
                url = getattr(amc, attr)
                if url:
                    d = urlparse(url).netloc.lower().replace("www.", "")
                    if d:
                        domain_to_amc[d] = amc

        orphans = session.query(Scheme).filter(Scheme.amc_id.is_(None)).all()
        stats["orphaned_total"] = len(orphans)
        print(f"orphaned schemes: {len(orphans)}")

        for sch in orphans:
            amc = None

            snap = session.execute(
                select(PortfolioSnapshot)
                .where(PortfolioSnapshot.scheme_id == sch.id)
                .limit(1)
            ).scalar_one_or_none()
            if snap and snap.source_url:
                d = urlparse(snap.source_url).netloc.lower().replace("www.", "")
                amc = domain_to_amc.get(d)
                if amc is None:
                    for kd, ka in domain_to_amc.items():
                        if kd in d or d in kd:
                            amc = ka
                            break

            if amc is not None:
                stats["linked_domain"] += 1
            else:
                resolved = _resolve_amc_for_scheme_name(session, sch.scheme_name)
                if resolved is not None:
                    amc = resolved
                    stats["linked_name"] += 1

            if amc is not None:
                if not dry_run:
                    sch.amc_id = amc.id
            else:
                stats["unmatched_kept"] += 1

        if dry_run:
            session.rollback()
        else:
            session.commit()
        return stats
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Backfill scheme -> AMC linkage")
    ap.add_argument("--database-url", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    s = backfill(args.database_url, args.dry_run)
    mode = "DRY-RUN" if args.dry_run else "LIVE"
    print(f"[{mode}] {s}")
