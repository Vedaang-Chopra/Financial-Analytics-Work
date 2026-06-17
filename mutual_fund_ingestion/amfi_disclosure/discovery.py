from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import replace
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote, urljoin, urlparse, urlunparse

import requests

from .browser import BrowserUnavailable, discover_with_browser
from .http import HttpSettings, build_session
from .models import DisclosureLink


LOGGER = logging.getLogger(__name__)
AMFI_PORTFOLIO_URL = "https://www.amfiindia.com/online-center/portfolio-disclosure"
FILE_EXTENSIONS = {"pdf", "xls", "xlsx", "csv", "zip"}
RELEVANT_TERMS = ("portfolio", "disclosure", "monthly", "holding")
EMBEDDED_FILE_PATTERN = re.compile(
    r"""["']((?:https?://|/)[^"'<> \t\r\n]+?\.(?:pdf|xls|xlsx|csv|zip)(?:\?[^"'<> \t\r\n]*)?)["']""",
    re.IGNORECASE,
)
DATE_PATTERNS = (
    re.compile(r"\b(20\d{2})[-_/](0[1-9]|1[0-2])[-_/](0[1-9]|[12]\d|3[01])\b"),
    re.compile(r"\b(0[1-9]|[12]\d|3[01])[-_/](0[1-9]|1[0-2])[-_/](20\d{2})\b"),
    re.compile(r"\b(20\d{2})[-_/](0[1-9]|1[0-2])\b"),
)
MONTHS = {
    name.lower(): number
    for number, name in enumerate(
        (
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ),
        1,
    )
}


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[dict[str, str]] = []
        self._stack: list[str] = []
        self._current: dict[str, str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.lower(): value or "" for key, value in attrs}
        context = " ".join(
            part
            for part in (
                attributes.get("id", ""),
                attributes.get("class", ""),
                attributes.get("aria-label", ""),
            )
            if part
        )
        self._stack.append(context)
        if tag.lower() == "a" and attributes.get("href"):
            self._current = {
                "href": attributes["href"].strip(),
                "title": attributes.get("title", "").strip(),
                "text": "",
                "context": " ".join(item for item in self._stack if item),
            }

    def handle_data(self, data: str) -> None:
        if self._current is not None:
            self._current["text"] += data

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._current is not None:
            self._current["text"] = " ".join(self._current["text"].split())
            self.anchors.append(self._current)
            self._current = None
        if self._stack:
            self._stack.pop()


def canonical_url(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path,
            "",
            parsed.query,
            "",
        )
    )


def file_type_from_url(url: str) -> str | None:
    path = unquote(urlparse(url).path)
    suffix = Path(path).suffix.lower().lstrip(".")
    return suffix if suffix in FILE_EXTENSIONS else None


def file_name_from_url(url: str, file_type: str) -> str:
    name = Path(unquote(urlparse(url).path)).name
    return name or f"disclosure.{file_type}"


def extract_month_or_date(text: str) -> str | None:
    normalized = unquote(text)
    match = DATE_PATTERNS[0].search(normalized)
    if match:
        return "-".join(match.groups())
    match = DATE_PATTERNS[1].search(normalized)
    if match:
        day, month, year = match.groups()
        return f"{year}-{month}-{day}"
    match = DATE_PATTERNS[2].search(normalized)
    if match:
        return "-".join(match.groups())
    month_pattern = "|".join(MONTHS)
    match = re.search(rf"\b({month_pattern})\s+(20\d{{2}})\b", normalized, re.IGNORECASE)
    if match:
        return f"{match.group(2)}-{MONTHS[match.group(1).lower()]:02d}"
    match = re.search(rf"\b(20\d{{2}})\s+({month_pattern})\b", normalized, re.IGNORECASE)
    if match:
        return f"{match.group(1)}-{MONTHS[match.group(2).lower()]:02d}"
    return None


def infer_amc_name(title: str, text: str, default: str | None) -> str | None:
    candidate = title or default
    if candidate:
        return candidate.strip()
    match = re.search(r"(.+?(?:Mutual Fund|Asset Management|AMC))", text, re.IGNORECASE)
    return match.group(1).strip() if match else None


def extract_page_links(
    html: str,
    source_page_url: str,
    discovery_method: str,
    default_disclosure_type: str | None = None,
    default_amc_name: str | None = None,
) -> tuple[list[DisclosureLink], list[str]]:
    parser = LinkParser()
    parser.feed(html)
    discovered_at = datetime.now(timezone.utc).isoformat()
    files: list[DisclosureLink] = []
    landing_pages: list[str] = []
    source_host = urlparse(source_page_url).netloc.lower()

    for anchor in parser.anchors:
        href = anchor["href"]
        if href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        url = canonical_url(urljoin(source_page_url, href))
        file_type = file_type_from_url(url)
        combined = " ".join((anchor["text"], anchor["title"], anchor["context"], url)).lower()
        if file_type:
            file_name = file_name_from_url(url, file_type)
            files.append(
                DisclosureLink(
                    source_page_url=source_page_url,
                    file_url=url,
                    file_name=file_name,
                    file_type=file_type,
                    disclosure_type=default_disclosure_type,
                    amc_name=infer_amc_name(anchor["title"], anchor["text"], default_amc_name),
                    month_or_date=extract_month_or_date(f"{anchor['text']} {file_name}"),
                    discovered_at=discovered_at,
                    discovery_method=discovery_method,
                    raw_metadata={
                        "anchor_text": anchor["text"],
                        "anchor_title": anchor["title"],
                        "anchor_context": anchor["context"],
                    },
                )
            )
            continue
        target_host = urlparse(url).netloc.lower()
        relevant = any(term in combined for term in RELEVANT_TERMS)
        in_monthly_section = "divmonthlyportfolio" in combined
        external_from_amfi = "amfiindia.com" in source_host and target_host != source_host
        if relevant or in_monthly_section or (external_from_amfi and "mutual fund" in combined):
            landing_pages.append(url)

    for match in EMBEDDED_FILE_PATTERN.finditer(html):
        url = canonical_url(urljoin(source_page_url, match.group(1)))
        file_type = file_type_from_url(url)
        if not file_type:
            continue
        file_name = file_name_from_url(url, file_type)
        files.append(
            DisclosureLink(
                source_page_url=source_page_url,
                file_url=url,
                file_name=file_name,
                file_type=file_type,
                disclosure_type=default_disclosure_type,
                amc_name=default_amc_name,
                month_or_date=extract_month_or_date(file_name),
                discovered_at=discovered_at,
                discovery_method=discovery_method,
                raw_metadata={"source": "embedded_script"},
            )
        )

    return deduplicate_links(files), list(dict.fromkeys(landing_pages))


