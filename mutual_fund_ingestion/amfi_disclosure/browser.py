from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

from .models import DisclosureLink


LOGGER = logging.getLogger(__name__)


class BrowserUnavailable(RuntimeError):
    pass


def discover_with_browser(source_url: str, debug_dir: Path) -> tuple[list[DisclosureLink], list[str]]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise BrowserUnavailable(
            "Install the optional browser dependency with 'pip install playwright' and "
            "'playwright install chromium'."
        ) from exc

    from .discovery import extract_page_links, file_type_from_url

    debug_dir.mkdir(parents=True, exist_ok=True)
    network_files: list[DisclosureLink] = []
    timestamp = datetime.now(timezone.utc).isoformat()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()

        def record_response(response) -> None:
            file_type = file_type_from_url(response.url)
            if not file_type:
                return
            network_files.append(
                DisclosureLink(
                    source_page_url=source_url,
                    file_url=response.url,
                    file_name=Path(response.url.split("?", 1)[0]).name,
                    file_type=file_type,
                    disclosure_type="Portfolio Disclosure",
                    discovered_at=timestamp,
                    discovery_method="network_request",
                    raw_metadata={"status": response.status},
                )
            )

        page.on("response", record_response)
        try:
            LOGGER.info("Opening AMFI page with Playwright: %s", source_url)
            page.goto(source_url, wait_until="domcontentloaded", timeout=45_000)
            page.wait_for_timeout(1_500)
            html_snapshots = [page.content()]

            for index in range(page.locator("select").count()):
                selector = page.locator("select").nth(index)
                for option in selector.locator("option").all():
                    value = option.get_attribute("value")
                    if not value:
                        continue
                    try:
                        selector.select_option(value=value)
                        page.wait_for_timeout(1_000)
                        html_snapshots.append(page.content())
                    except Exception as exc:
                        LOGGER.debug("Could not select disclosure option %s: %s", value, exc)

            for label in ("Monthly Portfolio Disclosure", "Portfolio Disclosure"):
                locator = page.get_by_text(label, exact=True)
                if locator.count() == 1:
                    try:
                        locator.click()
                        page.wait_for_timeout(1_000)
                        html_snapshots.append(page.content())
                    except Exception as exc:
                        LOGGER.debug("Could not click disclosure control %s: %s", label, exc)

            files = list(network_files)
            landing_pages: list[str] = []
            for html in html_snapshots:
                found_files, found_pages = extract_page_links(
                    html,
                    source_url,
                    "playwright",
                    default_disclosure_type="Portfolio Disclosure",
                )
                files.extend(found_files)
                landing_pages.extend(found_pages)
            browser.close()
            return files, list(dict.fromkeys(urljoin(source_url, url) for url in landing_pages))
        except Exception:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            try:
                (debug_dir / f"failure-{stamp}.html").write_text(page.content(), encoding="utf-8")
            except Exception as exc:
                LOGGER.warning("Could not save browser HTML failure artifact: %s", exc)
            try:
                page.screenshot(
                    path=str(debug_dir / f"failure-{stamp}.png"),
                    full_page=True,
                    timeout=5_000,
                )
            except Exception as exc:
                LOGGER.warning("Could not save browser screenshot failure artifact: %s", exc)
            browser.close()
            raise
