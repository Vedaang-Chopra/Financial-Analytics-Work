"""Source Capability Registry - Unified machine-readable registry for ingestion system.

This module loads and provides access to:
1. AMFI Dataset Census (configs/amfi_dataset_census.yaml)
2. AMC Capability Matrix (configs/amc_capability_matrix.yaml)
3. Provider Profiles (data/raw/mutual_funds/provider_profiles/provider_profiles.latest.json)

All ingestion pipelines should use this registry instead of hardcoding AMC/dataset logic.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import yaml

LOGGER = logging.getLogger(__name__)

# Default paths
DEFAULT_AMFI_CENSUS = Path("configs/amfi_dataset_census.yaml")
DEFAULT_AMC_MATRIX = Path("configs/amc_capability_matrix.yaml")
DEFAULT_PROVIDER_PROFILES = Path("data/raw/mutual_funds/provider_profiles/provider_profiles.latest.json")


class SourceCapabilityRegistry:
    """Unified registry for all source capabilities and dataset information."""

    def __init__(
        self,
        amfi_census_path: Path | str = DEFAULT_AMFI_CENSUS,
        amc_matrix_path: Path | str = DEFAULT_AMC_MATRIX,
        provider_profiles_path: Path | str = DEFAULT_PROVIDER_PROFILES,
    ):
        self.amfi_census_path = Path(amfi_census_path)
        self.amc_matrix_path = Path(amc_matrix_path)
        self.provider_profiles_path = Path(provider_profiles_path)

        self._amfi_census: dict[str, Any] | None = None
        self._amc_matrix: dict[str, Any] | None = None
        self._provider_profiles: list[dict[str, Any]] | None = None
        self._amc_by_name: dict[str, dict[str, Any]] = {}
        self._amc_by_code: dict[str, dict[str, Any]] = {}
        self._dataset_by_id: dict[str, dict[str, Any]] = {}
        self._strategy_patterns: list[dict[str, Any]] = []

    def load(self) -> None:
        """Load all registry data."""
        self._load_amfi_census()
        self._load_amc_matrix()
        self._load_provider_profiles()
        self._build_indexes()

    def _load_amfi_census(self) -> None:
        if not self.amfi_census_path.exists():
            LOGGER.warning("AMFI census not found at %s", self.amfi_census_path)
            self._amfi_census = {"datasets": [], "extraction_strategies": {}, "global_settings": {}}
            return
        with open(self.amfi_census_path) as f:
            self._amfi_census = yaml.safe_load(f)

    def _load_amc_matrix(self) -> None:
        if not self.amc_matrix_path.exists():
            LOGGER.warning("AMC matrix not found at %s", self.amc_matrix_path)
            self._amc_matrix = {"amcs": [], "default_capabilities": {}, "strategy_patterns": [], "parser_registry": {}}
            return
        with open(self.amc_matrix_path) as f:
            self._amc_matrix = yaml.safe_load(f)

    def _load_provider_profiles(self) -> None:
        if not self.provider_profiles_path.exists():
            LOGGER.warning("Provider profiles not found at %s", self.provider_profiles_path)
            self._provider_profiles = []
            return
        with open(self.provider_profiles_path) as f:
            self._provider_profiles = json.load(f)

    def _build_indexes(self) -> None:
        # Index AMCs by name and code
        if self._amc_matrix and "amcs" in self._amc_matrix:
            for amc in self._amc_matrix["amcs"]:
                name = amc.get("amc_name", "").strip()
                code = amc.get("amc_code", "").strip()
                if name:
                    self._amc_by_name[name.lower()] = amc
                if code:
                    self._amc_by_code[code.lower()] = amc

        # Index datasets by ID
        if self._amfi_census and "datasets" in self._amfi_census:
            for ds in self._amfi_census["datasets"]:
                ds_id = ds.get("dataset_id", "")
                if ds_id:
                    self._dataset_by_id[ds_id] = ds

        # Load strategy patterns
        if self._amc_matrix and "strategy_patterns" in self._amc_matrix:
            self._strategy_patterns = self._amc_matrix["strategy_patterns"]

    # ============================================================
    # AMC LOOKUP
    # ============================================================

    def get_amc(self, name: str) -> dict[str, Any] | None:
        """Get AMC capability entry by name (case-insensitive)."""
        return self._amc_by_name.get(name.lower().strip())

    def get_amc_by_code(self, code: str) -> dict[str, Any] | None:
        """Get AMC capability entry by code (case-insensitive)."""
        return self._amc_by_code.get(code.lower().strip())

    def get_amc_capability(self, name: str, dataset_type: str) -> dict[str, Any] | None:
        """Get capability for a specific dataset type for an AMC."""
        amc = self.get_amc(name)
        if not amc:
            return None
        return amc.get("capabilities", {}).get(dataset_type)

    def get_all_amcs(self) -> list[dict[str, Any]]:
        """Get all AMC entries."""
        if self._amc_matrix and "amcs" in self._amc_matrix:
            return self._amc_matrix["amcs"]
        return []

    def get_working_amcs(self, dataset_type: str = "portfolio_disclosure") -> list[dict[str, Any]]:
        """Get AMCs with working capability for a dataset type."""
        working = []
        for amc in self.get_all_amcs():
            cap = amc.get("capabilities", {}).get(dataset_type, {})
            if cap.get("status") == "working":
                working.append(amc)
        return working

    def get_amcs_needing_browser(self, dataset_type: str = "portfolio_disclosure") -> list[dict[str, Any]]:
        """Get AMCs that need browser/VLM for a dataset type."""
        needing = []
        for amc in self.get_all_amcs():
            cap = amc.get("capabilities", {}).get(dataset_type, {})
            strategy = cap.get("strategy", "")
            if "playwright" in strategy.lower() or "vlm" in strategy.lower() or cap.get("status") == "needs_browser_vlm":
                needing.append(amc)
        return needing

    # ============================================================
    # DATASET LOOKUP
    # ============================================================

    def get_dataset(self, dataset_id: str) -> dict[str, Any] | None:
        """Get AMFI dataset census entry by ID."""
        return self._dataset_by_id.get(dataset_id)

    def get_datasets_by_category(self, category: str) -> list[dict[str, Any]]:
        """Get all datasets in a category (nav, portfolio, metadata, aum, etc.)."""
        if not self._amfi_census or "datasets" not in self._amfi_census:
            return []
        return [ds for ds in self._amfi_census["datasets"] if ds.get("category") == category]

    def get_primary_datasets(self) -> list[dict[str, Any]]:
        """Get all datasets marked as primary priority."""
        if not self._amfi_census or "datasets" not in self._amfi_census:
            return []
        return [ds for ds in self._amfi_census["datasets"] if ds.get("priority") == "primary"]

    def get_amfi_nav_datasets(self) -> list[dict[str, Any]]:
        """Get all NAV-related AMFI datasets."""
        return self.get_datasets_by_category("nav")

    def get_amfi_portfolio_datasets(self) -> list[dict[str, Any]]:
        """Get all portfolio-related AMFI datasets."""
        return self.get_datasets_by_category("portfolio")

    def get_amfi_metadata_datasets(self) -> list[dict[str, Any]]:
        """Get all metadata-related AMFI datasets."""
        return self.get_datasets_by_category("metadata")

    def get_amfi_aum_datasets(self) -> list[dict[str, Any]]:
        """Get all AUM-related AMFI datasets."""
        return self.get_datasets_by_category("aum")

    def get_amfi_industry_datasets(self) -> list[dict[str, Any]]:
        """Get all industry data AMFI datasets."""
        return self.get_datasets_by_category("industry_data")

    def get_amfi_ter_datasets(self) -> list[dict[str, Any]]:
        """Get all TER-related AMFI datasets."""
        return self.get_datasets_by_category("ter")

    # ============================================================
    # EXTRACTION STRATEGY
    # ============================================================

    def get_extraction_strategy(self, dataset_id: str) -> dict[str, Any] | None:
        """Get extraction strategy for a dataset."""
        if not self._amfi_census or "extraction_strategies" not in self._amfi_census:
            return None
        return self._amfi_census["extraction_strategies"].get(dataset_id)

    def get_strategy_pattern(self, pattern_id: str) -> dict[str, Any] | None:
        """Get strategy pattern by ID."""
        for pattern in self._strategy_patterns:
            if pattern.get("pattern_id") == pattern_id:
                return pattern
        return None

    def get_strategy_patterns_for_amc(self, amc_name: str) -> list[dict[str, Any]]:
        """Get applicable strategy patterns for an AMC based on its capabilities."""
        amc = self.get_amc(amc_name)
        if not amc:
            return []
        patterns = []
        for cap in amc.get("capabilities", {}).values():
            strategy = cap.get("strategy") or ""
            extractor = pattern.get("extractor") if (pattern := {}) else ""  # dummy to avoid scope issues
            for pattern in self._strategy_patterns:
                pattern_extractor = pattern.get("extractor") or ""
                pattern_desc = pattern.get("description") or ""
                if pattern_extractor in strategy or pattern_desc.lower() in strategy.lower():
                    if pattern not in patterns:
                        patterns.append(pattern)
        return patterns

    # ============================================================
    # PROVIDER PROFILES
    # ============================================================

    def get_provider_profile(self, amc_name: str) -> dict[str, Any] | None:
        """Get provider profile by AMC name."""
        if not self._provider_profiles:
            return None
        for profile in self._provider_profiles:
            if profile.get("amc_name", "").lower() == amc_name.lower():
                return profile
        return None

    def get_provider_strategy(self, amc_name: str) -> str | None:
        """Get detected strategy from provider profile."""
        profile = self.get_provider_profile(amc_name)
        if profile:
            return profile.get("detected_strategy")
        return None

    # ============================================================
    # PARSER REGISTRY
    # ============================================================

    def get_parser_registry(self) -> dict[str, Any]:
        """Get parser registry."""
        if self._amc_matrix and "parser_registry" in self._amc_matrix:
            return self._amc_matrix["parser_registry"]
        return {"implemented": [], "stubs_only": [], "needed": []}

    def get_implemented_parsers(self) -> list[dict[str, Any]]:
        """Get list of implemented parsers."""
        registry = self.get_parser_registry()
        return registry.get("implemented", [])

    def get_parser_for_dataset(self, dataset_type: str, file_format: str) -> dict[str, Any] | None:
        """Find parser for dataset type and format."""
        for parser in self.get_implemented_parsers():
            if dataset_type in parser.get("dataset_types", []) and file_format in parser.get("formats", []):
                return parser
        return None

    # ============================================================
    # GLOBAL SETTINGS
    # ============================================================

    def get_global_settings(self) -> dict[str, Any]:
        """Get global crawling settings."""
        if self._amfi_census and "global_settings" in self._amfi_census:
            return self._amfi_census["global_settings"]
        return {}

    def get_default_capabilities(self) -> dict[str, Any]:
        """Get default capabilities template."""
        if self._amc_matrix and "default_capabilities" in self._amc_matrix:
            return self._amc_matrix["default_capabilities"]
        return {}


# Singleton instance
_registry: SourceCapabilityRegistry | None = None


def get_registry(
    amfi_census_path: Path | str = DEFAULT_AMFI_CENSUS,
    amc_matrix_path: Path | str = DEFAULT_AMC_MATRIX,
    provider_profiles_path: Path | str = DEFAULT_PROVIDER_PROFILES,
) -> SourceCapabilityRegistry:
    """Get or create singleton registry instance."""
    global _registry
    if _registry is None:
        _registry = SourceCapabilityRegistry(amfi_census_path, amc_matrix_path, provider_profiles_path)
        _registry.load()
    return _registry


def reload_registry() -> SourceCapabilityRegistry:
    """Force reload of registry."""
    global _registry
    _registry = SourceCapabilityRegistry()
    _registry.load()
    return _registry