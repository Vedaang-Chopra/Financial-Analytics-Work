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
from datetime import datetime
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
    """Mirae Asset - Monthly/Fortnightly/Half-Year tabs, each with bootpag paging.

    Walks EVERY pagination page of each tab (li.page-item.next until disabled)
    so the full historical archive is enumerated, not just page 1.
    """
    import asyncio
    from playwright.async_api import async_playwright

    TABS = {
        "Monthly Portfolio": "#portfolio_tab1",
        "Fortnightly Portfolio": "#portfolio_tab3",
        "Half Year Portfolio": "#portfolio_tab2",
    }

    async def _extract() -> list[str]:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.set_viewport_size({"width": 1280, "height": 720})

                all_urls: set[str] = set()
                for tab_text, tab_sel in TABS.items():
                    try:
                        await page.goto(
                            "https://www.miraeassetmf.co.in/downloads/portfolio",
                            wait_until="domcontentloaded",
                            timeout=30000,
                        )
                        await page.wait_for_timeout(2500)
                        await page.click(tab_sel, timeout=5000)
                        await page.wait_for_timeout(2000)

                        seen_pages = 0
                        while seen_pages < 60:  # hard safety cap
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
                            seen_pages += 1

                            next_li_class = await page.evaluate(
                                """() => { const n = document.querySelector(
                                     'ul.bootpag li.page-item.next');
                                     return n ? n.className : 'done'; }"""
                            )
                            if "disabled" in (next_li_class or "") or "done" == next_li_class:
                                break
                            try:
                                await page.click(
                                    "ul.bootpag li.page-item.next a", timeout=5000
                                )
                                await page.wait_for_timeout(1500)
                            except Exception:
                                break
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
    """Invesco - network_api strategy via /api/WeeklyHoldings JSON endpoints.

    Flow: ?year=YYYY -> list of months that have disclosures;
          ?month=M&year=YYYY&classification=fixed-income -> DailyHoldings
          entries carrying DocumentUrl per scheme per fortnight.
    Enumerates ALL years back to 2016 so the full fortnightly archive is covered.
    """
    api = "https://www.invescomutualfund.com/api/WeeklyHoldings"
    months = {
        "January": 1, "February": 2, "March": 3, "April": 4, "May": 5,
        "June": 6, "July": 7, "August": 8, "September": 9, "October": 10,
        "November": 11, "December": 12,
    }

    all_urls: set[str] = set()
    current_year = datetime.now().year
    for year in range(2016, current_year + 1):
        try:
            resp = _get_with_headers(f"{api}?year={year}", timeout=30)
            resp.raise_for_status()
            month_entries = resp.json()
        except Exception as exc:
            LOGGER.warning("Invesco year %s listing failed: %s", year, exc)
            continue

        for entry in month_entries:
            month_name = (entry or {}).get("mths")
            if month_name not in months:
                continue
            try:
                mresp = _get_with_headers(
                    f"{api}?month={months[month_name]}&year={year}"
                    f"&classification=fixed-income",
                    timeout=30,
                )
                mresp.raise_for_status()
                days = mresp.json()
            except Exception as exc:
                LOGGER.warning(
                    "Invesco %s-%s files failed: %s", year, month_name, exc
                )
                continue
            for day in days:
                for holding in (day or {}).get("DailyHoldingsdata") or []:
                    url = (holding or {}).get("DocumentUrl") or ""
                    if ".xlsx" in url.lower() or ".zip" in url.lower():
                        all_urls.add(url)
    return list(all_urls)


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
    """LIC - network_api strategy via the consolidated-portfolio AJAX endpoints.

    Flow (plain HTTP with a ci_session cookie from the listing page):
      POST /downloads/consolidated-portfolio-filters {id, filter:'year'}   -> years
      POST /downloads/consolidated-portfolio-filters {year, id, filter:'month'} -> months
      POST /downloads/consolidated-portfolio-files   {id, month, year}     -> HTML links
    Portfolio types: 639 = Monthly Portfolio, 638 = Fortnightly Portfolio.
    Enumerates EVERY type x year x month combination back to 2013.
    """
    base = "https://www.licmf.com"
    list_url = f"{base}/downloads/consolidated-portfolio-filters"
    files_url = f"{base}/downloads/consolidated-portfolio-files"
    headers = {
        "User-Agent": USER_AGENT,
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"{base}/downloads/consolidated-portfolio",
    }

    session = requests.Session()
    try:
        session.get(
            f"{base}/downloads/consolidated-portfolio",
            headers={"User-Agent": USER_AGENT},
            timeout=30,
        )
    except Exception as exc:
        LOGGER.warning("LIC bootstrap page failed: %s", exc)

    all_urls: set[str] = set()
    for type_id in ("639", "638"):  # Monthly, Fortnightly
        try:
            resp = session.post(
                list_url, headers=headers,
                data={"id": type_id, "filter": "year"}, timeout=30,
            )
            resp.raise_for_status()
        except Exception as exc:
            LOGGER.warning("LIC years for type %s failed: %s", type_id, exc)
            continue
        years = re.findall(r"value='?(\d{4})'?", resp.text)

        for year in years:
            try:
                mresp = session.post(
                    list_url, headers=headers,
                    data={"year": year, "id": type_id, "filter": "month"},
                    timeout=30,
                )
                mresp.raise_for_status()
            except Exception as exc:
                LOGGER.warning("LIC months %s/%s failed: %s", type_id, year, exc)
                continue
            months = re.findall(r"value='?([^'>]+)'?", mresp.text)
            months = [m for m in months if m.strip()]

            for month in months:
                try:
                    fresp = session.post(
                        files_url, headers=headers,
                        data={"id": type_id, "month": month, "year": year},
                        timeout=30,
                    )
                    fresp.raise_for_status()
                except Exception as exc:
                    LOGGER.warning(
                        "LIC files %s/%s/%s failed: %s", type_id, year, month, exc
                    )
                    continue
                for href in re.findall(r"href=['\"]([^'\"]+)['\"]", fresp.text):
                    if href.lower().split("?")[0].endswith((".xlsx", ".xls", ".zip")):
                        if not href.startswith("http"):
                            href = f"{base}{href}"
                        all_urls.add(href)

    return list(all_urls)


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