def deduplicate_links(links: Iterable[DisclosureLink]) -> list[DisclosureLink]:
    unique: dict[str, DisclosureLink] = {}
    for link in links:
        unique.setdefault(canonical_url(link.file_url), link)
    return sorted(unique.values(), key=lambda item: (item.amc_name or "", item.file_url))


def select_latest_per_amc(links: Iterable[DisclosureLink], limit: int) -> list[DisclosureLink]:
    grouped: dict[str, list[DisclosureLink]] = defaultdict(list)
    for link in links:
        grouped[link.amc_name or "Unknown AMC"].append(link)
    selected: list[DisclosureLink] = []
    for amc_name in sorted(grouped):
        ordered = sorted(
            grouped[amc_name],
            key=lambda link: (link.month_or_date or "", link.file_url),
            reverse=True,
        )
        selected.extend(ordered[:limit])
    return selected


class Discoverer:
    def __init__(
        self,
        *,
        settings: HttpSettings | None = None,
        session: requests.Session | None = None,
        browser_fallback: bool = True,
        debug_dir: Path = Path("data/debug/amfi"),
    ) -> None:
        self.settings = settings or HttpSettings()
        self.session = session or build_session(self.settings)
        self.browser_fallback = browser_fallback
        self.debug_dir = debug_dir

    def fetch_html(self, url: str) -> str:
        LOGGER.info("Loading page: %s", url)
        response = self.session.get(url, timeout=self.settings.timeout_seconds)
        response.raise_for_status()
        return response.text

    def discover(self, source_url: str = AMFI_PORTFOLIO_URL) -> list[DisclosureLink]:
        files: list[DisclosureLink] = []
        landing_pages: list[str] = []
        static_error: Exception | None = None
        try:
            html = self.fetch_html(source_url)
            files, landing_pages = extract_page_links(
                html,
                source_url,
                "static_html",
                default_disclosure_type="Portfolio Disclosure",
            )
            LOGGER.info("Static discovery found %d files and %d landing pages", len(files), len(landing_pages))
        except requests.RequestException as exc:
            static_error = exc
            LOGGER.warning("Static AMFI discovery failed: %s", exc)

        if self.browser_fallback and not files and not landing_pages:
            try:
                browser_files, browser_pages = discover_with_browser(source_url, self.debug_dir)
                files.extend(browser_files)
                landing_pages.extend(browser_pages)
                LOGGER.info(
                    "Playwright discovery found %d files and %d landing pages",
                    len(browser_files),
                    len(browser_pages),
                )
            except BrowserUnavailable as exc:
                LOGGER.warning("Playwright fallback unavailable: %s", exc)
            except Exception as exc:
                LOGGER.error("Playwright fallback failed: %s", exc)

        if static_error and not files and not landing_pages:
            raise RuntimeError(f"AMFI source was unreachable and no fallback links were discovered: {static_error}")

        for landing_url in list(dict.fromkeys(landing_pages)):
            amc_name = _amc_name_from_landing_url(landing_url)
            try:
                html = self.fetch_html(landing_url)
                landing_files, _ = extract_page_links(
                    html,
                    landing_url,
                    "static_html",
                    default_disclosure_type="Portfolio Disclosure",
                    default_amc_name=amc_name,
                )
                files.extend(landing_files)
                LOGGER.info("AMC page %s yielded %d files", landing_url, len(landing_files))
                if self.browser_fallback and not landing_files:
                    try:
                        browser_files, _ = discover_with_browser(landing_url, self.debug_dir)
                        files.extend(
                            replace(link, amc_name=link.amc_name or amc_name)
                            for link in browser_files
                        )
                        LOGGER.info(
                            "AMC browser fallback %s yielded %d files",
                            landing_url,
                            len(browser_files),
                        )
                    except BrowserUnavailable as exc:
                        LOGGER.warning("AMC browser fallback unavailable for %s: %s", landing_url, exc)
                    except Exception as exc:
                        LOGGER.warning("AMC browser fallback failed for %s: %s", landing_url, exc)
            except requests.RequestException as exc:
                LOGGER.warning("AMC page failed: %s (%s)", landing_url, exc)
        files = deduplicate_links(files)
        if not files:
            raise RuntimeError("Discovery completed but found zero disclosure files.")
        return files


def _amc_name_from_landing_url(url: str) -> str:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    return host.split(".")[0].replace("-", " ").title()
