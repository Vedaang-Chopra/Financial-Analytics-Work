from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .extract import PageEvidence, canonical_url, document_type_hint, extract_page_evidence, file_type_from_url
from .models import CandidateLink


class BrowserUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class BrowserEvidence:
    page: PageEvidence
    debug_artifacts: dict[str, str]


def render_reference_html(source_url: str, timeout_seconds: float) -> str:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise BrowserUnavailable("Playwright is not installed") from exc
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(source_url, wait_until="domcontentloaded", timeout=int(timeout_seconds * 1000))
            page.wait_for_timeout(1500)
            return page.content()
        finally:
            browser.close()


def save_browser_failure_artifacts(
    page: object,
    network_records: list[dict[str, object]],
    debug_dir: Path,
) -> dict[str, str]:
    debug_dir.mkdir(parents=True, exist_ok=True)
    artifacts: dict[str, str] = {}
    try:
        rendered_path = debug_dir / "rendered.html"
        rendered_path.write_text(page.content(), encoding="utf-8")
        artifacts["rendered_html"] = str(rendered_path)
    except Exception:
        pass
    try:
        screenshot_path = debug_dir / "screenshot.png"
        page.screenshot(path=str(screenshot_path), full_page=True, timeout=10_000)
        artifacts["screenshot"] = str(screenshot_path)
    except Exception:
        pass
    network_path = debug_dir / "network_log.jsonl"
    network_path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in network_records),
        encoding="utf-8",
    )
    artifacts["network_log"] = str(network_path)
    return artifacts


def augment_with_network_evidence(
    page: PageEvidence,
    network_records: list[dict[str, object]],
    source_url: str,
) -> PageEvidence:
    candidates = {candidate.url: candidate for candidate in page.candidate_links}
    api_hints = set(page.api_hints)
    for record in network_records:
        raw_url = record.get("url")
        if not isinstance(raw_url, str):
            continue
        url = canonical_url(raw_url)
        content_type = str(record.get("content_type") or "").casefold()
        if "/api/" in url.casefold() or "application/json" in content_type:
            api_hints.add(url)
        file_type = file_type_from_url(url)
        if file_type:
            candidates.setdefault(
                url,
                CandidateLink(
                    url=url,
                    text="",
                    file_type=file_type,
                    document_type_hint=document_type_hint(url),
                    source_page_url=source_url,
                    discovery_method="network_api",
                ),
            )
    values = tuple(candidates.values())
    return PageEvidence(
        static_links_found=page.static_links_found,
        download_links_found=sum(candidate.file_type is not None for candidate in values),
        candidate_links=values,
        file_types_found=tuple(sorted({candidate.file_type for candidate in values if candidate.file_type})),
        document_type_hints=tuple(
            sorted({candidate.document_type_hint for candidate in values if candidate.document_type_hint != "unknown"})
        ),
        api_hints=tuple(sorted(api_hints)),
        script_count=page.script_count,
        form_count=page.form_count,
    )


def inspect_with_browser(
    source_url: str,
    debug_dir: Path,
    timeout_seconds: float,
    *,
    persist_debug: bool = True,
) -> BrowserEvidence:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise BrowserUnavailable("Playwright is not installed") from exc

    if persist_debug:
        debug_dir.mkdir(parents=True, exist_ok=True)
    network_records: list[dict[str, object]] = []
    artifacts: dict[str, str] = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.on(
            "response",
            lambda response: network_records.append(
                {"url": response.url, "status": response.status, "content_type": response.headers.get("content-type")}
            ),
        )
        try:
            page.goto(source_url, wait_until="domcontentloaded", timeout=int(timeout_seconds * 1000))
            page.wait_for_timeout(1500)
            rendered_html = page.content()
            if persist_debug:
                rendered_path = debug_dir / "rendered.html"
                rendered_path.write_text(rendered_html, encoding="utf-8")
                artifacts["rendered_html"] = str(rendered_path)

                screenshot_path = debug_dir / "screenshot.png"
                page.screenshot(path=str(screenshot_path), full_page=True, timeout=10_000)
                artifacts["screenshot"] = str(screenshot_path)

                network_path = debug_dir / "network_log.jsonl"
                network_path.write_text(
                    "".join(json.dumps(record, sort_keys=True) + "\n" for record in network_records),
                    encoding="utf-8",
                )
                artifacts["network_log"] = str(network_path)

                accessibility_path = debug_dir / "accessibility_snapshot.json"
                accessibility_path.write_text(
                    json.dumps(
                        {"links": page.locator("a").all_inner_texts(), "buttons": page.locator("button").all_inner_texts()},
                        indent=2,
                        sort_keys=True,
                    ),
                    encoding="utf-8",
                )
                artifacts["accessibility_snapshot"] = str(accessibility_path)
            page_evidence = extract_page_evidence(rendered_html, source_url, "playwright")
            return BrowserEvidence(augment_with_network_evidence(page_evidence, network_records, source_url), artifacts)
        except Exception:
            if persist_debug:
                save_browser_failure_artifacts(page, network_records, debug_dir)
            raise
        finally:
            browser.close()
