#!/usr/bin/env python
"""Populate AMC IDs for schemes based on source URLs and capability matrix."""

from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).parent.parent))

from mutual_fund_ingestion.agent.db import AMC, Scheme, PortfolioSnapshot, get_session_maker


def populate_scheme_amc_ids(database_url: str) -> dict[str, int]:
    """Populate amc_id for schemes based on portfolio snapshot source URLs."""
    session_maker = get_session_maker(database_url)
    session = session_maker()
    
    stats = {
        "total_schemes": 0,
        "updated": 0,
        "already_had_amc": 0,
        "no_url": 0,
        "domain_not_found": 0,
    }
    
    try:
        # Build domain -> AMC mapping from amcs table
        amcs = session.query(AMC).all()
        domain_to_amc = {}
        for amc in amcs:
            if amc.website_url:
                parsed = urlparse(amc.website_url)
                domain = parsed.netloc.lower().replace("www.", "")
                domain_to_amc[domain] = amc.id
            if amc.source_url:
                parsed = urlparse(amc.source_url)
                domain = parsed.netloc.lower().replace("www.", "")
                domain_to_amc[domain] = amc.id
        
        print(f"Built domain map with {len(domain_to_amc)} entries")
        for domain, amc_id in list(domain_to_amc.items())[:10]:
            print(f"  {domain} -> {amc_id}")
        
        # Get all schemes that need amc_id
        schemes = session.query(Scheme).filter(Scheme.amc_id.is_(None)).all()
        stats["total_schemes"] = len(schemes)
        print(f"Found {len(schemes)} schemes without amc_id")
        
        for scheme in schemes:
            # Find portfolio snapshots for this scheme
            snapshot = session.query(PortfolioSnapshot).filter(
                PortfolioSnapshot.scheme_id == scheme.id
            ).first()
            
            if not snapshot:
                stats["no_url"] += 1
                continue
            
            source_url = snapshot.source_url
            if not source_url:
                stats["no_url"] += 1
                continue
            
            # Extract domain from source URL
            parsed = urlparse(source_url)
            domain = parsed.netloc.lower().replace("www.", "")
            
            # Try exact match
            amc_id = domain_to_amc.get(domain)
            
            if not amc_id:
                # Try partial match (e.g., icicipruamc.com matches icici)
                for known_domain, known_amc_id in domain_to_amc.items():
                    # Check if domain contains known AMC name
                    if known_domain in domain or domain in known_domain:
                        amc_id = known_amc_id
                        break
                    # Check AMC name in domain
                    amc = session.get(AMC, known_amc_id)
                    if amc:
                        amc_norm = amc.name.lower().replace(" ", "").replace("mutual", "").replace("fund", "").strip()
                        if amc_norm and amc_norm in domain:
                            amc_id = known_amc_id
                            break
            
            if amc_id:
                scheme.amc_id = amc_id
                stats["updated"] += 1
            else:
                stats["domain_not_found"] += 1
        
        session.commit()
        return stats
        
    except Exception as e:
        session.rollback()
        print(f"Error: {e}")
        raise
    finally:
        session.close()


def update_portfolio_snapshot_amc_ids(database_url: str) -> int:
    """Update portfolio_snapshots.amc_id from scheme.amc_id."""
    from sqlalchemy import text
    session_maker = get_session_maker(database_url)
    session = session_maker()
    
    updated = 0
    try:
        # Update portfolio_snapshots.amc_id from scheme
        result = session.execute(text("""
            UPDATE portfolio_snapshots ps
            SET amc_id = s.amc_id
            FROM schemes s
            WHERE ps.scheme_id = s.id
            AND ps.amc_id IS NULL
            AND s.amc_id IS NOT NULL
        """))
        updated = result.rowcount
        session.commit()
        return updated
    except Exception as e:
        session.rollback()
        print(f"Error: {e}")
        raise
    finally:
        session.close()


def populate_nav_scheme_amc_ids(database_url: str) -> int:
    """Populate amc_id for NAV schemes based on scheme_code lookup in portfolio schemes."""
    session_maker = get_session_maker(database_url)
    session = session_maker()
    
    updated = 0
    try:
        # For NAV schemes with scheme_code but no amc_id, try to find matching portfolio scheme
        nav_schemes = session.query(Scheme).filter(
            Scheme.scheme_code.isnot(None),
            Scheme.amc_id.is_(None)
        ).all()
        
        for nav_scheme in nav_schemes:
            # Find portfolio scheme with same scheme_code
            p_scheme = session.query(Scheme).filter(
                Scheme.scheme_code == nav_scheme.scheme_code,
                Scheme.amc_id.isnot(None)
            ).first()
            
            if p_scheme:
                nav_scheme.amc_id = p_scheme.amc_id
                updated += 1
        
        session.commit()
        return updated
        
    except Exception as e:
        session.rollback()
        print(f"Error: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Populate scheme AMC IDs")
    parser.add_argument("--database-url", required=True, help="PostgreSQL connection URL")
    args = parser.parse_args()
    
    print("Step 1: Populate scheme amc_id from portfolio source URLs...")
    stats1 = populate_scheme_amc_ids(args.database_url)
    print(f"  Updated: {stats1['updated']}, Already had: {stats1['already_had_amc']}, No URL: {stats1['no_url']}, Domain not found: {stats1['domain_not_found']}")
    
    print("\nStep 2: Update portfolio_snapshots amc_id...")
    updated2 = update_portfolio_snapshot_amc_ids(args.database_url)
    print(f"  Updated: {updated2}")
    
    print("\nStep 3: Populate NAV scheme amc_id from portfolio scheme matches...")
    updated3 = populate_nav_scheme_amc_ids(args.database_url)
    print(f"  Updated: {updated3}")
    
    print("\nDone!")