from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

from .models import CandidateLink
from utils.url_utils import canonical_url, file_type_from_url


FILE_EXTENSIONS = {"pdf", "xls", "xlsx", "csv", "zip"}
DOCUMENT_TERMS = {
    "portfolio_disclosure": ("portfolio", "holding"),
    "factsheet": ("factsheet", "fact sheet"),
    "statutory_disclosure": ("statutory", "disclosure"),
    "ter": ("total expense ratio", "ter"),
    "sid": ("scheme information document", "sid"),
    "kim": ("key information memorandum", "kim"),
    "notice": ("notice",),
    "form": ("form",),
}
EMBEDDED_URL = re.compile(
    r"""["']((?:https?://|/)[^"'<> \t\r\n]+?\.(?:pdf|xls|xlsx|csv|zip)[^"'<> \t\r\n]*)["']""",
    re.IGNORECASE,
)
EMBEDDED_API_URL = re.compile(
    r"""["']((?:https?://[^"'<> \t\r\n]*?/api(?:/|\?)|/api(?:/|\?))[^"'<> \t\r\n]*)["']""",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class PageEvidence:
    static_links_found: int
    download_links_found: int
    candidate_links: tuple[CandidateLink, ...]
    file_types_found: tuple[str, ...]
    document_type_hints: tuple[str, ...]
    api_hints: tuple[str, ...]
    script_count: int
    form_count: int


class EvidenceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[dict[str, str]] = []
        self.forms: list[str] = []
        self.script_count = 0
        self._anchor: dict[str, str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.casefold(): value or "" for key, value in attrs}
        if tag.casefold() == "a" and attributes.get("href"):
            self._anchor = {"href": attributes["href"].strip(), "text": "", "title": attributes.get("title", "")}
        elif tag.casefold() == "form" and attributes.get("action"):
            self.forms.append(attributes["action"].strip())
        elif tag.casefold() == "script":
            self.script_count += 1

    def handle_data(self, data: str) -> None:
        if self._anchor is not None:
            self._anchor["text"] += data

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "a" and self._anchor is not None:
            self._anchor["text"] = " ".join(self._anchor["text"].split())
            self.anchors.append(self._anchor)
            self._anchor = None



def document_type_hint(text: str) -> str:
    normalized = unquote(text).casefold()
    for document_type, terms in DOCUMENT_TERMS.items():
        if any(term in normalized for term in terms):
            return document_type
    return "unknown"


def extract_page_evidence(html: str, source_url: str, discovery_method: str) -> PageEvidence:
    parser = EvidenceParser()
    parser.feed(html)
    candidates: dict[str, CandidateLink] = {}
    api_hints: set[str] = set()

    for anchor in parser.anchors:
        if anchor["href"].startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        url = canonical_url(urljoin(source_url, anchor["href"]))
        text = " ".join((anchor["text"], anchor["title"], url))
        file_type = file_type_from_url(url)
        hint = document_type_hint(text)
        if file_type or hint != "unknown":
            candidates.setdefault(
                url,
                CandidateLink(url, anchor["text"] or anchor["title"], file_type, hint, source_url, discovery_method),
            )

    for action in parser.forms:
        url = canonical_url(urljoin(source_url, action))
        if "/api/" in url.casefold() or "/api?" in url.casefold():
            api_hints.add(url)

    for match in EMBEDDED_URL.finditer(html):
        url = canonical_url(urljoin(source_url, match.group(1)))
        file_type = file_type_from_url(url)
        if file_type:
            hint = document_type_hint(url)
            candidates.setdefault(url, CandidateLink(url, "", file_type, hint, source_url, discovery_method))

    for match in EMBEDDED_API_URL.finditer(html):
        api_hints.add(canonical_url(urljoin(source_url, match.group(1))))

    file_types = sorted({candidate.file_type for candidate in candidates.values() if candidate.file_type})
    hints = sorted({candidate.document_type_hint for candidate in candidates.values() if candidate.document_type_hint != "unknown"})
    return PageEvidence(
        static_links_found=len(parser.anchors),
        download_links_found=sum(candidate.file_type is not None for candidate in candidates.values()),
        candidate_links=tuple(candidates.values()),
        file_types_found=tuple(file_types),
        document_type_hints=tuple(hints),
        api_hints=tuple(sorted(api_hints)),
        script_count=parser.script_count,
        form_count=len(parser.forms),
    )
