from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

# Lazy imports for agent module (requires psycopg2-binary and SQLAlchemy)
_agent_db = None
_agent_runner = None
_agent_config = None

def _get_agent_db():
    global _agent_db
    if _agent_db is None:
        from .agent.db import create_tables as _db_create_tables
        _agent_db = _db_create_tables
    return _agent_db

def _get_agent_runner():
    global _agent_runner
    if _agent_runner is None:
        from .agent.runner import IngestionRunner
        _agent_runner = IngestionRunner
    return _agent_runner

def _get_agent_config():
    global _agent_config
    if _agent_config is None:
        from .agent.config import AgentConfig as _ac
        _agent_config = _ac
    return _agent_config

from .artifacts import ArtifactPaths, load_latest_profiles, write_profile_artifacts
from .browser import render_reference_html
from .http import HttpSettings, build_session
from .profiler import ProfileContext, ProfileOptions, profile_sources
from .registry import DEFAULT_REGISTRY, load_registry, load_sources
from .reports import calculate_metrics, generate_profile_reports
from .models import SourceCandidate
from .source_discovery import (
    AMFI_MEMBERS_URL,
    SEBI_REGISTERED_FUNDS_URL,
    discover_amfi_candidates,
    discover_sebi_candidates,
)
from .source_registry import (
    SourceRegistryPaths,
    calculate_source_registry_metrics,
    candidates_from_registry,
    generate_source_registry_report,
    merge_source_candidates,
    write_source_registry_artifacts,
)


DEFAULT_OUTPUT_DIR = Path("data/raw/mutual_funds/provider_profiles")
DEFAULT_REPORT_DIR = Path("data/reports/mutual_funds")
DEFAULT_DEBUG_DIR = Path("data/debug/mutual_funds/provider_profiles")
DEFAULT_SOURCE_REGISTRY_DIR = Path("data/raw/mutual_funds/source_registry")


def _run_identity() -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    created_at = now.isoformat().replace("+00:00", "Z")
    digest = sha256(created_at.encode()).hexdigest()[:6]
    return now.strftime("%Y%m%d_%H%M%S_") + digest, created_at


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Phase 1 mutual fund source discovery and provider profiling.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common(command: argparse.ArgumentParser) -> None:
        command.add_argument("--config", "--registry", dest="config", type=Path, default=DEFAULT_REGISTRY)
        command.add_argument("--limit", type=int)
        command.add_argument("--amc")
        command.add_argument("--dry-run", action="store_true")
        command.add_argument("--log-level", default="INFO")
        command.add_argument("--timeout", type=float, default=30)
        command.add_argument("--no-browser", action="store_true")
        command.add_argument("--use-playwright", choices=("true", "false"))

    def add_bootstrap(command: argparse.ArgumentParser, *, include_report_dir: bool = True) -> None:
        command.add_argument("--source-registry-dir", type=Path, default=DEFAULT_SOURCE_REGISTRY_DIR)
        if include_report_dir:
            command.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
        command.add_argument("--no-reference-network", action="store_true")

    def add_profile(command: argparse.ArgumentParser) -> None:
        command.add_argument("--force", action="store_true")
        command.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
        command.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
        command.add_argument("--debug-dir", type=Path, default=DEFAULT_DEBUG_DIR)

    bootstrap = subparsers.add_parser("bootstrap-sources")
    add_common(bootstrap)
    add_bootstrap(bootstrap)
    for name in ("profile-providers", "profile-sites"):
        profile = subparsers.add_parser(name)
        add_common(profile)
        add_profile(profile)
    phase_1 = subparsers.add_parser("phase-1")
    add_common(phase_1)
    add_bootstrap(phase_1, include_report_dir=False)
    add_profile(phase_1)

    # Agent subcommands
    run_agent = subparsers.add_parser("run-agent")
    run_agent.add_argument("--task-url", action="append", dest="task_url", default=[], help="Task URL to process (can be repeated)")
    run_agent.add_argument("--task-url-file", type=Path, help="File with task URLs (one per line)")
    run_agent.add_argument("--database-url", required=True, help="PostgreSQL connection URL")
    run_agent.add_argument("--max-pages", type=int, default=500)
    run_agent.add_argument("--max-depth", type=int, default=5)
    run_agent.add_argument("--max-files", type=int, default=200)
    run_agent.add_argument("--max-runtime-minutes", type=int, default=60)
    run_agent.add_argument("--max-file-size-mb", type=float, default=50)
    run_agent.add_argument("--use-browser", action="store_true", default=False)
    run_agent.add_argument("--headless", action="store_true", default=True)
    run_agent.add_argument("--use-vlm", action="store_true", default=False)
    run_agent.add_argument("--vlm-endpoint", default="http://localhost:11434")
    run_agent.add_argument("--vlm-model")
    run_agent.add_argument("--vlm-confidence-threshold", type=float, default=0.7)
    run_agent.add_argument("--keep-raw-files", action="store_true", default=False)
    run_agent.add_argument("--keep-failed-raw-files", action="store_true", default=True)
    run_agent.add_argument("--max-retained-file-size-mb", type=float, default=50)
    run_agent.add_argument("--raw-dir", type=Path, default=Path("data/raw/mutual_funds/runtime"))
    run_agent.add_argument("--temp-dir", type=Path, default=Path("data/tmp/mutual_funds/runtime"))
    run_agent.add_argument("--log-level", default="INFO")
    run_agent.add_argument("--fail-fast", action="store_true", default=False)
    run_agent.add_argument("--dry-run", action="store_true", default=False)

    init_db = subparsers.add_parser("init-db")
    init_db.add_argument("--database-url", required=True)
    init_db.add_argument("--log-level", default="INFO")

    return parser


