"""Polite HTTP fetching of screener.in company pages.

Raw HTML is cached under data/raw/screener/<slug>/ so parsing can be
re-run offline and the original artifact is never modified.
"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime
from pathlib import Path

import requests

LOGGER = logging.getLogger(__name__)

BASE_URL = "https://www.screener.in"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
DEFAULT_TIMEOUT_S = 20
MAX_RETRIES = 3
BACKOFF_S = 3


class FetchError(RuntimeError):
    """Raised when a page cannot be fetched after retries."""


def company_url(slug: str, consolidated: bool = True) -> str:
    suffix = "/consolidated/" if consolidated else "/"
    return f"{BASE_URL}/company/{slug}{suffix}"


def _get(url: str) -> str:
    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(
                url,
                headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"},
                timeout=DEFAULT_TIMEOUT_S,
            )
            if resp.status_code == 404:
                raise FetchError(f"404 not found: {url}")
            if resp.status_code == 429:
                wait = BACKOFF_S * attempt * 2
                LOGGER.warning("Rate limited (429) on %s; sleeping %ss", url, wait)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.text
        except (requests.RequestException, FetchError) as exc:
            last_exc = exc
            if isinstance(exc, FetchError) and "404" in str(exc):
                raise
            LOGGER.warning("Fetch attempt %d/%d failed for %s: %s", attempt, MAX_RETRIES, url, exc)
            if attempt < MAX_RETRIES:
                time.sleep(BACKOFF_S * attempt)
    raise FetchError(f"Failed to fetch {url}: {last_exc}")


def save_raw(slug: str, html: str, cache_dir: str | Path = "data/raw/screener") -> Path:
    """Persist raw HTML as an immutable dated artifact."""
    out_dir = Path(cache_dir) / slug.lower()
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    path = out_dir / f"{stamp}.html"
    path.write_text(html, encoding="utf-8")
    return path


def fetch_company(
    slug: str,
    consolidated: bool = True,
    cache_dir: str | Path = "data/raw/screener",
) -> str:
    """Fetch a company page and cache raw HTML. Returns HTML text."""
    url = company_url(slug, consolidated)
    html = _get(url)
    path = save_raw(slug, html, cache_dir)
    LOGGER.info("Fetched %s (%d bytes) -> %s", url, len(html), path)
    return html


def latest_cached(slug: str, cache_dir: str | Path = "data/raw/screener") -> Path | None:
    d = Path(cache_dir) / slug.lower()
    if not d.exists():
        return None
    files = sorted(d.glob("*.html"))
    return files[-1] if files else None


def fetch_chart(company_id: str, days: int = 1825) -> dict:
    """Fetch screener's chart data (Price/DMA50/DMA200/Volume) for a company.

    Same endpoint the website's interactive chart uses:
    /api/company/{company_id}/chart/?days=N&metrics=Price-DMA50-DMA200-Volume
    Returns the raw JSON dict with a 'datasets' list.
    """
    url = f"{BASE_URL}/api/company/{company_id}/chart/?days={days}&metrics=Price-DMA50-DMA200-Volume"
    resp = requests.get(url, headers={"User-Agent": USER_AGENT,
                                      "X-Requested-With": "XMLHttpRequest"},
                        timeout=DEFAULT_TIMEOUT_S)
    resp.raise_for_status()
    return resp.json()
