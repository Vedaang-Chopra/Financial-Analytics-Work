"""Fix: drop junk rows (Raw PDF / blank rows) and re-save all 10 stocks."""

from __future__ import annotations

import sys
import time

import pandas as pd
from sqlalchemy import create_engine, text

sys.path.insert(0, ".")
from screener_ingestion import db, fetch, parse  # noqa: E402

DB = "postgresql://vlmrouter:vlmrouter@localhost:5432/screener"
engine = create_engine(DB)

JUNK = {"raw pdf", "raw page", "raw consolidated pdf", "raw standalone pdf",
        "raw financial data excel", "financial data excel", ""}

SLUGS = ["HAL", "ITC", "TCS", "RELIANCE", "HDFCBANK", "INFY", "SBIN", "LT", "SUNPHARMA", "TMCV"]

# how much junk is currently stored?
n_junk_before = pd.read_sql(text("""
    SELECT COUNT(*) FROM financial_line_items li
    JOIN financial_periods fp ON fp.id = li.period_id
    WHERE LOWER(li.line_item) LIKE 'raw %' OR TRIM(li.line_item) = ''
"""), engine).iloc[0, 0]
print(f"junk line-item cells currently in DB: {n_junk_before}")

for slug in SLUGS:
    html = fetch.fetch_company(slug)
    payload = parse.parse_company_page(html)
    payload["slug"] = slug

    # strip junk rows from every statement before saving
    removed = 0
    for section in list((payload.get("financials") or {}).values()) + \
                   list((payload.get("shareholding") or {}).values()):
        before = len(section["rows"])
        kept = []
        for row in section["rows"]:
            if row["label"].strip().lower() in JUNK or row["label"].strip().lower().startswith("raw "):
                removed += 1
                continue
            # drop rows where every value cell is empty
            if all(v is None for v in row["values"]):
                removed += 1
                continue
            kept.append(row)
        section["rows"] = kept
        # keep periods that still have at least one non-null value across kept rows
        ncols = len(section["periods"])
        col_has_value = [False] * ncols
        for row in kept:
            for i, v in enumerate(row["values"]):
                if v is not None and i < ncols:
                    col_has_value[i] = True
        section["periods"] = [p if (p and col_has_value[i]) else None
                              for i, p in enumerate(section["periods"])]

    peers_html_ok = payload.get("warehouse_id")
    peers = []
    if peers_html_ok:
        try:
            from screener_ingestion.cli import fetch_peers_html
            peers = parse.parse_peers_table(fetch_peers_html(payload["warehouse_id"]))
        except Exception as e:
            print(f"  peers skipped for {slug}: {e}")

    run_uuid = db.save_payload(DB, payload, peers=peers,
                               raw_path=str(fetch.latest_cached(slug) or ""))
    print(f"{slug:<12} cleaned & re-saved ({removed} junk cells dropped) run={run_uuid[:8]}")
    time.sleep(2)

# delete the already-stored junk cells
with engine.begin() as conn:
    res = conn.execute(text("""
        DELETE FROM financial_line_items li
        USING financial_periods fp
        WHERE li.period_id = fp.id
          AND (LOWER(li.line_item) LIKE 'raw %' OR TRIM(li.line_item) = '')
    """))
    print(f"\ndeleted {res.rowcount} junk cells from DB")

# also delete now-empty trailing periods (e.g. FY2027 placeholders)
with engine.begin() as conn:
    res2 = conn.execute(text("""
        DELETE FROM financial_periods fp
        WHERE NOT EXISTS (
            SELECT 1 FROM financial_line_items li WHERE li.period_id = fp.id AND li.value IS NOT NULL
        ) AND fp.is_date = true
          AND fp.period_key > TO_CHAR(NOW(), 'YYYY-MM-DD')
    """))
    print(f"deleted {res2.rowcount} future placeholder periods")

print("\nDone. Re-run scripts/verify_db_vs_live.py to re-audit.")
