from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from urllib.parse import urlparse


PROFILE_STATUSES = {"success", "partial_success", "failed", "manual_review_required"}
STRATEGIES = {
    "static_html",
    "network_api",
    "playwright",
    "vlm_required",
    "manual_review",
    "failed_blocked",
    "unknown",
}
DOCUMENT_TYPES = {
    "portfolio_disclosure",
    "factsheet",
    "statutory_disclosure",
    "ter",
    "sid",
    "kim",
    "notice",
    "form",
    "unknown",
}
REFERENCE_DOCUMENT_TYPES = {"scheme_metadata", "nav_reference", "disclosure_index"}
REGISTRY_DOCUMENT_TYPES = DOCUMENT_TYPES | REFERENCE_DOCUMENT_TYPES
DISCOVERY_METHODS = {"static_html", "network_api", "playwright"}
SOURCE_ROLES = {"primary_provider", "reference_index"}
CONFIDENCE_LEVELS = {"low", "medium", "high", "unknown"}
PRIORITIES = {"primary", "secondary"}


def _valid_http_url(value: str, label: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{label} must be an absolute HTTP(S) URL: {value}")


@dataclass(frozen=True)
class AMCSource:
    amc_name: str
    seed_url: str
    enabled: bool
    source_type: str
    expected_document_types: tuple[str, ...] = ()
    notes: str = ""
    source_name: str | None = None
    source_role: str = "primary_provider"
    discovered_from: tuple[str, ...] = ()
    confidence: str = "unknown"
    priority: str = "primary"
    manual_overrides: tuple[str, ...] = ()
    access_notes: str = ""

    def __post_init__(self) -> None:
        if not self.amc_name.strip():
            raise ValueError("amc_name is required")
        _valid_http_url(self.seed_url, "seed_url")
        unknown = set(self.expected_document_types) - DOCUMENT_TYPES
        if unknown:
            raise ValueError(f"Unsupported expected document types: {sorted(unknown)}")
        if self.source_role != "primary_provider":
            raise ValueError("AMCSource must use source_role=primary_provider")
        if self.confidence not in CONFIDENCE_LEVELS:
            raise ValueError(f"Unsupported confidence: {self.confidence}")


@dataclass(frozen=True)
class SourceRegistryEntry:
    enabled: bool
    source_role: str
    source_type: str
    seed_url: str | None = None
    amc_name: str | None = None
    source_name: str | None = None
    amc_website: str | None = None
    expected_document_types: tuple[str, ...] = ()
    discovered_from: tuple[str, ...] = ()
    confidence: str = "unknown"
    priority: str = "primary"
    manual_overrides: tuple[str, ...] = ()
    unresolved_reasons: tuple[str, ...] = ()
    access_notes: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        if self.source_role not in SOURCE_ROLES:
            raise ValueError(f"Unsupported source role: {self.source_role}")
        if self.source_role == "primary_provider" and not (self.amc_name or "").strip():
            raise ValueError("amc_name is required for primary provider sources")
        if self.source_role == "reference_index" and not (self.source_name or "").strip():
            raise ValueError("source_name is required for reference index sources")
        if self.seed_url:
            _valid_http_url(self.seed_url, "seed_url")
        if self.amc_website:
            _valid_http_url(self.amc_website, "amc_website")
        unknown = set(self.expected_document_types) - REGISTRY_DOCUMENT_TYPES
        if unknown:
            raise ValueError(f"Unsupported expected document types: {sorted(unknown)}")
        if self.confidence not in CONFIDENCE_LEVELS:
            raise ValueError(f"Unsupported confidence: {self.confidence}")
        if self.priority not in PRIORITIES:
            raise ValueError(f"Unsupported priority: {self.priority}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_provider_source(self) -> AMCSource | None:
        if self.source_role != "primary_provider" or not self.enabled or not self.seed_url:
            return None
        return AMCSource(
            amc_name=self.amc_name or "",
            seed_url=self.seed_url,
            enabled=self.enabled,
            source_type=self.source_type,
            expected_document_types=tuple(
                item for item in self.expected_document_types if item in DOCUMENT_TYPES
            ),
            notes=self.notes,
            source_name=self.source_name,
            source_role=self.source_role,
            discovered_from=self.discovered_from,
            confidence=self.confidence,
            priority=self.priority,
            manual_overrides=self.manual_overrides,
            access_notes=self.access_notes,
        )


@dataclass(frozen=True)
class SourceCandidate:
    source_role: str
    source_type: str
    discovered_from: str
    confidence: str
    normalized_amc_name: str
    amc_name: str | None = None
    source_name: str | None = None
    seed_url: str | None = None
    amc_website: str | None = None
    expected_document_types: tuple[str, ...] = ()
    evidence_url: str | None = None
    enabled: bool = True
    priority: str = "primary"
    manual_overrides: tuple[str, ...] = ()
    unresolved_reasons: tuple[str, ...] = ()
    access_notes: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        if self.source_role not in SOURCE_ROLES:
            raise ValueError(f"Unsupported source role: {self.source_role}")
        if self.confidence not in CONFIDENCE_LEVELS:
            raise ValueError(f"Unsupported confidence: {self.confidence}")
        if self.seed_url:
            _valid_http_url(self.seed_url, "candidate seed_url")
        if self.evidence_url:
            _valid_http_url(self.evidence_url, "candidate evidence_url")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CandidateLink:
    url: str
    text: str
    file_type: str | None
    document_type_hint: str
    source_page_url: str
    discovery_method: str

    def __post_init__(self) -> None:
        _valid_http_url(self.url, "candidate link URL")
        _valid_http_url(self.source_page_url, "candidate source page URL")
        if self.document_type_hint not in DOCUMENT_TYPES:
            raise ValueError(f"Unsupported document type hint: {self.document_type_hint}")
        if self.discovery_method not in DISCOVERY_METHODS:
            raise ValueError(f"Unsupported discovery method: {self.discovery_method}")


@dataclass(frozen=True)
class SourcePage:
    url: str
    status_code: int | None
    method: str
    links_found: int

    def __post_init__(self) -> None:
        _valid_http_url(self.url, "source page URL")
        if self.method not in DISCOVERY_METHODS:
            raise ValueError(f"Unsupported source page method: {self.method}")


@dataclass(frozen=True)
class ProviderProfile:
    run_id: str
    created_at: str
    amc_name: str
    seed_url: str
    status: str
    detected_strategy: str
    requires_javascript: bool | None
    static_links_found: int
    download_links_found: int
    candidate_document_links_found: int
    file_types_found: tuple[str, ...] = ()
    document_type_hints: tuple[str, ...] = ()
    known_link_patterns: tuple[dict[str, str], ...] = ()
    known_selectors: dict[str, str] = field(default_factory=dict)
    source_pages_examined: tuple[SourcePage, ...] = ()
    candidate_links: tuple[CandidateLink, ...] = ()
    debug_artifacts: dict[str, str] = field(default_factory=dict)
    failure_reason: str | None = None
    notes: str = ""
    schema_version: str = "provider_profile_v1"
    source_name: str | None = None
    source_role: str = "primary_provider"
    source_type: str = "provider_homepage"
    source_provenance: tuple[str, ...] = ()
    strategy_confidence: str = "unknown"
    rendered_links_found: int = 0

    def __post_init__(self) -> None:
        if self.schema_version != "provider_profile_v1":
            raise ValueError(f"Unsupported schema version: {self.schema_version}")
        if self.status not in PROFILE_STATUSES:
            raise ValueError(f"Unsupported profile status: {self.status}")
        if self.detected_strategy not in STRATEGIES:
            raise ValueError(f"Unsupported strategy: {self.detected_strategy}")
        if self.source_role not in SOURCE_ROLES:
            raise ValueError(f"Unsupported source role: {self.source_role}")
        if self.strategy_confidence not in CONFIDENCE_LEVELS:
            raise ValueError(f"Unsupported strategy confidence: {self.strategy_confidence}")
        _valid_http_url(self.seed_url, "seed_url")
        unknown = set(self.document_type_hints) - DOCUMENT_TYPES
        if unknown:
            raise ValueError(f"Unsupported document type hints: {sorted(unknown)}")
        object.__setattr__(self, "candidate_links", tuple(self.candidate_links[:25]))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProviderProfile":
        converted = dict(data)
        converted["source_pages_examined"] = tuple(
            item if isinstance(item, SourcePage) else SourcePage(**item)
            for item in converted.get("source_pages_examined", ())
        )
        converted["candidate_links"] = tuple(
            item if isinstance(item, CandidateLink) else CandidateLink(**item)
            for item in converted.get("candidate_links", ())
        )
        for field_name in (
            "file_types_found",
            "document_type_hints",
            "known_link_patterns",
            "source_provenance",
        ):
            converted[field_name] = tuple(converted.get(field_name, ()))
        return cls(**converted)
