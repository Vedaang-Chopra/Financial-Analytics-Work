#!/usr/bin/env python
"""Load AMCs from configs/amc_sources.yaml into PostgreSQL amcs table."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from mutual_fund_ingestion.agent.db import AMC, get_session_maker
from utils.text_utils import normalize_amc_name


def load_amcs(database_url: str) -> int:
    """Load AMCs from amc_sources.yaml into database."""
    config_path = Path(__file__).parent.parent / "configs" / "amc_sources.yaml"
    
    try:
        with open(config_path) as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Config file not found: {config_path}")
        return 0
    except yaml.YAMLError as e:
        print(f"Invalid YAML: {e}")
        return 0
    
    session_maker = get_session_maker(database_url)
    session = session_maker()
    
    loaded = 0
    skipped = 0
    
    try:
        for source in data.get("sources", []):
            if not source.get("enabled", True):
                continue
                
            amc_name = source.get("amc_name") or source.get("source_name")
            if not amc_name:
                continue
            
            normalized = normalize_amc_name(amc_name)
            seed_url = source.get("seed_url", "")
            
            # Check if already exists
            existing = session.query(AMC).filter(AMC.normalized_name == normalized).first()
            if existing:
                # Update existing
                existing.name = amc_name
                existing.website_url = seed_url
                existing.source_url = seed_url
                skipped += 1
                continue
            
            # Create new AMC
            amc = AMC(
                id=uuid.uuid4(),
                name=amc_name,
                normalized_name=normalized,
                website_url=seed_url,
                source_url=seed_url,
            )
            session.add(amc)
            loaded += 1
        
        session.commit()
        print(f"Loaded {loaded} new AMCs, updated {skipped} existing")
        return loaded
        
    except Exception as e:
        session.rollback()
        print(f"Error: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Load AMCs from config into database")
    parser.add_argument("--database-url", required=True, help="PostgreSQL connection URL")
    args = parser.parse_args()
    
    load_amcs(args.database_url)