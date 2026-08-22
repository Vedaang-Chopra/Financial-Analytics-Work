"""CLI for screener.in ingestion.

Usage:
  python -m screener_ingestion.cli init-db --database-url postgresql://...
  python -m screener_ingestion.cli ingest --stock HAL --consolidated
  python -m screener_ingestion.cli ingest-batch --stocks HAL,ITC,TCS
  python -m screener_ingestion.cli inspect --stock HAL
"""

from __future__ import annotations

import argparse
import logging
import sys
import time

from sqlalchemy import text

from . import db, fetch, parse

try:
    from db_config import screener_url
except ImportError:  # imported from outside the repo root (installed package)
    def screener_url() -> str:
        import os

        return os.environ.get("SCREENER_DATABASE_URL", "")


def cmd_init_db(args) -> int:
    db.init_db(args.database_url)
    print(f"Schema initialized in {args.database_url.split('@')[-1]}")
    return 0


def ingest_one(slug: str, database_url: str, consolidated: bool = True,
               with_peers: bool = True, with_chart: bool = True,
               chart_days: int = 3652, with_daily: bool = True) -> dict:
    """Fetch → parse → save one stock. Returns run summary."""
    html = fetch.fetch_company(slug, consolidated=consolidated)
    payload = parse.parse_company_page(html)
    payload["slug"] = slug

    peers = []
    if with_peers:
        warehouse_id = payload.get("warehouse_id")
        if warehouse_id:
            try:
                peers_html = fetch_peers_html(warehouse_id)
                peers = parse.parse_peers_table(peers_html)
            except Exception as exc:  # peers must never fail the run
                logging.getLogger(__name__).warning("Peers fetch failed for %s: %s", slug, exc)

    price_history = []
    if with_chart and payload.get("company_id"):
        try:
            chart_json = fetch.fetch_chart(payload["company_id"], days=chart_days)
            price_history = parse.parse_chart_data(chart_json)
        except Exception as exc:  # chart must never fail the run
            logging.getLogger(__name__).warning("Chart fetch failed for %s: %s", slug, exc)

    daily_history = []
    if with_daily:
        try:
            from . import yahoo
            ysym = yahoo.yahoo_symbol(slug, payload.get("nse_code"))
            rows, ymeta = yahoo.parse_daily(yahoo.fetch_daily(ysym))
            daily_history = rows
            logging.getLogger(__name__).info("Yahoo daily for %s (%s): %d rows %s..%s",
                                             slug, ysym, ymeta["count"],
                                             ymeta["first_date"], ymeta["last_date"])
        except Exception as exc:  # daily backfill must never fail the run
            logging.getLogger(__name__).warning("Yahoo daily failed for %s: %s", slug, exc)

    raw_path = str(fetch.latest_cached(slug) or "")
    run_uuid = db.save_payload(database_url, payload, peers=peers, raw_path=raw_path,
                               price_history=price_history + daily_history)
    all_statements = {**(payload.get("financials") or {}), **(payload.get("shareholding") or {})}
    line_items = sum(_count_items(x) for x in all_statements.values())
    return {
        "slug": slug,
        "run_uuid": run_uuid,
        "name": payload.get("name"),
        "line_items": line_items,
        "peers": len(peers),
        "price_points": len(price_history),
        "daily_points": len(daily_history),
        "documents": len(payload.get("documents") or []),
        "top_ratios": payload.get("top_ratios") or {},
    }


def _count_items(parsed: dict) -> int:
    return sum(len(row["values"]) for row in parsed.get("rows", []))


def fetch_peers_html(warehouse_id: str) -> str:
    import requests

    url = f"{fetch.BASE_URL}/api/company/{warehouse_id}/peers/"
    resp = requests.get(url, headers={"User-Agent": fetch.USER_AGENT,
                                      "X-Requested-With": "XMLHttpRequest"},
                        timeout=fetch.DEFAULT_TIMEOUT_S)
    resp.raise_for_status()
    return resp.text


def cmd_ingest(args) -> int:
    summary = ingest_one(args.stock.upper(), args.database_url,
                         consolidated=not args.standalone, with_peers=not args.no_peers,
                         with_chart=not getattr(args, "no_chart", False))
    tr = summary["top_ratios"]
    print(f"[OK] {summary['slug']} ({summary['name']})")
    print(f"     run={summary['run_uuid']} line_items={summary['line_items']} "
          f"peers={summary['peers']} documents={summary['documents']}")
    print(f"     M-Cap={tr.get('market_cap_cr')} P/E={tr.get('stock_pe')} "
          f"ROCE={tr.get('roce_pct')}% ROE={tr.get('roe_pct')}%")
    return 0


