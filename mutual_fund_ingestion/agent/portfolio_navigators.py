"""
AMC-specific portfolio URL extractors.

Each AMC has a different UI:
- PPFAS, DSP, Mirae, Invesco, Aditya Birla: static HTML with download links
- ICICI: React app with Financial Year dropdown (see icici_navigator.py)
- LIC: Server-rendered page with POST AJAX for filter options
- Axis: Ionic dropdowns

Each function returns a list[str] of full URLs to portfolio files (xlsx/zip).
"""

from __future__ import annotations

import logging
import re
from typing import Any

import requests

LOGGER = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def _get_with_headers(url: str, timeout: int = 30) -> requests.Response:
    return requests.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
    )


def get_ppfas_portfolio_urls() -> list[str]:
    """PPFAS - portfolio disclosure subpages (files are NOT on the main downloads page)."""
    from bs4 import BeautifulSoup

    seed_pages = [
        "https://amc.ppfas.com/downloads/portfolio-disclosure/",
        "https://amc.ppfas.com/downloads/portfolio-disclosure/fortnightly-debt-portfolio-disclosure/",
    ]
    urls: list[str] = []
    for page_url in seed_pages:
        try:
            resp = _get_with_headers(page_url)
            resp.raise_for_status()
        except Exception:
            continue
        soup = BeautifulSoup(resp.text, "html.parser")
        for link in soup.find_all("a", href=True):
            href = link["href"]
            text = link.get_text(strip=True).lower()
            if href.lower().split("?")[0].endswith((".xlsx", ".xls", ".zip")):
                if not href.startswith("http"):
                    href = f"https://amc.ppfas.com{href}"
                urls.append(href)
    return list(set(urls))


def get_mirae_portfolio_urls() -> list[str]:
    """Mirae Asset - has Monthly/Fortnightly tabs loaded by JS.

    Static HTML works because tabs render on first load via Playwright.
    """
    import asyncio
    from playwright.async_api import async_playwright

    async def _extract() -> list[str]:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.set_viewport_size({"width": 1280, "height": 720})

                all_urls: set[str] = set()
                for tab_text in ("Monthly Portfolio", "Fortnightly Portfolio"):
                    try:
                        await page.goto(
                            "https://www.miraeassetmf.co.in/downloads/portfolio",
                            wait_until="domcontentloaded",
                            timeout=30000,
                        )
                        await page.wait_for_timeout(2500)
                        await page.click(
                            f'a:has-text("{tab_text}")', timeout=5000
                        )
                        await page.wait_for_timeout(2000)
                        links = await page.locator("a").all()
                        for link in links:
                            try:
                                href = await link.get_attribute("href")
                                text = await link.inner_text()
                                if (
                                    href
                                    and text
                                    and ".xlsx" in href.lower()
                                    and "portfolio" in text.lower()
                                ):
                                    if not href.startswith("http"):
                                        href = (
                                            f"https://www.miraeassetmf.co.in{href}"
                                        )
                                    all_urls.add(href)
                            except Exception:
                                continue
                    except Exception as exc:
                        LOGGER.warning("Mirae tab %s failed: %s", tab_text, exc)
                return list(all_urls)
            finally:
                await browser.close()

    return asyncio.run(_extract())


def get_dsp_portfolio_urls() -> list[str]:
    """DSP - static HTML with simple <a> links."""
    from bs4 import BeautifulSoup

    resp = _get_with_headers(
        "https://www.dspim.com/mandatory-disclosures/portfolio-disclosures"
    )
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    urls: list[str] = []
    for link in soup.find_all("a", href=True):
        href = link["href"]
        text = link.get_text(strip=True).lower()
        if (
            href.lower().endswith((".xlsx", ".zip"))
            and (
                "fortnightly" in text
                or "portfolio" in text
                or "monthly" in text
                or "debt" in text
            )
        ):
            if not href.startswith("http"):
                href = f"https://www.dspim.com{href}"
            urls.append(href)
    return list(set(urls))


def get_invesco_portfolio_urls() -> list[str]:
    """Invesco - tab is selected via URL parameter so static-ish."""
    import asyncio
    from playwright.async_api import async_playwright

    async def _extract() -> list[str]:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.set_viewport_size({"width": 1280, "height": 720})

                await page.goto(
                    "https://www.invescomutualfund.com/literature-and-form?tab=Fortnightly",
                    wait_until="domcontentloaded",
                    timeout=30000,
                )
                await page.wait_for_timeout(3000)

                all_urls: set[str] = set()
                links = await page.locator("a").all()
                for link in links:
                    try:
                        href = await link.get_attribute("href")
                        if href and ".xlsx" in href.lower() and "fortnightly" in href.lower():
                            if not href.startswith("http"):
                                href = (
                                    f"https://www.invescomutualfund.com{href}"
                                )
                            all_urls.add(href)
                    except Exception:
                        continue
                return list(all_urls)
            finally:
                await browser.close()

    return asyncio.run(_extract())


