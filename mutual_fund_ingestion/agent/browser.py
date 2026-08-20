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
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise BrowserUnavailable("Playwright is not installed") from exc

    import asyncio

    async def _extract():
        debug_dir.mkdir(parents=True, exist_ok=True)
        network_calls: list[dict[str, Any]] = []
        downloads: list[dict[str, Any]] = []

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=headless)
            page = await browser.new_page()

            page.on("response", lambda response: network_calls.append({
                "url": response.url,
                "status": response.status,
                "content_type": response.headers.get("content-type"),
            }))

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=int(timeout_seconds * 1000))
                await page.wait_for_timeout(1500)
                html = await page.content()

                # Extract links
                links = []
                for elem in await page.locator("a").all():
                    try:
                        href = await elem.get_attribute("href")
                        text = await elem.inner_text()
                        if href:
                            links.append({"url": canonical_url(href), "text": text.strip(), "title": ""})
                    except Exception:
                        pass

                # Screenshot
                screenshot_path = debug_dir / "screenshot.png"
                try:
                    await page.screenshot(path=str(screenshot_path), full_page=True, timeout=10_000)
                    screenshot_path_str = str(screenshot_path)
                except Exception:
                    screenshot_path_str = None

                # Network downloads
                for call in network_calls:
                    ft = file_type_from_url(call["url"])
                    if ft:
                        downloads.append({"url": call["url"], "content_type": call.get("content_type"), "file_type": ft})

                await browser.close()
                return BrowserResult(
                    html=html,
                    screenshot_path=screenshot_path_str,
                    links=links,
                    downloads=downloads,
                    network_calls=network_calls,
                )
            finally:
                await browser.close()

    return asyncio.run(_extract())