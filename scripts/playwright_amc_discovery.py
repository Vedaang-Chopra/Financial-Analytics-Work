"""
Generic Playwright-based portfolio disclosure discovery + ingestion.

Deterministic strategy order per AGENTS.md:
  1. static_html   - direct HTTP GET of seed_url, harvest file links from raw HTML
  2. playwright    - JS render of seed_url, expand common tabs/accordions,
                     harvest file links from the DOM

Modes:
  discover : probe every enabled source in configs/amc_sources.yaml, write a
             machine-readable artifact to data/raw/mutual_funds/discovered_links/
  ingest   : read the latest discovery artifact, download -> parse ->
             validate_and_filter_records -> quarantine_rows -> upsert_canonical
             (same gated path as scripts/targeted_portfolio_ingestion.py)

Politeness: strictly sequential, >=1s sleep between requests, real UA,
explicit timeouts. No CAPTCHA/auth bypass, public disclosures only.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.url_utils import file_type_from_url

LOGGER = logging.getLogger("playwright_discovery")

REPO_ROOT = Path(__file__).parent.parent
CONFIG_PATH = REPO_ROOT / "configs" / "amc_sources.yaml"
DISCOVERY_DIR = REPO_ROOT / "data" / "raw" / "mutual_funds" / "discovered_links"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 45
POLITE_SLEEP = 1.5

FILE_EXTS = (".xlsx", ".xls", ".zip", ".csv")
PORTFOLIO_HINTS = ("portfolio", "fortnightly", "monthly", "holding")
# Month-year pattern in anchor text ("July 2026 - All Funds") marks dated
# disclosure files even when the word "portfolio" is absent.
MONTH_YEAR_RE = re.compile(
    r"\b(jan(uary)?|feb(ruary)?|mar(ch)?|apr(il)?|may|jun(e)?|jul(y)?|"
    r"aug(ust)?|sep(t(ember)?)?|oct(ober)?|nov(ember)?|dec(ember)?)\s*,?\s*20\d{2}\b",
    re.I,
)
MONTH_FULL = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# Tab / accordion labels worth expanding once before harvesting.
EXPAND_TEXTS = [
    "portfolio", "disclosure", "download", "monthly",
    "statutory", "mandatory", "reports",
]

# AMCs already served by dedicated navigators / targeted ingestion
# (scripts/targeted_portfolio_ingestion.py). Skipped by default.
COVERED_AMCS = {
    "PPFAS Mutual Fund",
    "Mirae Asset Mutual Fund",
    "DSP Mutual Fund",
    "Invesco Mutual Fund",
    "ICICI Prudential Mutual Fund",
    "Aditya Birla Sun Life Mutual Fund",
    "LIC Mutual Fund",
    "Axis Mutual Fund",
    "SBI Mutual Fund",
    "HDFC Mutual Fund",
    "Nippon India Mutual Fund",
    "UTI Mutual Fund",
    "Franklin Templeton Mutual Fund",
}


# --------------------------------------------------------------------------
# Static (strategy step 1)
# --------------------------------------------------------------------------

def harvest_links_static(session: requests.Session, url: str) -> list[dict]:
    """Fetch raw HTML and pull out file links without any JS rendering."""
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except Exception as exc:
        LOGGER.warning("static fetch failed %s: %s", url, exc)
        return []
    return _extract_links_from_html(resp.text, url)


def _extract_links_from_html(html: str, base_url: str) -> list[dict]:
    import re
    from urllib.parse import urljoin

    found: dict[str, dict] = {}
    for match in re.finditer(r'href=["\']([^"\']+)["\']', html, re.I):
        href = match.group(1)
        lower = href.lower()
        if not lower.endswith(FILE_EXTS):
            continue
        absolute = urljoin(base_url, href)
        if not absolute.startswith(("http://", "https://")):
            continue
        if absolute in found:
            continue
        found[absolute] = {"url": absolute, "context": None}
    # Second pass: capture anchor context text for portfolio relevance scoring
    for match in re.finditer(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.I | re.S
    ):
        href, text = match.group(1), re.sub(r"<[^>]+>", " ", match.group(2))
        from urllib.parse import urljoin
        absolute = urljoin(base_url, href.strip())
        if absolute in found and text.strip():
            found[absolute]["context"] = " ".join(text.split())[:200]
    return list(found.values())


# --------------------------------------------------------------------------
# Playwright (strategy step 3)
# --------------------------------------------------------------------------

def harvest_links_playwright(seed_url: str, screenshot_dir: Path | None = None,
                             safe_name: str = "amc") -> tuple[list[dict], list[str]]:
    """Render the page headless, expand likely tabs, harvest file links.

    Returns (links, notes).
    """
    from urllib.parse import urljoin

    notes: list[str] = []
    links: dict[str, dict] = {}

    def harvest(page) -> int:
        new = 0
        for link in page.locator("a").all():
            try:
                href = link.get_attribute("href", timeout=2000)
            except Exception:
                continue
            if not href:
                continue
            lower = href.lower().split("?")[0]
            if not lower.endswith(FILE_EXTS):
                continue
            absolute = urljoin(page.url, href)
            if absolute in links:
                continue
            try:
                text = " ".join((link.inner_text(timeout=1000) or "").split())[:200]
            except Exception:
                text = ""
            links[absolute] = {"url": absolute, "context": text}
            new += 1
        return new

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            ctx = browser.new_context(user_agent=USER_AGENT, viewport={"width": 1366, "height": 900})
            page = ctx.new_page()
            try:
                page.goto(seed_url, wait_until="domcontentloaded", timeout=45000)
            except Exception as exc:
                notes.append(f"goto failed: {str(exc).splitlines()[0]}")
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                notes.append("networkidle timeout (continuing)")
            page.wait_for_timeout(2500)

            n0 = harvest(page)

            # Expand likely tab/accordion triggers once each, re-harvest after.
            for text in EXPAND_TEXTS:
                try:
                    trigger = page.locator(
                        f"[role='tab']:has-text('{text}'), "
                        f"a:has-text('{text}'), "
                        f"button:has-text('{text}'), "
                        f"h2:has-text('{text}'), h3:has-text('{text}'), "
                        f"div[class*='accordion']:has-text('{text}')"
                    ).first
                    if trigger.count() == 0:
                        continue
                    trigger.scroll_into_view_if_needed(timeout=3000)
                    trigger.click(timeout=4000)
                    page.wait_for_timeout(1200)
                    n0 += harvest(page)
                except Exception:
                    continue

            notes.append(f"harvested {n0} unique file links after render+expand")
            if screenshot_dir is not None and n0 == 0:
                screenshot_dir.mkdir(parents=True, exist_ok=True)
                try:
                    path = screenshot_dir / f"{safe_name}_nolinks.png"
                    page.screenshot(path=str(path), full_page=False)
                    notes.append(f"screenshot saved: {path.name}")
                except Exception:
                    pass
        finally:
            browser.close()

    return list(links.values()), notes


# --------------------------------------------------------------------------
# Discovery orchestration
# --------------------------------------------------------------------------

def classify_relevance(links: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split into portfolio-relevant and other file links.

    Relevant = keyword hint OR a month-year label in the anchor text
    (monthly disclosure archives are usually labeled "July 2026 ...").
    """
    relevant, other = [], []
    for link in links:
        context = link.get("context") or ""
        hay = (context + " " + link["url"]).lower()
        if any(h in hay for h in PORTFOLIO_HINTS) or MONTH_YEAR_RE.search(context):
            relevant.append(link)
        else:
            other.append(link)
    return relevant, other


