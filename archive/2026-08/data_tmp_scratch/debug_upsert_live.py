"""Reproduce the exact failing upsert against live Postgres with echo on the
holdings dedupe step. Uses a transaction that we roll back at the end."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from db_config import mutual_funds_url

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import requests
from sqlalchemy import select

from mutual_fund_ingestion.agent.db import (
    IngestionRun, PortfolioHolding, get_session_maker,
)
from mutual_fund_ingestion.agent.parser import parse_file
from mutual_fund_ingestion.agent.upserts import UpsertManager
from mutual_fund_ingestion.agent.validate import validate_and_filter_records

DB = mutual_funds_url()
session = get_session_maker(DB)()

url = "https://www.icicipruamc.com/blob/downloads/Files/Fortnightly%20Portfolio%20Disclosures/2026/Fortnightly%20Debt%20Scheme%20Portfolio%20-%2015th%20August%202026.zip"
run = IngestionRun(status="running", config_json={"tool": "debug"})
session.add(run)
session.flush()

from mutual_fund_ingestion.agent.db import RawArtifact

art = RawArtifact(run_id=run.id, source_url=url, artifact_type="file",
                  file_type="zip", content_type="application/zip",
                  size_bytes=0, checksum=None)
session.add(art)
session.commit()

resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=120)
result = parse_file("portfolio_disclosure", "zip", resp.content,
                    {"source_url": url, "amc_name": "ICICI Prudential Mutual Fund", "file_ext": ".zip"})
valid, quarantined, _ = validate_and_filter_records(result, str(run.id), return_warnings=True)

mgr = UpsertManager()
mgr.set_run_id(str(run.id))
try:
    mgr.upsert_canonical(
        session, valid, "portfolio_disclosure",
        raw_artifact_id=art.id,
        source_url=url, stats={}, checksum="deadbeef",
        amc_name="ICICI Prudential Mutual Fund",
    )
    session.rollback()
    print("UPSERT OK (rolled back)")
except Exception as e:
    session.rollback()
    print("UPSERT FAILED:", type(e).__name__, str(e)[:300])
finally:
    session.close()
