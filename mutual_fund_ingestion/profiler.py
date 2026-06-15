from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from utils.url_utils import safe_name
from .browser import inspect_with_browser
from .extract import PageEvidence, extract_page_evidence
from .http import HttpSettings, build_session
from .models import AMCSource, ProviderProfile, SourcePage


@dataclass(frozen=True)
class ProfileOptions:
    browser_enabled: bool = True
    force: bool = False
    timeout_seconds: float = 30
    persist_debug: bool = True


@dataclass(frozen=True)
class ProfileContext:
    run_id: str
    created_at: str
    debug_root: Path
    session: Any | None = None
    options: ProfileOptions = field(default_factory=ProfileOptions)
    latest_profiles: dict[str, ProviderProfile] = field(default_factory=dict)


def _write_error(debug_dir: Path, errors: list[str]) -> str:
    debug_dir.mkdir(parents=True, exist_ok=True)
    path = debug_dir / "profiler_error.json"
    path.write_text(json.dumps({"errors": errors}, indent=2, sort_keys=True), encoding="utf-8")
    return str(path)


def _existing_debug_artifacts(debug_dir: Path) -> dict[str, str]:
    names = {
        "static_html": "static.html",
        "rendered_html": "rendered.html",
        "screenshot": "screenshot.png",
        "network_log": "network_log.jsonl",
        "accessibility_snapshot": "accessibility_snapshot.json",
        "profiler_error": "profiler_error.json",
    }
    return {key: str(debug_dir / name) for key, name in names.items() if (debug_dir / name).exists()}


def _profile_from_evidence(
    source: AMCSource,
    context: ProfileContext,
    evidence: PageEvidence,
    *,
    strategy: str,
    requires_javascript: bool,
    debug_artifacts: dict[str, str],
    status_code: int | None,
    notes: str = "",
) -> ProviderProfile:
    if evidence.candidate_links:
        status = "success"
        if strategy == "playwright" and all(
            candidate.discovery_method == "network_api" for candidate in evidence.candidate_links
        ):
            detected_strategy = "network_api"
        else:
            detected_strategy = strategy
    elif evidence.api_hints:
        status = "partial_success"
        detected_strategy = "network_api"
    else:
        status = "manual_review_required"
        detected_strategy = "vlm_required" if requires_javascript else "manual_review"
    patterns = tuple({"type": "extension", "value": f".{item}"} for item in evidence.file_types_found)
    return ProviderProfile(
        run_id=context.run_id,
        created_at=context.created_at,
        amc_name=source.amc_name,
        seed_url=source.seed_url,
        status=status,
        detected_strategy=detected_strategy,
        requires_javascript=requires_javascript,
        static_links_found=evidence.static_links_found if strategy == "static_html" else 0,
        download_links_found=evidence.download_links_found,
        candidate_document_links_found=len(evidence.candidate_links),
        file_types_found=evidence.file_types_found,
        document_type_hints=evidence.document_type_hints,
        known_link_patterns=patterns,
        source_pages_examined=(SourcePage(source.seed_url, status_code, strategy, evidence.static_links_found),),
        candidate_links=evidence.candidate_links,
        debug_artifacts=debug_artifacts,
        notes=notes,
        source_name=source.source_name,
        source_role=source.source_role,
        source_type=source.source_type,
        source_provenance=source.discovered_from,
        strategy_confidence="high" if evidence.candidate_links else "medium" if evidence.api_hints else "low",
        rendered_links_found=evidence.static_links_found if strategy == "playwright" else 0,
    )


def profile_source(source: AMCSource, context: ProfileContext) -> ProviderProfile:
    debug_dir = context.debug_root / safe_name(source.amc_name)
    debug_artifacts: dict[str, str] = {}
    errors: list[str] = []
    session = context.session or build_session(HttpSettings(timeout_seconds=context.options.timeout_seconds))
    static_evidence: PageEvidence | None = None
    status_code: int | None = None

    try:
        response = session.get(source.seed_url, timeout=context.options.timeout_seconds, allow_redirects=True)
        response.raise_for_status()
        status_code = getattr(response, "status_code", None)
        static_evidence = extract_page_evidence(response.text, source.seed_url, "static_html")
        if context.options.persist_debug:
            debug_dir.mkdir(parents=True, exist_ok=True)
            static_path = debug_dir / "static.html"
            static_path.write_text(response.text, encoding="utf-8")
            debug_artifacts["static_html"] = str(static_path)
        if static_evidence.candidate_links or static_evidence.api_hints:
            return _profile_from_evidence(
                source,
                context,
                static_evidence,
                strategy="static_html",
                requires_javascript=False,
                debug_artifacts=debug_artifacts,
                status_code=status_code,
            )
    except Exception as exc:
        errors.append(f"static_html: {exc}")

    if context.options.browser_enabled:
        try:
            browser = inspect_with_browser(
                source.seed_url,
                debug_dir,
                context.options.timeout_seconds,
                persist_debug=context.options.persist_debug,
            )
            debug_artifacts.update(browser.debug_artifacts)
            return _profile_from_evidence(
                source,
                context,
                browser.page,
                strategy="playwright",
                requires_javascript=True,
                debug_artifacts=debug_artifacts,
                status_code=status_code,
            )
        except Exception as exc:
            errors.append(f"playwright: {exc}")
            debug_artifacts.update(_existing_debug_artifacts(debug_dir))

    if static_evidence is not None:
        if context.options.persist_debug:
            failure_path = _write_error(debug_dir, errors or ["No relevant candidate links or API hints found"])
            debug_artifacts["profiler_error"] = failure_path
        return _profile_from_evidence(
            source,
            context,
            static_evidence,
            strategy="static_html",
            requires_javascript=None,
            debug_artifacts=debug_artifacts,
            status_code=status_code,
            notes="Deterministic inspection found no relevant disclosure evidence.",
        )

    if context.options.persist_debug:
        failure_path = _write_error(debug_dir, errors)
        debug_artifacts["profiler_error"] = failure_path
    return ProviderProfile(
        run_id=context.run_id,
        created_at=context.created_at,
        amc_name=source.amc_name,
        seed_url=source.seed_url,
        status="failed",
        detected_strategy="failed_blocked",
        requires_javascript=None,
        static_links_found=0,
        download_links_found=0,
        candidate_document_links_found=0,
        debug_artifacts=debug_artifacts,
        failure_reason="; ".join(errors),
        notes="All available deterministic profiling strategies failed.",
        source_name=source.source_name,
        source_role=source.source_role,
        source_type=source.source_type,
        source_provenance=source.discovered_from,
        strategy_confidence="high",
    )


def profile_sources(sources: Iterable[AMCSource], context: ProfileContext) -> list[ProviderProfile]:
    profiles: list[ProviderProfile] = []
    for source in sources:
        existing = context.latest_profiles.get(source.amc_name)
        if existing is not None and not context.options.force:
            profiles.append(existing)
        else:
            profiles.append(profile_source(source, context))
    return profiles
