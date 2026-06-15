from __future__ import annotations

from pathlib import Path
import yaml

from .models import AMCSource, SourceRegistryEntry


DEFAULT_REGISTRY = Path("configs/amc_sources.yaml")


def load_registry(path: Path = DEFAULT_REGISTRY) -> list[SourceRegistryEntry]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw.get("sources"), list):
        raise ValueError(f"{path} must contain a sources list")

    entries: list[SourceRegistryEntry] = []
    provider_names: set[str] = set()
    reference_names: set[str] = set()
    for item in raw["sources"]:
        source_role = item.get("source_role", "primary_provider")
        legacy_provider = source_role == "primary_provider" and "discovered_from" not in item
        entry = SourceRegistryEntry(
            amc_name=item.get("amc_name"),
            source_name=item.get("source_name"),
            amc_website=item.get("amc_website"),
            seed_url=item.get("seed_url"),
            enabled=bool(item.get("enabled", True)),
            source_role=source_role,
            source_type=item.get(
                "source_type",
                "provider_homepage" if source_role == "primary_provider" else "industry_reference_portal",
            ),
            expected_document_types=tuple(item.get("expected_document_types", ())),
            discovered_from=tuple(
                item.get(
                    "discovered_from",
                    ("existing_config", "manual_curated") if legacy_provider else ("existing_config",),
                )
            ),
            confidence=item.get("confidence", "unknown"),
            priority=item.get("priority", "primary" if source_role == "primary_provider" else "secondary"),
            manual_overrides=tuple(
                item.get("manual_overrides", ("seed_url", "source_type") if legacy_provider else ())
            ),
            unresolved_reasons=tuple(item.get("unresolved_reasons", ())),
            access_notes=item.get("access_notes", ""),
            notes=item.get("notes", ""),
        )
        key = (entry.amc_name or "").casefold() if source_role == "primary_provider" else (entry.source_name or "").casefold()
        names = provider_names if source_role == "primary_provider" else reference_names
        if key in names:
            raise ValueError(f"Duplicate {source_role} in source registry: {entry.amc_name or entry.source_name}")
        names.add(key)
        entries.append(entry)
    return entries


def load_sources(
    path: Path = DEFAULT_REGISTRY,
    *,
    limit: int | None = None,
    amc: str | None = None,
) -> list[AMCSource]:
    sources: list[AMCSource] = []
    for entry in load_registry(path):
        source = entry.to_provider_source()
        if source is not None and (amc is None or source.amc_name.casefold() == amc.casefold()):
            sources.append(source)
    if amc is not None and not sources:
        raise ValueError(f"Enabled AMC not found: {amc}")
    return sources[:limit] if limit is not None else sources