def get_sbi_portfolio_urls() -> list[str]:
    """SBI Mutual Fund - network_api strategy.

    www.sbimf.com/portfolios loads its table via a JSON-body POST to
    /ajaxcall/CMS/GetSchemePortfolioSheets (no token required). The response
    is an HTML fragment whose anchors point at .xlsx files under
    https://www.sbimf.com/docs/default-source/scheme-portfolios/.
    Frequencies: Monthly, Half Yearly.
    """
    api_url = "https://www.sbimf.com/ajaxcall/CMS/GetSchemePortfolioSheets"
    headers = {
        "User-Agent": USER_AGENT,
        "Content-Type": "application/json; charset=utf-8",
        "Referer": "https://www.sbimf.com/portfolios",
    }

    all_urls: list[str] = []
    seen: set[str] = set()
    from bs4 import BeautifulSoup

    for frequency in ("Monthly", "Half Yearly"):
        try:
            resp = requests.post(
                api_url,
                headers=headers,
                data='{"FundId":"","PSYear":"","PSMonth":"","PSFrequency":"%s"}' % frequency,
                timeout=60,
            )
            resp.raise_for_status()
        except Exception as exc:
            LOGGER.warning("SBI API call failed for %s: %s", frequency, exc)
            continue
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.lower().split("?")[0].endswith((".xlsx", ".xls", ".zip")):
                if href not in seen:
                    seen.add(href)
                    all_urls.append(href)
        import time

        time.sleep(1)  # polite crawl
    return all_urls


def get_hdfc_portfolio_urls() -> list[str]:
    """HDFC Mutual Fund - static_html strategy.

    Server-rendered Drupal pages link monthly portfolio workbooks directly on
    files.hdfcfund.com/s3fs-public/. The fortnightly page renders via JS, so
    only the monthly page reliably yields static links.
    """
    from bs4 import BeautifulSoup

    seed_pages = [
        "https://www.hdfcfund.com/statutory-disclosure/portfolio/monthly-portfolio",
        "https://www.hdfcfund.com/statutory-disclosure/portfolio/fortnightly-portfolio",
    ]
    urls: list[str] = []
    seen: set[str] = set()
    for page_url in seed_pages:
        try:
            resp = _get_with_headers(page_url)
            resp.raise_for_status()
        except Exception as exc:
            LOGGER.warning("HDFC page fetch failed %s: %s", page_url, exc)
            continue
        # File links are embedded in Drupal-rendered JSON (not <a> tags), so
        # extract s3fs-public workbook URLs straight from the raw HTML.
        for match in re.findall(
            r'https?://files\.hdfcfund\.com/s3fs-public/[^"\'\s\\]+?\.(?:xlsx|xls|zip)',
            resp.text,
            re.I,
        ):
            hl = match.lower()
            # keep portfolio workbooks only (exclude notices/booklets)
            name = match.rsplit("/", 1)[-1]
            if "portfolio" not in hl and not re.search(r"(monthly|fortnightly)", name, re.I):
                continue
            if match not in seen:
                seen.add(match)
                urls.append(match)
        import time

        time.sleep(1)
    return urls


