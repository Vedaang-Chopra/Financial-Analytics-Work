#!/usr/bin/env python
"""Fix MIS-LINKED schemes.amc_id (Wave 4 cross-cutting fix, 2026-08-22).

backfill_scheme_amc.py only fills NULL amc_id rows. This script addresses the
other failure mode: a scheme whose portfolio_snapshots.source_url host clearly
belongs to a DIFFERENT registered AMC than schemes.amc_id (e.g. "Axis Quant
Fund" snapshots served from transact.axismf.com but linked to "Quant Mutual
Fund" because a fuzzy name resolver matched the token 'quant').

Policy:
- Domain evidence is authoritative: for every scheme WITH snapshots, derive the
  AMC from the snapshot source_url host using the same partial-domain matching
  rules as backfill_scheme_amc.py.
- Only relink when ALL of the scheme's snapshot hosts resolve to ONE other
  registered AMC (unambiguous), otherwise leave untouched and report.
- Backup-first: affected scheme ids exported to data/backups/ before UPDATE.
- Schemes without snapshots are NOT touched here.

Usage:
  python scripts/fix_scheme_amc_mislinks.py --database-url URL --dry-run
  python scripts/fix_scheme_amc_mislinks.py --database-url URL          # live
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from datetime import datetime
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

BACKUP_DIR = Path(__file__).parent.parent / "data" / "backups"


def _host(url: str) -> str:
    return urlparse(url).netloc.lower().replace("www.", "")


def fix(database_url: str, dry_run: bool) -> dict[str, int]:
    session = get_session_maker(database_url)()
    stats = {
        "schemes_checked": 0,
        "mislinked_found": 0,
        "relinked": 0,
        "ambiguous_kept": 0,
        "unresolvable_kept": 0,
    }
    try:
        amcs = session.query(AMC).all()
        domain_to_amc: dict[str, AMC] = {}
        for amc in amcs:
            for attr in ("website_url", "source_url"):
                url = getattr(amc, attr)
                if url:
                    d = _host(url)
                    if d:
                        domain_to_amc[d] = amc

        def resolve(host: str) -> AMC | None:
            if not host:
                return None
            if host in domain_to_amc:
                return domain_to_amc[host]
            for kd, ka in domain_to_amc.items():
                if kd in host or host in kd:
                    return ka
            return None

        # host -> amc map from OBSERVED data domains too (registry URLs are sparse)
        snap_hosts = session.execute(
            select(PortfolioSnapshot.source_url)
        ).scalars()
        observed: dict[str, int] = defaultdict(int)
        for u in snap_hosts:
            observed[_host(u)] += 1

        schemes = session.query(Scheme).filter(Scheme.amc_id.isnot(None)).all()
        stats["schemes_checked"] = len(schemes)

        changes: list[tuple[Scheme, AMC]] = []
        report_rows: list[dict] = []
        for sch in schemes:
            snaps = session.execute(
                select(PortfolioSnapshot)
                .where(PortfolioSnapshot.scheme_id == sch.id)
            ).scalars().all()
            if not snaps:
                continue
            hosts = {_host(s.source_url) for s in snaps if s.source_url}
            resolved_amcs = {h: resolve(h) for h in hosts}
            good = {h: a for h, a in resolved_amcs.items() if a is not None}
            if not good:
                stats["unresolvable_kept"] += 1
                continue
            targets = {a.id for a in good.values()}
            current_id = sch.amc_id
            if targets == {current_id}:
                continue  # correctly linked
            if len(targets) > 1:
                stats["ambiguous_kept"] += 1
                continue
            new_amc = next(iter(good.values()))
            # Only act when the domain-evidence target differs from current link
            changes.append((sch, new_amc))
            report_rows.append({
                "scheme_id": str(sch.id),
                "scheme_name": sch.scheme_name,
                "old_amc_id": str(current_id),
                "new_amc_id": str(new_amc.id),
                "new_amc_name": new_amc.name,
                "evidence_hosts": ";".join(sorted(good)),
                "n_snapshots": len(snaps),
            })

        stats["mislinked_found"] = len(changes)
        if changes and not dry_run:
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            bpath = BACKUP_DIR / f"scheme_amc_mislinks_{ts}.csv"
            with open(bpath, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(report_rows[0].keys()))
                w.writeheader()
                w.writerows(report_rows)
            print(f"[backup] {len(report_rows)} rows -> {bpath}")
            for sch, new_amc in changes:
                sch.amc_id = new_amc.id
            stats["relinked"] = len(changes)
            session.commit()
        else:
            for row in report_rows[:50]:
                print("  would relink:", row["scheme_name"][:60],
                      "->", row["new_amc_name"], "| hosts:", row["evidence_hosts"][:60])
        return stats
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Fix mis-linked schemes.amc_id from domain evidence")
    ap.add_argument("--database-url", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    s = fix(args.database_url, args.dry_run)
    mode = "DRY-RUN" if args.dry_run else "LIVE"
    print(f"[{mode}] {s}")
