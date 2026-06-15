"""Agent configuration."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AgentConfig:
    # Task URLs
    task_urls: list[str]
    # Database
    database_url: str
    # Discovery limits
    max_pages: int = 500
    max_depth: int = 5
    max_files: int = 200
    max_runtime_minutes: int = 60
    max_file_size_mb: float = 50
    # Browser
    use_browser: bool = True
    headless: bool = True
    # VLM
    use_vlm: bool = False
    vlm_endpoint: str = "http://localhost:11434"
    vlm_model: str | None = None
    vlm_confidence_threshold: float = 0.7
    # Storage
    keep_raw_files: bool = False
    keep_failed_raw_files: bool = True
    max_retained_file_size_mb: float = 50
    raw_dir: Path = Path("data/raw/mutual_funds/runtime")
    temp_dir: Path = Path("data/tmp/mutual_funds/runtime")
    # Operational
    log_level: str = "INFO"
    fail_fast: bool = False
    dry_run: bool = False
    # Dataset type priority
    dataset_type_priority: list[str] = field(
        default_factory=lambda: [
            "amc_provider_list",
            "scheme_master",
            "nav_history",
            "portfolio_disclosure",
            "factsheet",
        ]
    )

    @classmethod
    def from_args(cls, args: Any) -> "AgentConfig":
        return cls(
            task_urls=args.task_url,
            database_url=args.database_url,
            max_pages=args.max_pages,
            max_depth=args.max_depth,
            max_files=args.max_files,
            max_runtime_minutes=args.max_runtime_minutes,
            max_file_size_mb=args.max_file_size_mb,
            use_browser=args.use_browser,
            headless=args.headless,
            use_vlm=args.use_vlm,
            vlm_endpoint=args.vlm_endpoint,
            vlm_model=args.vlm_model,
            vlm_confidence_threshold=args.vlm_confidence_threshold,
            keep_raw_files=args.keep_raw_files,
            keep_failed_raw_files=args.keep_failed_raw_files,
            max_retained_file_size_mb=args.max_retained_file_size_mb,
            raw_dir=Path(args.raw_dir) if hasattr(args, "raw_dir") else cls.raw_dir,
            temp_dir=Path(args.temp_dir) if hasattr(args, "temp_dir") else cls.temp_dir,
            log_level=args.log_level,
            fail_fast=args.fail_fast,
            dry_run=args.dry_run,
            dataset_type_priority=args.dataset_type_priority if hasattr(args, "dataset_type_priority") else cls.dataset_type_priority,
        )
