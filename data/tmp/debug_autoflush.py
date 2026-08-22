"""Minimal repro: does the seen_holdings dedupe query see un-flushed inserts?"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import select, create_engine
from sqlalchemy.orm import sessionmaker

from mutual_fund_ingestion.agent.db import PortfolioHolding, Base

engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(engine)
s = sessionmaker(bind=engine)()

h1 = PortfolioHolding(snapshot_id="11111111-1111-1111-1111-111111111111",
                      instrument_id=None, security_name="SWAP X", isin=None,
                      metadata_json={})
s.add(h1)
# NO flush — same state as upsert_portfolio mid-loop
rows = s.execute(
    select(PortfolioHolding.security_name, PortfolioHolding.isin)
    .where(PortfolioHolding.snapshot_id == "11111111-1111-1111-1111-111111111111")
).all()
print("query result before flush:", rows)
print("pending new objects:", s.new)
s.close()
