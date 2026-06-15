from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from .models import SourceCandidate
from .source_registry import normalize_amc_name


AMFI_MEMBERS_URL = "https://www.amfiindia.com/aboutamfi?tab=members"
SEBI_REGISTERED_FUNDS_URL = "https://www.sebi.gov.in/cms/sebi_data/attachdocs/1464929174939.pdf"


class AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag.casefold() == "a" and attributes.get("href"):
            self._href = attributes["href"]
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "a" and self._href is not None:
            self.anchors.append((self._href, " ".join("".join(self._text).split())))
            self._href = None
            self._text = []


def _anchors(html: str) -> list[tuple[str, str]]:
    parser = AnchorParser()
    parser.feed(html)
    return parser.anchors


def _external_website(html: str, source_url: str, excluded_domains: set[str]) -> str | None:
    for href, _ in _anchors(html):
        url = urljoin(source_url, href)
        parsed = urlparse(url)
        domain = parsed.netloc.casefold().removeprefix("www.")
        if parsed.scheme in {"http", "https"} and domain and domain not in excluded_domains:
            return url
    return None


def discover_amfi_candidates(
    session,
    members_url: str = AMFI_MEMBERS_URL,
    *,
    timeout_seconds: float = 30,
    browser_fetcher=None,
) -> tuple[list[SourceCandidate], list[str]]:
    warnings: list[str] = []
    try:
        response = session.get(members_url, timeout=timeout_seconds, allow_redirects=True)
        response.raise_for_status()
    except Exception as exc:
        return [], [f"AMFI reference discovery failed: {exc}"]

    member_anchors = _anchors(response.text)
    if not any("mutual fund" in text.casefold() or text.casefold().endswith(" mf") for _, text in member_anchors):
        if browser_fetcher is not None:
            try:
                member_anchors = _anchors(browser_fetcher(members_url, timeout_seconds))
            except Exception as exc:
                warnings.append(f"AMFI browser fallback failed: {exc}")
    candidates: list[SourceCandidate] = []
    amfi_domain = urlparse(members_url).netloc.casefold().removeprefix("www.")
    for href, text in member_anchors:
        if "mutual fund" not in text.casefold() and not text.casefold().endswith(" mf"):
            continue
        detail_url = urljoin(members_url, href)
        provider_url: str | None = None
        try:
            detail = session.get(detail_url, timeout=timeout_seconds, allow_redirects=True)
            detail.raise_for_status()
            detail_html = detail.text
            provider_url = _external_website(detail_html, detail_url, {amfi_domain})
            if provider_url is None and browser_fetcher is not None:
                provider_url = _external_website(browser_fetcher(detail_url, timeout_seconds), detail_url, {amfi_domain})
        except Exception as exc:
            warnings.append(f"AMFI member detail failed for {text}: {exc}")
        candidates.append(
            SourceCandidate(
                amc_name=text,
                seed_url=provider_url,
                amc_website=provider_url,
                source_role="primary_provider",
                source_type="provider_homepage",
                expected_document_types=("portfolio_disclosure", "factsheet"),
                discovered_from="amfi_reference",
                confidence="high" if provider_url else "low",
                evidence_url=detail_url,
                normalized_amc_name=normalize_amc_name(text),
                unresolved_reasons=() if provider_url else ("missing_provider_url",),
                notes="Discovered from AMFI member reference page.",
            )
        )
    return candidates, warnings


def discover_sebi_candidates(
    session,
    source_url: str = SEBI_REGISTERED_FUNDS_URL,
    *,
    timeout_seconds: float = 30,
) -> tuple[list[SourceCandidate], list[str]]:
    try:
        response = session.get(source_url, timeout=timeout_seconds, allow_redirects=True)
        response.raise_for_status()
    except Exception as exc:
        return [], [f"SEBI reference discovery failed: {exc}"]
    content_type = str(getattr(response, "headers", {}).get("content-type", "")).casefold()
    content = getattr(response, "content", b"")
    if "pdf" in content_type or bytes(content[:4]) == b"%PDF":
        return [], ["SEBI reference response is binary and unsupported for deterministic Phase 1A extraction."]
    candidates: list[SourceCandidate] = []
    for href, text in _anchors(response.text):
        if "mutual fund" not in text.casefold():
            continue
        candidates.append(
            SourceCandidate(
                amc_name=text,
                seed_url=None,
                source_role="primary_provider",
                source_type="provider_homepage",
                discovered_from="sebi_reference",
                confidence="low",
                evidence_url=urljoin(source_url, href),
                normalized_amc_name=normalize_amc_name(text),
                unresolved_reasons=("missing_provider_url",),
                notes="SEBI evidence is corroborative and non-authoritative.",
            )
        )
    return candidates, []