def month_year_from_context(context: str | None) -> str | None:
    """'June 2026 - All Funds' -> '2026-06-01' (ISO), else None."""
    if not context:
        return None
    match = MONTH_YEAR_RE.search(context)
    if not match:
        return None
    token = match.group(0).lower().replace(",", " ").split()
    month = next(v for k, v in MONTH_FULL.items() if token[0].startswith(k))
    year = int(token[-1])
    return f"{year:04d}-{month:02d}-01"


def discover(sources: list[dict], include_covered: bool = False,
             debug_dir: Path | None = None) -> list[dict]:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    results: list[dict] = []

    for i, src in enumerate(sources):
        amc = src["amc_name"]
        seed = src["seed_url"]
        entry: dict = {
            "amc_name": amc,
            "seed_url": seed,
            "strategy": None,
            "portfolio_links": [],
            "other_links": [],
            "notes": [],
        }
        if not include_covered and amc in COVERED_AMCS:
            entry["strategy"] = "skipped_covered"
            entry["notes"].append("already served by targeted_portfolio_ingestion navigator")
            results.append(entry)
            continue

        LOGGER.info("[%d/%d] %s :: %s", i + 1, len(sources), amc, seed)

        def _finalize(links: list[dict], strategy: str) -> None:
            rel, oth = classify_relevance(links)
            for link in rel:
                link["reporting_date_hint"] = month_year_from_context(link.get("context"))
            entry["strategy"] = strategy
            entry["portfolio_links"], entry["other_links"] = rel, oth

        # Step 1: static_html
        links = harvest_links_static(session, seed)
        time.sleep(POLITE_SLEEP)
        if links:
            rel, _ = classify_relevance(links)
            if rel:
                _finalize(links, "static_html")
                entry["notes"].append(f"static: {len(rel)} portfolio links")
                results.append(entry)
                continue

        # Step 3: playwright (skip step 2 network_api here - site-specific)
        pw_links, notes = harvest_links_playwright(
            seed, screenshot_dir=debug_dir, safe_name=_slug(amc)
        )
        entry["notes"].extend(notes)
        _finalize(pw_links, "")
        if entry["portfolio_links"]:
            entry["strategy"] = "playwright"
        elif pw_links:
            entry["strategy"] = "playwright_files_no_portfolio_hint"
        else:
            entry["strategy"] = "no_files_found"
            entry["notes"].append("manual_review candidate")
        results.append(entry)

        # Persist incrementally so progress survives interruption
        DISCOVERY_DIR.mkdir(parents=True, exist_ok=True)
        incremental = DISCOVERY_DIR / f"discovery_partial_{_slug(amc)}.json"
        incremental.write_text(json.dumps(entry, indent=2))

    return results


