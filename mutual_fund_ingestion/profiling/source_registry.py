from __future__ import annotations

import re
import json
import html
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import yaml

from .models import SourceCandidate, SourceRegistryEntry


NAME_SUFFIXES = re.compile(r"\b(mutual\s+fund|mf|asset\s+management(?:\s+company)?|amc)\b", re.IGNORECASE)
PROVENANCE_RANK = {
    "manual_curated": 50,
    "existing_config": 40,
    "amfi_reference": 30,
    "manual_reference": 20,
    "sebi_reference": 10,
}


@dataclass(frozen=True)
class SourceRegistryPaths:
    config: Path
    candidates: Path
    latest: Path
    report_html: Path

    @classmethod
    def from_roots(cls, config: Path, raw_dir: Path, report_dir: Path) -> "SourceRegistryPaths":
        return cls(
            config=config,
            candidates=raw_dir / "source_registry_candidates.jsonl",
            latest=raw_dir / "source_registry.latest.json",
            report_html=report_dir / "source_registry_report.html",
        )


def normalize_amc_name(value: str) -> str:
    normalized = NAME_SUFFIXES.sub(" ", value.casefold())
    return re.sub(r"[^a-z0-9]+", " ", normalized).strip()


def normalize_domain(value: str | None) -> str:
    if not value:
        return ""
    return urlparse(value).netloc.casefold().removeprefix("www.")


def candidates_from_registry(entries: list[SourceRegistryEntry]) -> list[SourceCandidate]:
    candidates: list[SourceCandidate] = []
    for entry in entries:
        provenance = entry.discovered_from or ("existing_config",)
        for discovered_from in provenance:
            candidates.append(
                SourceCandidate(
                    amc_name=entry.amc_name,
                    source_name=entry.source_name,
                    seed_url=entry.seed_url,
                    amc_website=entry.amc_website,
                    enabled=entry.enabled,
                    source_role=entry.source_role,
                    source_type=entry.source_type,
                    expected_document_types=entry.expected_document_types,
                    discovered_from=discovered_from,
                    confidence=entry.confidence,
                    priority=entry.priority,
                    manual_overrides=entry.manual_overrides,
                    unresolved_reasons=entry.unresolved_reasons,
                    access_notes=entry.access_notes,
                    notes=entry.notes,
                    normalized_amc_name=normalize_amc_name(entry.amc_name or entry.source_name or ""),
                    evidence_url=entry.seed_url,
                )
            )
    return candidates


def _group_key(candidate: SourceCandidate) -> tuple[str, str]:
    if candidate.source_role == "reference_index":
        return candidate.source_role, normalize_amc_name(candidate.source_name or "")
    name = candidate.normalized_amc_name or normalize_amc_name(candidate.amc_name or "")
    return candidate.source_role, name or normalize_domain(candidate.seed_url or candidate.amc_website)


def _ordered(candidates: list[SourceCandidate]) -> list[SourceCandidate]:
    return sorted(
        candidates,
        key=lambda item: (
            PROVENANCE_RANK.get(item.discovered_from, 0),
            {"high": 3, "medium": 2, "low": 1, "unknown": 0}[item.confidence],
        ),
        reverse=True,
    )


def merge_source_candidates(
    candidates: list[SourceCandidate],
) -> tuple[list[SourceRegistryEntry], list[dict[str, object]]]:
    groups: dict[tuple[str, str], list[SourceCandidate]] = defaultdict(list)
    domain_groups: dict[str, tuple[str, str]] = {}
    for candidate in candidates:
        key = _group_key(candidate)
        domain = normalize_domain(candidate.seed_url or candidate.amc_website)
        if candidate.source_role == "primary_provider" and domain in domain_groups:
            key = domain_groups[domain]
        groups[key].append(candidate)
        if candidate.source_role == "primary_provider" and domain:
            domain_groups[domain] = key

    merged: list[SourceRegistryEntry] = []
    decisions: list[dict[str, object]] = []
    for key, group in groups.items():
        ordered = _ordered(group)
        base = ordered[0]
        locked = {field for item in group for field in item.manual_overrides}

        def choose(field: str):
            locked_values = [getattr(item, field) for item in ordered if field in item.manual_overrides and getattr(item, field)]
            values = locked_values or [getattr(item, field) for item in ordered if getattr(item, field)]
            return values[0] if values else None

        seed_url = choose("seed_url")
        unresolved = {reason for item in group for reason in item.unresolved_reasons}
        if base.source_role == "primary_provider" and not seed_url:
            unresolved.add("missing_provider_url")
        else:
            unresolved.discard("missing_provider_url")
        provenance = tuple(dict.fromkeys(item.discovered_from for item in ordered))
        entry = SourceRegistryEntry(
            amc_name=choose("amc_name"),
            source_name=choose("source_name"),
            seed_url=seed_url,
            amc_website=choose("amc_website"),
            enabled=base.enabled,
            source_role=base.source_role,
            source_type=choose("source_type") or base.source_type,
            expected_document_types=tuple(
                sorted({document_type for item in group for document_type in item.expected_document_types})
            ),
            discovered_from=provenance,
            confidence=base.confidence,
            priority=choose("priority") or base.priority,
            manual_overrides=tuple(sorted(locked)),
            unresolved_reasons=tuple(sorted(unresolved)),
            access_notes=choose("access_notes") or "",
            notes=choose("notes") or "",
        )
        merged.append(entry)
        if len(group) > 1:
            decisions.append(
                {
                    "source_role": key[0],
                    "normalized_key": key[1],
                    "candidate_count": len(group),
                    "selected_seed_url": entry.seed_url,
                    "locked_fields": sorted(locked),
                    "provenance": list(provenance),
                }
            )
    return sorted(merged, key=lambda item: (item.source_role, (item.amc_name or item.source_name or "").casefold())), decisions


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def _yaml_entry(entry: SourceRegistryEntry) -> dict[str, object]:
    data = entry.to_dict()
    return {
        key: list(value) if isinstance(value, tuple) else value
        for key, value in data.items()
        if value not in (None, "", (), [])
    }


