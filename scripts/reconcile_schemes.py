#!/usr/bin/env python
"""Reconcile scheme identities between NAV and portfolio data."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mutual_fund_ingestion.agent.db import (
    AMC,
    Scheme,
    PortfolioSnapshot,
    NAVHistory,
    get_session_maker,
)
from mutual_fund_ingestion.agent.scheme_identity import SchemeIdentityResolver
from utils.text_utils import normalize_amc_name


def reconcile_schemes(database_url: str) -> dict[str, int]:
    """Reconcile NAV schemes with portfolio schemes."""
    session_maker = get_session_maker(database_url)
    session = session_maker()
    
    resolver = SchemeIdentityResolver(database_url)
    resolver._load_caches(session)
    
    stats = {
        "nav_schemes_total": 0,
        "portfolio_schemes_total": 0,
        "nav_schemes_updated": 0,
        "portfolio_schemes_updated": 0,
        "amc_id_populated": 0,
        "scheme_code_populated": 0,
        "merged": 0,
    }
    
    try:
        # Get all NAV schemes
        nav_schemes = session.query(Scheme).filter(Scheme.scheme_code.isnot(None)).all()
        stats["nav_schemes_total"] = len(nav_schemes)
        print(f"Found {len(nav_schemes)} NAV schemes with scheme_code")
        
        # Get all portfolio schemes (from snapshots)
        portfolio_scheme_ids = session.query(PortfolioSnapshot.scheme_id).distinct().all()
        portfolio_scheme_ids = [sid[0] for sid in portfolio_scheme_ids]
        portfolio_schemes = session.query(Scheme).filter(Scheme.id.in_(portfolio_scheme_ids)).all()
        stats["portfolio_schemes_total"] = len(portfolio_schemes)
        print(f"Found {len(portfolio_schemes)} portfolio schemes from snapshots")
        
        # For each portfolio scheme, try to match with NAV scheme
        for p_scheme in portfolio_schemes:
            if p_scheme.scheme_code:
                continue  # Already has scheme_code
            
            # Try to match by name
            if p_scheme.scheme_name:
                normalized_name = normalize_amc_name(p_scheme.scheme_name)
                
                # Check exact normalized name match
                if normalized_name in resolver._normalized_name_cache:
                    candidates = resolver._normalized_name_cache[normalized_name]
                    if candidates:
                        nav_scheme = candidates[0]
                        # Update portfolio scheme with NAV scheme_code
                        p_scheme.scheme_code = nav_scheme.scheme_code
                        p_scheme.normalized_scheme_name = nav_scheme.normalized_scheme_name
                        nav_amc_id = getattr(nav_scheme, 'amc_id', None)
                        if nav_amc_id is not None:
                            p_scheme.amc_id = nav_amc_id
                        stats["scheme_code_populated"] += 1
                        stats["merged"] += 1
                        continue
                
                # Try fuzzy match
                nav_matches = session.query(Scheme).filter(
                    Scheme.normalized_scheme_name.ilike(f"%{normalized_name}%"),
                    Scheme.scheme_code.isnot(None)
                ).limit(5).all()
                
                if nav_matches:
                    best_match = max(nav_matches, key=lambda s: len(set(normalized_name.split()) & set(s.normalized_scheme_name.split())))
                    if best_match:
                        p_scheme.scheme_code = best_match.scheme_code
                        best_amc_id = getattr(best_match, 'amc_id', None)
                        if best_amc_id is not None:
                            p_scheme.amc_id = best_amc_id
                        stats["scheme_code_populated"] += 1
                        stats["merged"] += 1
        
        # Now update NAV schemes with AMC info from portfolio schemes
        for n_scheme in nav_schemes:
            nav_amc_id = getattr(n_scheme, 'amc_id', None)
            if nav_amc_id is not None:
                continue
            
            # Try to find portfolio scheme with same scheme_code
            p_scheme = session.query(Scheme).filter(
                Scheme.scheme_code == n_scheme.scheme_code,
                Scheme.amc_id.isnot(None)
            ).first()
            
            if p_scheme:
                p_amc_id = getattr(p_scheme, 'amc_id', None)
                if p_amc_id is not None:
                    n_scheme.amc_id = p_amc_id
                    stats["amc_id_populated"] += 1
            else:
                # Try to infer AMC from scheme name
                if n_scheme.scheme_name and n_scheme.scheme_name != f"Scheme {n_scheme.scheme_code}":
                    # This is a real name, try to extract AMC
                    name_lower = n_scheme.scheme_name.lower()
                    # Query schemes that have amc_id populated
                    amc_schemes = session.query(Scheme).filter(Scheme.amc_id.isnot(None)).all()
                    
                    # Build AMC name map
                    amc_names = {}
                    for s in amc_schemes:
                        s_amc_id = getattr(s, 'amc_id', None)
                        if s_amc_id is not None:
                            amc = session.get(AMC, s_amc_id)
                            if amc:
                                amc_names[normalize_amc_name(amc.name)] = amc.id
                    
                    for amc_norm_name, amc_id in amc_names.items():
                        if amc_norm_name in name_lower:
                            n_scheme.amc_id = amc_id
                            stats["amc_id_populated"] += 1
                            break
        
        session.commit()
        return stats
        
    except Exception as e:
        session.rollback()
        print(f"Error: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Reconcile scheme identities")
    parser.add_argument("--database-url", required=True, help="PostgreSQL connection URL")
    args = parser.parse_args()
    
    stats = reconcile_schemes(args.database_url)
    print("\nReconciliation complete:")
    for k, v in stats.items():
        print(f"  {k}: {v}")