from __future__ import annotations

import csv
import html
from collections import Counter
from pathlib import Path
from typing import Iterable

from .artifacts import ArtifactPaths
from utils.url_utils import safe_name
from .models import ProviderProfile


SUMMARY_FIELDS = (
    "amc_name",
    "seed_url",
    "status",
    "detected_strategy",
    "strategy_confidence",
    "source_role",
    "source_type",
    "source_provenance",
    "requires_javascript",
    "static_links_found",
    "rendered_links_found",
    "download_links_found",
    "candidate_document_links_found",
    "file_types_found",
    "failure_reason",
    "debug_folder",
)


def calculate_metrics(profiles: Iterable[ProviderProfile]) -> dict[str, object]:
    profiles = list(profiles)
    statuses = Counter(profile.status for profile in profiles)
    strategies = Counter(profile.detected_strategy for profile in profiles)
    file_types = Counter(file_type for profile in profiles for file_type in profile.file_types_found)
    return {
        "total_amcs": len(profiles),
        "profiled_successfully": statuses["success"],
        "partial_success": statuses["partial_success"],
        "failed": statuses["failed"],
        "manual_review_required": statuses["manual_review_required"],
        "static_html_count": strategies["static_html"],
        "network_api_count": strategies["network_api"],
        "playwright_count": strategies["playwright"],
        "vlm_required_count": strategies["vlm_required"],
        "manual_review_count": strategies["manual_review"],
        "failed_blocked_count": strategies["failed_blocked"],
        "total_static_links_found": sum(profile.static_links_found for profile in profiles),
        "total_download_links_found": sum(profile.download_links_found for profile in profiles),
        "total_candidate_document_links_found": sum(profile.candidate_document_links_found for profile in profiles),
        "file_type_counts": dict(sorted(file_types.items())),
    }


def _row(profile: ProviderProfile, debug_root: Path) -> dict[str, object]:
    return {
        "amc_name": profile.amc_name,
        "seed_url": profile.seed_url,
        "status": profile.status,
        "detected_strategy": profile.detected_strategy,
        "strategy_confidence": profile.strategy_confidence,
        "source_role": profile.source_role,
        "source_type": profile.source_type,
        "source_provenance": ", ".join(profile.source_provenance),
        "requires_javascript": profile.requires_javascript,
        "static_links_found": profile.static_links_found,
        "rendered_links_found": profile.rendered_links_found,
        "download_links_found": profile.download_links_found,
        "candidate_document_links_found": profile.candidate_document_links_found,
        "file_types_found": ", ".join(profile.file_types_found),
        "failure_reason": profile.failure_reason or "",
        "debug_folder": str(debug_root / safe_name(profile.amc_name)),
    }


def generate_profile_reports(profiles: Iterable[ProviderProfile], paths: ArtifactPaths) -> None:
    profiles = list(profiles)
    paths.report_html.parent.mkdir(parents=True, exist_ok=True)
    rows = [_row(profile, paths.debug_root) for profile in profiles]
    with paths.summary_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    metrics = calculate_metrics(profiles)
    metric_rows = "".join(
        f"<tr><th>{html.escape(str(key))}</th><td>{html.escape(str(value))}</td></tr>"
        for key, value in metrics.items()
    )
    header = "".join(f"<th>{html.escape(field)}</th>" for field in SUMMARY_FIELDS)
    table_rows = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row[field]))}</td>" for field in SUMMARY_FIELDS) + "</tr>"
        for row in rows
    )
    paths.report_html.write_text(
        "<!doctype html><html><head><meta charset='utf-8'><title>Provider Profile Report</title>"
        "<style>body{font-family:Arial,sans-serif;margin:2rem}table{border-collapse:collapse;width:100%;margin-bottom:2rem}"
        "th,td{border:1px solid #ccc;padding:.45rem;text-align:left;vertical-align:top}th{background:#eee}</style>"
        "</head><body><h1>Mutual Fund Provider Profile Report</h1><h2>Metrics</h2><table>"
        f"{metric_rows}</table><h2>Providers</h2><table><thead><tr>{header}</tr></thead><tbody>{table_rows}</tbody></table>"
        "</body></html>",
        encoding="utf-8",
    )
