"""Ingestion run models and dataclasses."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin, urlparse


@dataclass(frozen=True)
class AgentResult:
    run_id: str
    status: str
    pages_visited: int = 0
    links_discovered: int = 0
    files_downloaded: int = 0
    intervals_staged: int = 0
    rows_inserted: int = 0
    rows_quarantined: int = 0
    retry_tasks: int = 0
    error_summary: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ParserResult:
    dataset_type: str
    parser_name: str
    parser_version: str
    confidence: float
    records: list[dict[str, Any]]
    warnings: list[str]
    errors: list[str]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class SourcePageRecord:
    url: str
    canonical_url: str
    parent_url: str | None
    domain: str
    title: str | None
    status_code: int | None
    page_relevance: str | None
    source_authority_type: str | None
    html_snapshot_path: str | None
    screenshot_path: str | None
    network_log_path: str | None
    metadata: dict[str, Any]


@dataclass(frozen=True)
class DiscoveredLinkRecord:
    url: str
    anchor_text: str | None
    link_type: str | None
    dataset_type_hint: str | None
    file_type_hint: str | None
    should_follow: bool
    relevance_score: float | None
    reason: str | None
    metadata: dict[str, Any]


@dataclass(frozen=True)
class DatasetCandidateRecord:
    url: str
    dataset_type: str | None
    provider_hint: str | None
    download_method: str | None
    file_type: str | None
    requires_browser: bool
    requires_form: bool
    requires_vlm: bool
    confidence: float | None
    status: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class RawArtifactRecord:
    source_url: str
    artifact_type: str
    file_type: str | None
    content_type: str | None
    checksum: str | None
    size_bytes: int | None
    local_path: str | None
    retained: bool
    metadata: dict[str, Any]