def get_aditya_birla_portfolio_urls() -> list[str]:
    """Aditya Birla Sun Life - portfolio links embedded under /-/media/.

    Page loads with JS; uses Playwright to ensure links render before extraction.
    """
    import asyncio
    from playwright.async_api import async_playwright

    async def _extract() -> list[str]:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.set_viewport_size({"width": 1280, "height": 720})

                await page.goto(
                    "https://mutualfund.adityabirlacapital.com/portfolio",
                    wait_until="domcontentloaded",
                    timeout=30000,
                )
                await page.wait_for_timeout(3000)

                all_urls: set[str] = set()
                links = await page.locator("a.afDowloadCss").all()
                for link in links:
                    try:
                        href = await link.get_attribute("href")
                        if href and (
                            ".xlsx" in href.lower() or ".zip" in href.lower()
                        ):
                            if not href.startswith("http"):
                                href = (
                                    f"https://mutualfund.adityabirlacapital.com{href}"
                                )
                            all_urls.add(href)
                    except Exception:
                        continue
                return list(all_urls)
            finally:
                await browser.close()

    return asyncio.run(_extract())


def get_lic_portfolio_urls() -> list[str]:
    """LIC - Monthly/Fortnightly tabs with cascading dropdowns.

    Workflow:
    1. Load https://www.licmf.com/downloads/monthly-portfolio
    2. For Monthly tab (default):
       - Select category (Debt, Equity, Hybrid, ETFs & Index Funds, Solution Oriented Funds)
       - Select scheme from fund_name dropdown
       - Select year from year dropdown
       - Select month from month dropdown
       - Click Submit button
       - Collect download links
    3. For Fortnightly tab:
       - Click Fortnightly tab (href="#fortnightly-tab-content")
       - Select category from fortnightly_fund_category
       - Select scheme from fortnightly_fund_name
       - Select year from fortnightly_year
       - Select month from fortnightly_month
       - Click Submit button inside fortnightly tab
       - Collect download links
    """
    import asyncio
    from playwright.async_api import async_playwright

    # JavaScript function templates for extracting dropdown options
    JS_GET_OPTIONS = """
    () => {
        const select = document.querySelector('%s');
        if (!select) return [];
        return Array.from(select.options)
            .map(o => ({value: o.value, text: o.text.trim()}))
            .filter(o => o.value);
    }
    """

    async def _extract() -> list[str]:
        all_urls: set[str] = set()

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.set_viewport_size({"width": 1280, "height": 720})

                await page.goto(
                    "https://www.licmf.com/downloads/monthly-portfolio",
                    wait_until="domcontentloaded",
                    timeout=30000,
                )
                await page.wait_for_timeout(3000)

                # Process both Monthly and Fortnightly tabs
                for tab_name in ("Monthly", "Fortnightly"):
                    if tab_name == "Fortnightly":
                        # Click Fortnightly tab
                        try:
                            await page.click(
                                'a[href="#fortnightly-tab-content"]',
                                force=True,
                                timeout=5000,
                            )
                            await page.wait_for_timeout(3000)
                        except Exception as exc:
                            LOGGER.warning("LIC fortnightly tab click failed: %s", exc)
                            continue
                    
                    # Selectors for current tab
                    if tab_name == "Monthly":
                        cat_selector = "select.fund_category"
                        scheme_selector = "select.fund_name"
                        year_selector = "select.year"
                        month_selector = "select.month"
                        submit_in_tab = ""  # submit button is global
                    else:
                        cat_selector = "select.fortnightly_fund_category"
                        scheme_selector = "select.fortnightly_fund_name"
                        year_selector = "select.fortnightly_year"
                        month_selector = "select.fortnightly_month"
                        submit_in_tab = "#fortnightly-tab-content "
                    
                    # Categories to iterate - limit to Debt for speed
                    categories = ["Debt"]
                    
                    for category in categories:
                        try:
                            await page.select_option(cat_selector, value=category, timeout=5000)
                            await page.wait_for_timeout(2000)
                        except Exception as exc:
                            LOGGER.warning("LIC %s category %s select failed: %s", tab_name, category, exc)
                            continue

                        # Get scheme options
                        try:
                            scheme_options = await page.evaluate(JS_GET_OPTIONS % scheme_selector)
                        except Exception as exc:
                            LOGGER.warning("LIC %s scheme options failed: %s", tab_name, exc)
                            continue

                        for scheme in scheme_options[:5]:  # cap per category
                            try:
                                await page.select_option(scheme_selector, value=scheme["value"], timeout=5000)
                                await page.wait_for_timeout(2000)
                            except Exception as exc:
                                LOGGER.warning("LIC %s scheme %s select failed: %s", tab_name, scheme["value"], exc)
                                continue

                            # Get year options
                            try:
                                year_options = await page.evaluate(JS_GET_OPTIONS % year_selector)
                            except Exception as exc:
                                LOGGER.warning("LIC %s year options failed: %s", tab_name, exc)
                                continue

                            # Process recent years first (2026, 2025)
                            for year in year_options[1:3]:  # skip "Year" placeholder, take up to 2 recent
                                try:
                                    await page.select_option(year_selector, value=year["value"], timeout=5000)
                                    await page.wait_for_timeout(2000)
                                except Exception as exc:
                                    LOGGER.warning("LIC %s year %s select failed: %s", tab_name, year["value"], exc)
                                    continue

                                # Get month options
                                try:
                                    month_options = await page.evaluate(JS_GET_OPTIONS % month_selector)
                                except Exception as exc:
                                    LOGGER.warning("LIC %s month options failed: %s", tab_name, exc)
                                    continue

                                # Process months (try recent ones)
                                for month in month_options[1:3]:  # skip "Month" placeholder
                                    try:
                                        await page.select_option(month_selector, value=month["value"], timeout=5000)
                                        await page.wait_for_timeout(2000)
                                    except Exception as exc:
                                        LOGGER.warning("LIC %s month %s select failed: %s", tab_name, month["value"], exc)
                                        continue

                                    # Click Submit button
                                    try:
                                        await page.click(f'{submit_in_tab}button:has-text("Submit"), {submit_in_tab}button:has-text("SUBMIT")', force=True, timeout=5000)
                                        await page.wait_for_timeout(3000)
                                    except Exception as exc:
                                        LOGGER.warning("LIC %s submit click failed: %s", tab_name, exc)
                                        continue

                                    # Get download links
                                    try:
                                        links = await page.locator('a[href*=".xlsx"], a[href*=".zip"]').all()
                                        for link in links:
                                            try:
                                                href = await link.get_attribute("href")
                                                if not href:
                                                    continue
                                                href_l = href.lower()
                                                # Only portfolio + monthly/fortnightly URLs
                                                if (
                                                    "portfolio" in href_l
                                                    or (tab_name == "Fortnightly" and "fortnight" in href_l)
                                                ):
                                                    if not href.startswith("http"):
                                                        href = f"https://www.licmf.com{href}"
                                                    all_urls.add(href)
                                            except Exception:
                                                continue
                                    except Exception as exc:
                                        LOGGER.warning("LIC %s download links failed: %s", tab_name, exc)
                                        continue

            finally:
                await browser.close()

        return list(all_urls)

    return asyncio.run(_extract())