def write_source_registry_artifacts(
    candidates: list[SourceCandidate],
    entries: list[SourceRegistryEntry],
    paths: SourceRegistryPaths,
    *,
    dry_run: bool = False,
) -> None:
    if dry_run:
        return
    candidates_text = "".join(json.dumps(candidate.to_dict(), sort_keys=True) + "\n" for candidate in candidates)
    latest_text = json.dumps([entry.to_dict() for entry in entries], indent=2, sort_keys=True)
    config_text = yaml.safe_dump(
        {"sources": [_yaml_entry(entry) for entry in entries]},
        allow_unicode=False,
        sort_keys=False,
    )
    _atomic_write(paths.candidates, candidates_text)
    _atomic_write(paths.latest, latest_text)
    _atomic_write(paths.config, config_text)


def calculate_source_registry_metrics(
    entries: list[SourceRegistryEntry],
    *,
    merge_count: int = 0,
) -> dict[str, int]:
    return {
        "total_sources": len(entries),
        "primary_provider_sources": sum(entry.source_role == "primary_provider" for entry in entries),
        "reference_sources": sum(entry.source_role == "reference_index" for entry in entries),
        "amfi_reference_sources": sum(
            entry.source_name == "AMFI" or "amfi_reference" in entry.discovered_from for entry in entries
        ),
        "sebi_reference_sources": sum(
            entry.source_name == "SEBI" or "sebi_reference" in entry.discovered_from for entry in entries
        ),
        "manual_curated_sources": sum("manual_curated" in entry.discovered_from for entry in entries),
        "duplicate_merged_sources": merge_count,
        "sources_missing_seed_urls": sum(entry.source_role == "primary_provider" and not entry.seed_url for entry in entries),
        "sources_requiring_manual_completion": sum(bool(entry.unresolved_reasons) for entry in entries),
    }


def generate_source_registry_report(
    entries: list[SourceRegistryEntry],
    decisions: list[dict[str, object]],
    warnings: list[str],
    paths: SourceRegistryPaths,
) -> None:
    metrics = calculate_source_registry_metrics(entries, merge_count=len(decisions))
    metric_rows = "".join(
        f"<tr><th>{html.escape(key)}</th><td>{value}</td></tr>" for key, value in metrics.items()
    )
    source_rows = "".join(
        "<tr>"
        f"<td>{html.escape(entry.amc_name or entry.source_name or '')}</td>"
        f"<td>{html.escape(entry.source_role)}</td>"
        f"<td>{html.escape(entry.seed_url or '')}</td>"
        f"<td>{html.escape(', '.join(entry.discovered_from))}</td>"
        f"<td>{html.escape(', '.join(entry.unresolved_reasons))}</td>"
        "</tr>"
        for entry in entries
    )
    warning_items = "".join(f"<li>{html.escape(item)}</li>" for item in warnings) or "<li>None</li>"
    decision_rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(item.get('normalized_key', '')))}</td>"
        f"<td>{html.escape(str(item.get('candidate_count', '')))}</td>"
        f"<td>{html.escape(str(item.get('selected_seed_url', '')))}</td>"
        f"<td>{html.escape(', '.join(item.get('locked_fields', [])))}</td>"
        "</tr>"
        for item in decisions
    ) or "<tr><td colspan='4'>No duplicate candidates were merged.</td></tr>"
    content = (
        "<!doctype html><html><head><meta charset='utf-8'><title>Source Registry Report</title>"
        "<style>body{font-family:Arial,sans-serif;margin:2rem}table{border-collapse:collapse;width:100%;margin-bottom:2rem}"
        "th,td{border:1px solid #ccc;padding:.45rem;text-align:left;vertical-align:top}th{background:#eee}</style>"
        "</head><body><h1>Mutual Fund Source Registry Report</h1><h2>Metrics</h2><table>"
        f"{metric_rows}</table><h2>Warnings</h2><ul>{warning_items}</ul><h2>Sources</h2>"
        "<table><thead><tr><th>Name</th><th>Role</th><th>Seed URL</th><th>Provenance</th><th>Unresolved</th></tr></thead>"
        f"<tbody>{source_rows}</tbody></table><h2>Merge Decisions</h2>"
        "<table><thead><tr><th>Normalized Key</th><th>Candidates</th><th>Selected Seed URL</th><th>Locked Fields</th></tr></thead>"
        f"<tbody>{decision_rows}</tbody></table></body></html>"
    )
    _atomic_write(paths.report_html, content)
