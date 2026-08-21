"""Discovery engine for URL queue management and link extraction."""
from __future__ import annotations

import logging
import re
from collections import deque
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin, urlparse

import requests

from utils.http import HttpSettings, build_session, get_with_retry
from utils.url_utils import canonical_url, file_type_from_url


LOGGER = logging.getLogger(__name__)

DATASET_TYPE_HINTS = {
    "portfolio_disclosure": ["portfolio", "holding", "monthly portfolio", "fortnightly portfolio", "dashboard", "monthly dashboard"],
    "factsheet": ["factsheet", "fact sheet"],
    "nav_history": ["nav", "net asset value", "historical nav", "navall"],
    "ter": ["total expense ratio", "ter"],
    "sid": ["scheme information document", "sid"],
    "kim": ["key information memorandum", "kim"],
    "aum_aaum": ["aum", "aaum"],
    "scheme_master": ["scheme", "scheme code", "scheme name"],
    "amc_provider_list": ["amc", "mutual fund", "fund house", "members"],
    "statutory_disclosure": ["statutory", "disclosure"],
}

def _keyword_matches(text: str, keyword: str) -> bool:
    keyword_l = keyword.lower()
    if keyword_l.isalpha() and len(keyword_l) <= 3:
        return re.search(rf"(?<!\w){re.escape(keyword_l)}(?!\w)", text) is not None
    return keyword_l in text

RELEVANCE_KEYWORDS = {
    "high": ["NAV", "Net Asset Value", "Scheme", "Portfolio", "Portfolio Disclosure",
              "Monthly Portfolio", "Factsheet", "Fact Sheet", "Disclosure"],
    "low": ["careers", "contact", "privacy", "terms", "sitemap", 
            "press release", "login", "feedback", "branches"],
}


class LinkExtractor:
    """Simple regex-based link extractor for discovery pages."""

    def __init__(self) -> None:
        self.anchors: list[dict[str, str]] = []

    def feed(self, html: str) -> None:
        import re
        pattern = re.compile(r'<a\s+([^>]*?)>(.*?)</a>', re.IGNORECASE | re.DOTALL)
        for match in pattern.finditer(html):
            attrs_str, text = match.groups()
            attrs = dict(re.findall(r'(\w+)=["\']([^"\']*)["\']', attrs_str))
            href = attrs.get("href", "")
            if href and not href.startswith(("#", "javascript:", "mailto:", "tel:")):
                self.anchors.append({
                    "href": href,
                    "text": re.sub(r'<[^>]+>', '', text).strip(),
                    "title": attrs.get("title", ""),
                })


@dataclass
class DiscoveryEngine:
    session: requests.Session
    settings: HttpSettings
    visited_urls: set[str] = field(default_factory=set)
    url_queue: deque[tuple[str, str | None, int]] = field(default_factory=deque)

    def __post_init__(self) -> None:
        if self.session is None:
            self.session = build_session(self.settings)

    def add_urls(self, urls: list[str], parent: str | None = None, depth: int = 0) -> None:
        for url in urls:
            c_url = canonical_url(url)
            if c_url not in self.visited_urls:
                self.url_queue.append((c_url, parent, depth))

    def fetch(self, url: str) -> tuple[int, str | None]:
        try:
            response = get_with_retry(
                self.session,
                url,
                timeout=self.settings.timeout_seconds,
            )
            if response.status_code >= 400:
                return response.status_code, None
            content_type = response.headers.get("content-type", "").lower()
            if "text/html" in content_type or "application/xhtml" in content_type:
                return response.status_code, response.text
            return response.status_code, None
        except requests.RequestException:
            return 0, None

    def extract_links(self, html: str, source_url: str) -> list[dict[str, str]]:
        parser = LinkExtractor()
        parser.feed(html)
        links = []
        for anchor in parser.anchors:
            href = anchor["href"]
            if href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue
            full_url = canonical_url(urljoin(source_url, href))
            links.append({"url": full_url, "text": anchor.get("text", ""), "title": anchor.get("title", "")})
        return links

    def score_relevance(self, url: str, text: str, title: str) -> tuple[float, str | None]:
        combined = (text + " " + title + " " + url).lower()
        for term in RELEVANCE_KEYWORDS["low"]:
            if _keyword_matches(combined, term):
                return 0.0, None
        for term in RELEVANCE_KEYWORDS["high"]:
            if _keyword_matches(combined, term):
                return 0.8, "relevant"
        for dataset_type, keywords in DATASET_TYPE_HINTS.items():
            for keyword in keywords:
                if _keyword_matches(combined, keyword):
                    return 0.7, dataset_type
        return 0.3, None

    def classify_dataset(self, url: str, text: str) -> str | None:
        combined = (text + " " + url).lower()
        for dataset_type, keywords in DATASET_TYPE_HINTS.items():
            for keyword in keywords:
                if _keyword_matches(combined, keyword):
                    return dataset_type
        return None

    def get_file_type(self, url: str) -> str | None:
        return file_type_from_url(url)

    def get_domain(self, url: str) -> str:
        return urlparse(url).netloc.lower().removeprefix("www.")

    def is_off_domain(self, url: str, task_domain: str) -> bool:
        return self.get_domain(url) != task_domain