def get_axis_portfolio_urls() -> list[str]:
    """Axis - network_api strategy (no browser needed).

    transact.axismf.com exposes a JSON API:
      /cms/api/statutory-disclosures?cat=<category>
    Categories of interest:
      - "Monthly Scheme Portfolios"
      - "Fortnightly Portfolio Disclosure for Debt Schemes"
    Each entry has field_related_file (path under /cms/sites/default/files/...).
    """
    categories = [
        "Fortnightly Portfolio Disclosure for Debt Schemes",
        "Monthly Scheme Portfolios",
    ]
    api_url = "https://transact.axismf.com/cms/api/statutory-disclosures"
    base = "https://transact.axismf.com"

    all_urls: list[str] = []
    seen: set[str] = set()

    for category in categories:
        try:
            resp = _get_with_headers(api_url, timeout=30)
            # requests.get params would be cleaner but keep simple explicit URL
            import urllib.parse

            resp = _get_with_headers(
                f"{api_url}?cat={urllib.parse.quote(category)}", timeout=30
            )
            resp.raise_for_status()
            entries = resp.json()
        except Exception as exc:
            LOGGER.warning("Axis API call failed for %s: %s", category, exc)
            continue

        for entry in entries:
            path = entry.get("field_related_file") or ""
            name = entry.get("field_pdf_name_statutory") or ""
            if not path:
                continue
            path_l = path.lower()
            if not any(path_l.endswith(ext) for ext in (".xlsx", ".xls", ".zip")):
                continue
            if "portfolio" not in path_l and "portfolio" not in name.lower():
                continue
            url = path if path.startswith("http") else f"{base}{path}"
            if url not in seen:
                seen.add(url)
                all_urls.append(url)

    return all_urls


# Registry of all navigators - add new AMCs here.
AMC_NAVIGATORS: dict[str, Any] = {
    "ppfas": get_ppfas_portfolio_urls,
    "mirae_asset": get_mirae_portfolio_urls,
    "dsp": get_dsp_portfolio_urls,
    "invesco": get_invesco_portfolio_urls,
    "icici_prudential": None,  # uses icici_navigator.py
    "aditya_birla": get_aditya_birla_portfolio_urls,
    "lic": get_lic_portfolio_urls,
    "axis": get_axis_portfolio_urls,
}