def cmd_ingest_batch(args) -> int:
    slugs = [s.strip().upper() for s in args.stocks.split(",") if s.strip()]
    ok, failed = [], []
    for i, slug in enumerate(slugs):
        try:
            t0 = time.time()
            summary = ingest_one(slug, args.database_url,
                                 consolidated=not args.standalone,
                                 with_peers=not args.no_peers,
                                 with_chart=not args.no_chart)
            print(f"[{i + 1}/{len(slugs)}] OK   {slug:<14} "
                  f"items={summary['line_items']:<5} peers={summary['peers']:<3} "
                  f"({time.time() - t0:.1f}s)")
            ok.append(slug)
        except Exception as exc:
            print(f"[{i + 1}/{len(slugs)}] FAIL {slug:<14} {exc}")
            logging.getLogger(__name__).exception("Ingestion failed for %s", slug)
            try:
                db.record_failure(args.database_url, slug,
                                  "consolidated" if not args.standalone else "standalone",
                                  str(exc))
            except Exception:
                pass
            failed.append(slug)
        time.sleep(args.delay)
    print(f"\nDone: {len(ok)} ingested, {len(failed)} failed"
          + (f" — failed: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


def cmd_inspect(args) -> int:
    engine = db.get_engine(args.database_url)
    with engine.connect() as conn:
        stock = conn.execute(
            text("SELECT id, name, bse_code, nse_code, sector FROM stocks WHERE slug=:s"),
            {"s": args.stock.upper()},
        ).first()
        if not stock:
            print(f"Stock {args.stock} not found.")
            return 1
        print(f"{args.stock.upper()} — {stock[1]} (BSE:{stock[2]}, NSE:{stock[3]}) sector={stock[4]}")
        snap = conn.execute(
            text("SELECT * FROM stock_snapshots WHERE stock_id=:i ORDER BY fetched_at DESC LIMIT 1"),
            {"i": stock[0]},
        ).first()
        if snap:
            keys = ("market_cap_cr", "current_price", "stock_pe", "book_value",
                    "dividend_yield", "roce_pct", "roe_pct")
            row = conn.execute(
                text("SELECT market_cap_cr, current_price, stock_pe, book_value,"
                     " dividend_yield, roce_pct, roe_pct FROM stock_snapshots"
                     " WHERE stock_id=:i ORDER BY fetched_at DESC LIMIT 1"),
                {"i": stock[0]},
            ).first()
            for k, v in zip(keys, row):
                print(f"  {k:<16} {v}")
        counts = conn.execute(
            text("SELECT statement_type, COUNT(DISTINCT period_key), COUNT(*) "
                 "FROM financial_periods fp JOIN financial_line_items li ON li.period_id=fp.id "
                 "WHERE fp.stock_id=:i GROUP BY statement_type ORDER BY statement_type"),
            {"i": stock[0]},
        ).all()
        print("  statements:")
        for stype, n_periods, n_items in counts:
            print(f"    {stype:<24} {n_periods:>3} periods, {n_items:>5} line items")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="screener_ingestion", description=__doc__)
    p.add_argument("--database-url",
                   default=screener_url())
    sub = p.add_subparsers(dest="command", required=True)

    init_p = sub.add_parser("init-db", help="Create all tables")
    init_p.set_defaults(func=cmd_init_db)

    ing = sub.add_parser("ingest", help="Ingest one stock")
    ing.add_argument("--stock", required=True)
    ing.add_argument("--standalone", action="store_true",
                     help="Fetch standalone instead of consolidated")
    ing.add_argument("--no-peers", action="store_true")
    ing.add_argument("--no-chart", action="store_true",
                     help="Skip price-history chart data")
    ing.set_defaults(func=cmd_ingest)

    batch = sub.add_parser("ingest-batch", help="Ingest multiple stocks (comma-separated)")
    batch.add_argument("--stocks", required=True)
    batch.add_argument("--delay", type=float, default=2.0,
                       help="Seconds between stocks (politeness)")
    batch.add_argument("--standalone", action="store_true")
    batch.add_argument("--no-peers", action="store_true")
    batch.add_argument("--no-chart", action="store_true")
    batch.set_defaults(func=cmd_ingest_batch)

    ins = sub.add_parser("inspect", help="Show stored data for a stock")
    ins.add_argument("--stock", required=True)
    ins.set_defaults(func=cmd_inspect)
    return p


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = build_parser()
    args, unknown = parser.parse_known_args(argv)
    if "--database-url" in unknown or any(u.startswith("--database-url") for u in unknown):
        # allow --database-url after the subcommand
        idx = unknown.index("--database-url") if "--database-url" in unknown else 0
        if isinstance(unknown[idx], str) and unknown[idx].startswith("--database-url="):
            args.database_url = unknown[idx].split("=", 1)[1]
        else:
            args.database_url = unknown[idx + 1]
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
