"""Browser-based extraction using Playwright."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from utils.url_utils import canonical_url, file_type_from_url


LOGGER = logging.getLogger(__name__)


class BrowserUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class BrowserResult:
    html: str
    screenshot_path: str | None
    links: list[dict[str, str]]
    downloads: list[dict[str, Any]]
    network_calls: list[dict[str, Any]]


def extract_with_browser(
    url: str,
    debug_dir: Path,
    timeout_seconds: float = 30.0,
    headless: bool = True,
) -> BrowserResult:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise BrowserUnavailable("Playwright is not installed") from exc

    debug_dir.mkdir(parents=True, exist_ok=True)
    network_calls: list[dict[str, Any]] = []
    downloads: list[dict[str, Any]] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        page = browser.new_page()

        page.on("response", lambda response: network_calls.append({
            "url": response.url,
            "status": response.status,
            "content_type": response.headers.get("content-type"),
        }))

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=int(timeout_seconds * 1000))
            page.wait_for_timeout(1500)
            html = page.content()

            # Extract links
            links = []
            for elem in page.locator("a").all():
                try:
                    href = elem.get_attribute("href")
                    text = elem.inner_text().strip()
                    if href:
                        links.append({"url": canonical_url(href), "text": text, "title": ""})
                except Exception:
                    pass

            # Screenshot
            screenshot_path = debug_dir / "screenshot.png"
            try:
                page.screenshot(path=str(screenshot_path), full_page=True, timeout=10_000)
                screenshot_path_str = str(screenshot_path)
            except Exception:
                screenshot_path_str = None

            # Network downloads
            for call in network_calls:
                ft = file_type_from_url(call["url"])
                if ft:
                    downloads.append({"url": call["url"], "content_type": call.get("content_type"), "file_type": ft})

            browser.close()
            return BrowserResult(
                html=html,
                screenshot_path=screenshot_path_str,
                links=links,
                downloads=downloads,
                network_calls=network_calls,
            )
        finally:
            browser.close()
