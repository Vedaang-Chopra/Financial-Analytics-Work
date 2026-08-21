from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

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


def _resolve_relative_url(base_url: str, href: str) -> str:
    """Resolve relative URLs to absolute using the base URL."""
    if not href:
        return ""
    parsed_href = urlparse(href)
    if parsed_href.scheme and parsed_href.netloc:
        return href  # Already absolute
    # Resolve relative to base
    return urljoin(base_url, href)


def _extract_file_urls_from_json(data: Any, base_url: str) -> list[str]:
    """Recursively extract file URLs from JSON data."""
    file_urls = []
    
    if isinstance(data, dict):
        for key, value in data.items():
            if key in ('url', 'fileUrl', 'downloadUrl', 'link', 'href', 'file_url', 'download_url'):
                if isinstance(value, str) and value:
                    absolute_url = _resolve_relative_url(base_url, value)
                    file_urls.append(absolute_url)
            elif key == 'files' and isinstance(value, list):
                # ICICI API specific: files array with url field
                for item in value:
                    if isinstance(item, dict):
                        file_url = item.get('url') or item.get('fileUrl') or item.get('downloadUrl')
                        if file_url and isinstance(file_url, str):
                            absolute_url = _resolve_relative_url(base_url, file_url)
                            file_urls.append(absolute_url)
            elif isinstance(value, (dict, list)):
                file_urls.extend(_extract_file_urls_from_json(value, base_url))
    elif isinstance(data, list):
        for item in data:
            file_urls.extend(_extract_file_urls_from_json(item, base_url))
    
    return file_urls


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
        api_file_urls: list[str] = []

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=headless)
            page = await browser.new_page()

            page.on("response", lambda response: network_calls.append({
                "url": response.url,
                "status": response.status,
                "content_type": response.headers.get("content-type"),
            }))

            # Also capture JSON response bodies for API calls
            json_responses: dict[str, Any] = {}
            
            async def handle_response(response):
                content_type = response.headers.get("content-type", "") or ""
                if "application/json" in content_type and response.url.startswith("http"):
                    try:
                        body = await response.json()
                        json_responses[response.url] = body
                    except Exception:
                        pass

            page.on("response", handle_response)

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=int(timeout_seconds * 1000))
                await page.wait_for_timeout(1500)
                html = await page.content()

                # Extract links from HTML
                links = []
                for elem in await page.locator("a").all():
                    try:
                        href = await elem.get_attribute("href")
                        text = await elem.inner_text()
                        if href:
                            # Resolve relative URLs to absolute
                            absolute_url = _resolve_relative_url(url, href)
                            links.append({"url": canonical_url(absolute_url), "text": text.strip(), "title": ""})
                    except Exception:
                        pass

                # Screenshot
                screenshot_path = debug_dir / "screenshot.png"
                try:
                    await page.screenshot(path=str(screenshot_path), full_page=True, timeout=10_000)
                    screenshot_path_str = str(screenshot_path)
                except Exception:
                    screenshot_path_str = None

                # Network downloads - resolve relative URLs
                for call in network_calls:
                    ft = file_type_from_url(call["url"])
                    if ft:
                        absolute_download_url = _resolve_relative_url(url, call["url"])
                        downloads.append({"url": absolute_download_url, "content_type": call.get("content_type"), "file_type": ft})

                # Extract file URLs from captured JSON API responses
                for api_url, data in json_responses.items():
                    urls = _extract_file_urls_from_json(data, url)
                    for u in urls:
                        ft = file_type_from_url(u)
                        if ft:
                            downloads.append({"url": u, "content_type": "application/json", "file_type": ft})
                            api_file_urls.append(u)

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