def get_nippon_india_portfolio_urls() -> list[str]:
    """Nippon India Mutual Fund - static_html strategy.

    mf.nipponindiaim.com downloads page lists NIMF-MONTHLY-PORTFOLIO-*.xls and
    NIMF-FORTNIGHTLY-PORTFOLIO-*.xls files directly in the HTML.
    """
    from bs4 import BeautifulSoup

    page_url = (
        "https://mf.nipponindiaim.com/investor-service/downloads/"
        "factsheet-portfolio-and-other-disclosures"
    )
    resp = _get_with_headers(page_url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    base = "https://mf.nipponindiaim.com"
    urls: list[str] = []
    seen: set[str] = set()
    for link in soup.find_all("a", href=True):
        href = link["href"]
        hl = href.lower().split("?")[0]
        if "nimf-monthly-portfolio" not in hl and "nimf-fortnightly-portfolio" not in hl:
            continue
        if not hl.endswith((".xlsx", ".xls", ".zip")):
            continue
        if not href.startswith("http"):
            href = f"{base}{href}"
        if href not in seen:
            seen.add(href)
            urls.append(href)
    return urls


def get_uti_portfolio_urls() -> list[str]:
    """UTI Mutual Fund - network_api strategy.

    The Angular site pulls consolidated portfolio zips from its Drupal CMS API:
      /api/get-consolidate-portfolio-disclosure?year=<Y>&month=<MonthName>
      /api/get-consolidate-debt-portfolio-disclosure?year=<Y>&month=<MonthName>
    Each row carries an absolute URL (cloudfront-hosted zip).
    """
    from datetime import date

    def _recent_months(n: int) -> list[tuple[int, str]]:
        out: list[tuple[int, str]] = []
        today = date.today()
        y, m = today.year, today.month
        for _ in range(n):
            m -= 1
            if m == 0:
                m = 12
                y -= 1
            out.append((y, ["January", "February", "March", "April", "May", "June",
                            "July", "August", "September", "October", "November",
                            "December"][m - 1]))
        return out

    endpoints = [
        "https://www.utimf.com/api/get-consolidate-portfolio-disclosure",
        "https://www.utimf.com/api/get-consolidate-debt-portfolio-disclosure",
    ]
    all_urls: list[str] = []
    seen: set[str] = set()
    for year, month in _recent_months(6):
        for ep in endpoints:
            try:
                resp = _get_with_headers(f"{ep}?year={year}&month={month}")
                resp.raise_for_status()
                rows = resp.json().get("rows", [])
            except Exception as exc:
                LOGGER.warning("UTI API failed %s %s-%s: %s", ep, year, month, exc)
                continue
            for row in rows:
                url = row.get("url") or row.get("doc") or ""
                if url and url.lower().split("?")[0].endswith((".xlsx", ".xls", ".zip")):
                    if url not in seen:
                        seen.add(url)
                        all_urls.append(url)
            import time

            time.sleep(1)
    return all_urls


def get_franklin_templeton_portfolio_urls() -> list[str]:
    """Franklin Templeton India - network_api strategy.

    franklintempletonindia.com/reports is an Angular SPA backed by the
    literature JSON API:
      /api/literature/v1/responseLitJson?type=report
    Categories MONTHLY-PORTFOLIO-DSCLR and FORTNIGHT-PORTFOLIO-DEBT-SCHEMES
    carry consolidated portfolio workbooks as relative literatureHref paths
    (/en-in/<category>/<uuid>/<File>.xlsx).

    Note: the SSD_*.xls links on portal.amfiindia.com referenced by the same
    page are Scheme Summary Documents (SID data), NOT holdings.
    """
    api_url = (
        "https://www.franklintempletonindia.com/api/literature/v1/responseLitJson"
        "?type=report"
    )
    try:
        resp = _get_with_headers(api_url)
        resp.raise_for_status()
        categories = resp.json().get("FirstDropDown", [])
    except Exception as exc:
        LOGGER.warning("Franklin literature API fetch failed: %s", exc)
        return []
    wanted = {"monthly-portfolio-dsclr", "fortnight-portfolio-debt-schemes"}
    urls: list[str] = []
    seen: set[str] = set()
    for category in categories:
        cid = str(category.get("id", "")).lower()
        if cid not in wanted:
            continue
        linkdata = category.get("dataRecords", {}).get("linkdata", [])
        for entry in linkdata:
            href = entry.get("literatureHref") or ""
            if not href.lower().endswith((".xlsx", ".xls", ".zip")):
                continue
            url = (
                "https://www.franklintempletonindia.com/download" + href
                if href.startswith("/")
                else href
            )
            if url not in seen:
                seen.add(url)
                urls.append(url)
    return urls


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
    "sbi": get_sbi_portfolio_urls,
    "hdfc": get_hdfc_portfolio_urls,
    "nippon_india": get_nippon_india_portfolio_urls,
    "uti": get_uti_portfolio_urls,
    "franklin_templeton": get_franklin_templeton_portfolio_urls,
}
