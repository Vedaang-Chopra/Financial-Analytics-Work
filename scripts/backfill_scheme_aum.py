#!/usr/bin/env python
"""Backfill scheme_aum_history from AMFI's scheme-wise Average AUM API.

Source (verified working 2026-08-22):
    https://www.amfiindia.com/api/average-aum-schemewise
        ?strType=Typewise&fyId=<n>&periodId=<n>&MF_ID=0
  - MF_ID=0 returns ALL AMCs in one request (~2 MB JSON, ~8.5k schemes)
  - data are quarterly periods; month_start = quarter's first day
  - each row carries the AMFI scheme code -> resolved against
    schemes.scheme_code exactly; fallback: normalized AMC name +
    normalized scheme name match

Politeness: strictly sequential requests, >=1.1s sleep between them,
real browser User-Agent, 120s timeouts. A full multi-year backfill is a
handful of requests (one per fiscal year x period), not one per AMC.

Idempotent: INSERT ... ON CONFLICT (scheme_id, month_start)
DO UPDATE SET avg_aum_cr / source_url.

Usage:
    ./financial_env/bin/python scripts/backfill_scheme_aum.py [--years 3]
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time

sys.path.insert(0, ".")

import requests
from sqlalchemy import create_engine, text

from utils.text_utils import normalize_amc_name
from mutual_fund_ingestion.agent.parser.aum_excel import (
    AMFI_SCHEMEWISE_API_URL,
    parse_amfi_schemewise_aum_json,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
LOGGER = logging.getLogger("aum_backfill")

DATABASE_URL = "postgresql://vlmrouter:vlmrouter@localhost:5432/mutual_funds"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "application/json",
}
SLEEP_SECONDS = 1.1


def polite_get(url: str) -> requests.Response:
    LOGGER.info("GET %s", url)
    resp = requests.get(url, headers=HEADERS, timeout=120)
    time.sleep(SLEEP_SECONDS)
    resp.raise_for_status()
    return resp


def list_financial_years() -> list[dict]:
    """fyId discovery: no fyId -> {"type": "financial_years", "data": [...]}."""
    payload = polite_get(f"{AMFI_SCHEMEWISE_API_URL.split('?')[0]}?strType=Typewise").json()
    return payload.get("data") or []


def list_periods(fy_id: int) -> list[dict]:
    url = f"{AMFI_SCHEMEWISE_API_URL.split('?')[0]}?strType=Typewise&fyId={fy_id}&MF_ID=0"
    payload = polite_get(url).json()
    if isinstance(payload.get("data"), dict):
        return payload["data"].get("periods") or []
    return []


def build_scheme_lookup(engine) -> tuple[dict[str, object], dict[tuple[str, str], object]]:
    """(amfi_code -> scheme_id), ((norm_amc, norm_scheme) -> scheme_id)."""
    by_code: dict[str, object] = {}
    by_name: dict[tuple[str, str], object] = {}
    with engine.connect() as conn:
        rows = conn.execute(text(
            """
            SELECT s.id, s.scheme_code, s.normalized_scheme_name, a.normalized_name AS amc_norm
            FROM schemes s LEFT JOIN amcs a ON a.id = s.amc_id
            WHERE s.scheme_code IS NOT NULL OR s.normalized_scheme_name <> ''
            """
        ))
        for scheme_id, code, norm_name, amc_norm in rows:
            if code:
                by_code[str(code)] = scheme_id
            if norm_name and amc_norm:
                by_name.setdefault((amc_norm, norm_name), scheme_id)
    LOGGER.info("scheme lookup: %d codes, %d name pairs", len(by_code), len(by_name))
    return by_code, by_name


def upsert_rows(engine, rows: list[dict]) -> tuple[int, int, int]:
    """Insert idempotently; returns (inserted_or_updated, unresolved, skipped_no_aum)."""
    inserted = unresolved = skipped = 0
    with engine.begin() as conn:
        for rec in rows:
            aum = rec.get("avg_aum_cr")
            if not aum or aum <= 0 or not rec.get("month_start"):
                skipped += 1
                continue
            scheme_id = None
            code = rec.get("amfi_scheme_code")
            if code:
                scheme_id = LOOKUP_BY_CODE.get(str(code))
            if scheme_id is None and rec.get("amc_name") and rec.get("scheme_name"):
                key = (
                    normalize_amc_name(rec["amc_name"]),
                    normalize_amc_name(rec["scheme_name"]),
                )
                scheme_id = LOOKUP_BY_NAME.get(key)
            if scheme_id is None:
                unresolved += 1
                continue
            conn.execute(
                text(
                    """
                    INSERT INTO scheme_aum_history (scheme_id, month_start, avg_aum_cr, source_url)
                    VALUES (:scheme_id, CAST(:month_start AS date), :avg_aum_cr, :source_url)
                    ON CONFLICT (scheme_id, month_start)
                    DO UPDATE SET avg_aum_cr = EXCLUDED.avg_aum_cr,
                                  source_url = EXCLUDED.source_url
                    """
                ),
                {
                    "scheme_id": scheme_id,
                    "month_start": rec["month_start"],
                    "avg_aum_cr": aum,
                    "source_url": rec["source_url"] or AMFI_SCHEMEWISE_API_URL,
                },
            )
            inserted += 1
    return inserted, unresolved, skipped


LOOKUP_BY_CODE: dict = {}
LOOKUP_BY_NAME: dict = {}


def main() -> int:
    global LOOKUP_BY_CODE, LOOKUP_BY_NAME

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", type=int, default=3,
                        help="how many recent financial years to backfill (default 3)")
    args = parser.parse_args()

    engine = create_engine(DATABASE_URL)

    years = list_financial_years()
    if not years:
        LOGGER.error("Could not discover financial years from AMFI API")
        return 1
    chosen = years[: max(args.years, 0)] or years[:3]
    LOGGER.info("backfilling %d financial years: %s", len(chosen),
                [y.get("financial_year") for y in chosen])

    LOOKUP_BY_CODE, LOOKUP_BY_NAME = build_scheme_lookup(engine)

    total_written = total_unresolved = total_skipped = 0
    for fy in chosen:
        fy_id = fy["id"]
        periods = list_periods(fy_id)
        LOGGER.info("FY %s (%s): %d periods", fy_id, fy.get("financial_year"), len(periods))
        for period in periods:
            url = AMFI_SCHEMEWISE_API_URL.format(
                str_type="Typewise", fy_id=fy_id, period_id=period["id"], mf_id=0
            )
            resp = polite_get(url)
            payload = resp.json()
            result = parse_amfi_schemewise_aum_json(
                payload,
                {
                    "source_url": url,
                    "period_label": period.get("period"),
                    "file_ext": ".json",
                },
            )
            if result.errors:
                LOGGER.warning("parse errors for %s: %s", period.get("period"), result.errors[:3])
            written, unresolved, skipped = upsert_rows(engine, result.records)
            total_written += written
            total_unresolved += unresolved
            total_skipped += skipped
            LOGGER.info(
                "  %s: parsed=%d written=%d unresolved=%d skipped=%d",
                period.get("period"), len(result.records), written, unresolved, skipped,
            )

    LOGGER.info(
        "DONE: rows_written=%d unresolved=%d skipped_no_aum=%d",
        total_written, total_unresolved, total_skipped,
    )
    print(json.dumps({
        "rows_written": total_written,
        "unresolved": total_unresolved,
        "skipped_no_aum": total_skipped,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