def _slug(name: str) -> str:
    import re as _re
    return _re.sub(r"[^a-z0-9]+", "_", name.casefold()).strip("_") or "unknown"


def load_sources() -> list[dict]:
    import yaml
    data = yaml.safe_load(CONFIG_PATH.read_text())
    # Some registry entries are metadata-only (no seed_url) - keep actionable ones.
    return [s for s in data["sources"]
            if s.get("enabled", True) and s.get("seed_url") and s.get("amc_name")]


# --------------------------------------------------------------------------
# Ingestion mode (reuses the gated path from targeted_portfolio_ingestion)
# --------------------------------------------------------------------------

def ingest_from_artifact(artifact_path: Path, database_url: str, max_files_per_amc: int,
                         only_amcs: "set[str] | None" = None) -> dict:
    from mutual_fund_ingestion.agent.db import get_session_maker
    from mutual_fund_ingestion.agent.upserts import UpsertManager
    from targeted_portfolio_ingestion import download_and_parse

    payload = json.loads(artifact_path.read_text())
    entries = payload["results"]

    session_maker = get_session_maker(database_url)
    upsert_manager = UpsertManager()

    run_id = str(uuid.uuid4())
    session = session_maker()
    try:
        from mutual_fund_ingestion.agent.db import IngestionRun
        run = IngestionRun(
            id=uuid.UUID(run_id),
            started_at=datetime.now(timezone.utc),
            status="running",
            config_json={
                "mode": "playwright_discovery_ingest",
                "artifact": str(artifact_path),
                "max_files_per_amc": max_files_per_amc,
            },
        )
        session.add(run)
        session.commit()
    finally:
        session.close()

    totals: dict = {
        "files_downloaded": 0, "artifacts_parsed": 0, "rows_staged": 0,
        "rows_inserted": 0, "rows_quarantined": 0, "errors": 0,
    }
    per_amc: dict[str, dict] = {}

    for entry in entries:
        amc = entry["amc_name"]
        if only_amcs and amc not in only_amcs:
            continue
        urls = [l["url"] for l in entry.get("portfolio_links", [])]
        if not urls:
            continue
        # Sort by parsed month descending (newest first) then cap per-AMC.
        links_sorted = sorted(
            entry.get("portfolio_links", []),
            key=lambda l: l.get("reporting_date_hint") or "", reverse=True,
        )
        links_sorted = links_sorted[:max_files_per_amc]
        LOGGER.info("Ingesting %d files for %s", len(links_sorted), amc)
        stats: dict = {}
        for link in links_sorted:
            fallback_date = link.get("reporting_date_hint")
            download_and_parse(
                link["url"], amc, run_id, session_maker, upsert_manager, stats,
                extra_metadata={"fallback_reporting_date": fallback_date} if fallback_date else None,
            )
            time.sleep(POLITE_SLEEP)
        per_amc[amc] = stats
        for k in totals:
            totals[k] = totals.get(k, 0) + stats.get(k, 0)

    # finalize run record
    session = session_maker()
    try:
        from mutual_fund_ingestion.agent.db import IngestionRun
        run = session.query(IngestionRun).filter(IngestionRun.id == uuid.UUID(run_id)).first()
        if run:
            run.finished_at = datetime.now(timezone.utc)
            run.status = "completed"
            run.files_seen = totals["files_downloaded"]
            run.rows_inserted = totals["rows_inserted"]
            run.rows_rejected = totals["rows_quarantined"]
            run.error_summary = {"errors": totals["errors"]}
            session.commit()
    finally:
        session.close()

    return {"run_id": run_id, "totals": totals, "per_amc": per_amc}


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", help="PostgreSQL URL (required for ingest)")
    parser.add_argument("--mode", choices=["discover", "ingest"], default="discover")
    parser.add_argument("--include-covered", action="store_true",
                        help="also probe AMCs with dedicated navigators")
    parser.add_argument("--only", nargs="*", help="limit to these AMC names")
    parser.add_argument("--max-files-per-amc", type=int, default=12)
    parser.add_argument("--artifact", help="discovery artifact to ingest (default: latest)")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.mode == "discover":
        sources = load_sources()
        if args.only:
            wanted = set(args.only)
            sources = [s for s in sources if s["amc_name"] in wanted]
        results = discover(
            sources, include_covered=args.include_covered,
            debug_dir=REPO_ROOT / "data" / "debug" / "mutual_funds" / "playwright_discovery",
        )
        DISCOVERY_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out = DISCOVERY_DIR / f"playwright_discovery_{ts}.json"
        summary = {
            "generated_at": ts,
            "sources_probed": len(results),
            "by_strategy": {},
            "results": results,
        }
        for r in results:
            summary["by_strategy"][r["strategy"]] = summary["by_strategy"].get(r["strategy"], 0) + 1
        out.write_text(json.dumps(summary, indent=2))
        print(json.dumps({
            "artifact": str(out),
            "sources_probed": summary["sources_probed"],
            "by_strategy": summary["by_strategy"],
            "total_portfolio_links": sum(len(r["portfolio_links"]) for r in results),
        }, indent=2))
        return

    # ingest
    if not args.database_url:
        parser.error("--database-url required for --mode ingest")
    artifact = Path(args.artifact) if args.artifact else _latest_artifact()
    LOGGER.info("Ingesting from artifact %s", artifact)
    outcome = ingest_from_artifact(
        artifact, args.database_url, args.max_files_per_amc,
        only_amcs=set(args.only) if args.only else None,
    )
    print(json.dumps(outcome, indent=2))


def _latest_artifact() -> Path:
    artifacts = sorted(DISCOVERY_DIR.glob("playwright_discovery_*.json"))
    if not artifacts:
        raise SystemExit("No discovery artifacts found - run --mode discover first")
    return artifacts[-1]


if __name__ == "__main__":
    main()
