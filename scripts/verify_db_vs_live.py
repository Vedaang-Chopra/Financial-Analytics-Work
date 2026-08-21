"""Accuracy audit: compare DB-stored values against a fresh live fetch.

For each stock: re-fetch the screener page, re-parse it, and compare
top ratios + every financial line item against what's in Postgres.
Saturday run => market closed => values should match exactly.
"""

from __future__ import annotations

import sys

import pandas as pd
from sqlalchemy import create_engine, text

sys.path.insert(0, ".")
from screener_ingestion import fetch, parse  # noqa: E402

DB = "postgresql://vlmrouter:vlmrouter@localhost:5432/screener"
engine = create_engine(DB)

SLUGS = ["HAL", "ITC", "TCS", "RELIANCE", "HDFCBANK", "INFY", "SBIN", "LT", "SUNPHARMA", "TMCV"]

total_checked, total_match, total_diff, total_missing = 0, 0, 0, 0
report_rows = []

for slug in SLUGS:
    live = parse.parse_company_page(fetch.fetch_company(slug))
    live_tr = live["top_ratios"]

    db_snap = pd.read_sql(
        text("""
            SELECT DISTINCT ON (stock_id) *
            FROM stock_snapshots ss JOIN stocks s ON s.id = ss.stock_id
            WHERE s.slug=:s ORDER BY stock_id, fetched_at DESC
        """), engine, params={"s": slug}).iloc[0]

    # --- top ratios comparison ---
    for field in ["market_cap_cr", "current_price", "stock_pe", "book_value",
                  "dividend_yield", "roce_pct", "roe_pct", "face_value",
                  "high_52w", "low_52w"]:
        live_v = live_tr.get(field)
        db_v = db_snap[field]
        total_checked += 1
        if live_v is None and pd.isna(db_v):
            total_match += 1
        elif live_v is not None and not pd.isna(db_v) and abs(float(live_v) - float(db_v)) < 1e-6:
            total_match += 1
        else:
            total_diff += 1
            report_rows.append((slug, f"snapshot.{field}", db_v, live_v))

    # --- line items comparison (all statements) ---
    db_items = pd.read_sql(
        text("""
            SELECT fp.statement_type, fp.period_key, li.line_item, li.value
            FROM financial_line_items li
            JOIN financial_periods fp ON fp.id = li.period_id
            JOIN stocks s ON s.id = fp.stock_id
            WHERE s.slug=:s
        """), engine, params={"s": slug})
    db_lookup = {
        (r.statement_type, str(r.period_key), r.line_item): r.value
        for r in db_items.itertuples()
    }

    all_statements = {**(live.get("financials") or {}), **(live.get("shareholding") or {})}
    for stype, parsed in all_statements.items():
        periods = parsed.get("periods") or []
        for row in parsed.get("rows") or []:
            for col, period in enumerate(periods):
                if not period:
                    continue
                live_v = row["values"][col] if col < len(row["values"]) else None
                db_v = db_lookup.get((stype, str(period), row["label"]))
                if db_v is None and live_v is None:
                    continue
                total_checked += 1
                if live_v is None or pd.isna(db_v):
                    total_missing += 1
                    report_rows.append((slug, f"{stype}/{period}/{row['label']}", db_v, live_v))
                elif abs(float(live_v) - float(db_v)) < 1e-6:
                    total_match += 1
                else:
                    total_diff += 1
                    report_rows.append((slug, f"{stype}/{period}/{row['label']}", db_v, live_v))
    print(f"{slug:<12} checked so far: {total_checked}")

print("\n" + "=" * 70)
print(f"VALUES CHECKED : {total_checked}")
print(f"MATCH          : {total_match} ({100 * total_match / max(total_checked,1):.2f}%)")
print(f"MISMATCH       : {total_diff}")
print(f"MISSING IN DB  : {total_missing}")
print("=" * 70)

if report_rows:
    print("\nDifferences (db_value vs live_value):")
    for r in report_rows[:40]:
        print(f"  {r[0]:<10} {r[1]:<55} db={r[2]} live={r[3]}")
else:
    print("\nEvery stored value matches the live site exactly.")