def _reference_candidates() -> list[SourceCandidate]:
    return [
        SourceCandidate(
            source_name="AMFI",
            seed_url="https://www.amfiindia.com/",
            source_role="reference_index",
            source_type="industry_reference_portal",
            expected_document_types=("scheme_metadata", "nav_reference", "disclosure_index"),
            discovered_from="manual_reference",
            confidence="high",
            priority="secondary",
            normalized_amc_name="amfi",
            notes="Use for source discovery and validation, not as the primary provider source.",
            access_notes="May require VPN depending on the execution environment.",
        ),
        SourceCandidate(
            source_name="SEBI",
            seed_url="https://www.sebi.gov.in/",
            source_role="reference_index",
            source_type="regulatory_reference_portal",
            expected_document_types=("scheme_metadata", "disclosure_index"),
            discovered_from="manual_reference",
            confidence="medium",
            priority="secondary",
            normalized_amc_name="sebi",
            notes="Corroborative regulatory reference; discovered material may be stale.",
        ),
    ]


def _bootstrap(args, session) -> tuple[list, list[str]]:
    existing = load_registry(args.config) if args.config.exists() else []
    candidates = candidates_from_registry(existing) + _reference_candidates()
    warnings: list[str] = []
    if not args.no_reference_network:
        browser_fetcher = None if args.no_browser or args.use_playwright == "false" else render_reference_html
        amfi, amfi_warnings = discover_amfi_candidates(
            session,
            AMFI_MEMBERS_URL,
            timeout_seconds=args.timeout,
            browser_fetcher=browser_fetcher,
        )
        sebi, sebi_warnings = discover_sebi_candidates(session, SEBI_REGISTERED_FUNDS_URL, timeout_seconds=args.timeout)
        candidates.extend(amfi)
        candidates.extend(sebi)
        warnings.extend(amfi_warnings)
        warnings.extend(sebi_warnings)
    entries, decisions = merge_source_candidates(candidates)
    paths = SourceRegistryPaths.from_roots(args.config, args.source_registry_dir, args.report_dir)
    if args.dry_run:
        print(
            json.dumps(
                {
                    "metrics": calculate_source_registry_metrics(entries, merge_count=len(decisions)),
                    "warnings": warnings,
                    "sources": [entry.to_dict() for entry in entries],
                },
                indent=2,
            )
        )
    else:
        write_source_registry_artifacts(candidates, entries, paths)
        generate_source_registry_report(entries, decisions, warnings, paths)
        logging.info("Bootstrapped %d sources; registry written to %s", len(entries), args.config)
    return entries, warnings


def _profile(args, session, sources=None) -> int:
    if sources is None:
        sources = load_sources(args.config, limit=args.limit, amc=args.amc)
    else:
        sources = [
            source
            for entry in sources
            if (source := entry.to_provider_source()) is not None
            and (args.amc is None or source.amc_name.casefold() == args.amc.casefold())
        ][: args.limit]
    paths = ArtifactPaths.from_roots(args.output_dir, args.report_dir, args.debug_dir)
    latest = load_latest_profiles(paths.latest)
    run_id, created_at = _run_identity()
    settings = HttpSettings(timeout_seconds=args.timeout)
    context = ProfileContext(
        run_id=run_id,
        created_at=created_at,
        debug_root=args.debug_dir,
        session=session,
        options=ProfileOptions(
            browser_enabled=not args.no_browser and args.use_playwright != "false",
            force=args.force,
            timeout_seconds=args.timeout,
            persist_debug=not args.dry_run,
        ),
        latest_profiles=latest,
    )
    profiles = profile_sources(sources, context)
    if args.dry_run:
        print(json.dumps({"metrics": calculate_metrics(profiles), "profiles": [item.to_dict() for item in profiles]}, indent=2))
        return 0
    write_profile_artifacts(profiles, paths)
    generate_profile_reports(profiles, paths)
    logging.info("Profiled %d providers; reports written to %s", len(profiles), args.report_dir)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level.upper()), format="%(asctime)s %(levelname)s %(message)s")
    settings = HttpSettings(timeout_seconds=getattr(args, 'timeout', 30))
    session = build_session(settings)
    if args.command == "bootstrap-sources":
        _bootstrap(args, session)
        return 0
    if args.command in {"profile-providers", "profile-sites"}:
        return _profile(args, session)
    if args.command == "phase-1":
        entries, _ = _bootstrap(args, session)
        return _profile(args, session, entries)
    if args.command == "init-db":
        try:
            _get_agent_db()(args.database_url)
            logging.info("Database schema created for: %s", args.database_url)
            return 0
        except Exception as exc:
            logging.error("DB init failed: %s", exc)
            return 1
    if args.command == "run-agent":
        task_urls = list(args.task_url)
        if args.task_url_file and args.task_url_file.exists():
            task_urls.extend(args.task_url_file.read_text().strip().splitlines())
        if not task_urls:
            logging.error("No task URLs provided. Use --task-url or --task-url-file.")
            return 1
        config = _get_agent_config()(
            task_urls=task_urls,
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
            raw_dir=args.raw_dir,
            temp_dir=args.temp_dir,
            log_level=args.log_level,
            fail_fast=args.fail_fast,
            dry_run=args.dry_run,
        )
        runner = _get_agent_runner()(config)
        result = runner.run()
        print(json.dumps(result, indent=2, default=str))
        return 0
    return 0
