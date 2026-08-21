"""Portfolio Ingestion Pipeline - Dedicated pipeline for portfolio disclosure data.

This is a separate pipeline from NAV ingestion, focused specifically on:
- Portfolio holdings from AMC provider websites (primary source)
- Multiple reporting frequencies (monthly, fortnightly, quarterly)
- ZIP file handling with multiple scheme files
- Scheme mapping and instrument resolution
- Gap detection and coverage monitoring
- Idempotent upserts with provenance
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from mutual_fund_ingestion.agent.db import (
    AMC,
    PortfolioSnapshot,
    PortfolioHolding,
    Scheme,
    Instrument,
    Document,
    RawArtifact,
    IngestionRun,
    DatasetCandidate,
    get_session_maker,
)
from mutual_fund_ingestion.agent.parser import parse_file
from mutual_fund_ingestion.agent.source_registry import get_registry
from mutual_fund_ingestion.agent.upserts import UpsertManager
from mutual_fund_ingestion.agent.artifact_processor import ArtifactProcessor
from mutual_fund_ingestion.agent.extract import ArtifactCollector
from utils.http import HttpSettings, build_session

LOGGER = logging.getLogger(__name__)


class PortfolioPipeline:
    """Dedicated pipeline for portfolio disclosure data ingestion."""

    def __init__(
        self,
        database_url: str,
        config: dict[str, Any] | None = None,
    ):
        self.database_url = database_url
        self.config = config or {}
        self.session_maker = get_session_maker(database_url)
        self.upsert_manager = UpsertManager()
        
        # Initialize artifact collector with required args
        http_settings = HttpSettings()
        http_session = build_session(http_settings)
        temp_dir = Path(self.config.get("temp_dir", "/tmp/mf_portfolio"))
        self.collector = ArtifactCollector(
            session=http_session,
            temp_dir=temp_dir,
            max_file_size_mb=self.config.get("max_file_size_mb", 50.0),
            keep_raw_files=self.config.get("keep_raw_files", False),
        )
        self.registry = get_registry()

    def run_backfill(
        self,
        amc_codes: list[str] | None = None,
        dataset_types: list[str] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        max_files_per_amc: int = 50,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        """Run historical portfolio backfill for specified AMCs.

        Args:
            amc_codes: List of AMC codes to process (default: all working AMCs)
            dataset_types: Types of portfolio disclosures (monthly, fortnightly, etc.)
            start_date: Start date for backfill
            end_date: End date for backfill
            max_files_per_amc: Max files to process per AMC
            run_id: Optional run ID for tracking

        Returns:
            Statistics dict
        """
        if run_id is None:
            run_id = str(uuid.uuid4())

        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=2 * 365)

        stats = {
            "run_id": run_id,
            "amcs_processed": 0,
            "files_downloaded": 0,
            "artifacts_parsed": 0,
            "rows_staged": 0,
            "records_upserted": 0,
            "errors": 0,
            "gaps_detected": 0,
        }

        LOGGER.info("Starting portfolio backfill for AMCs: %s", amc_codes)

        # Create ingestion run record
        session = self.session_maker()
        try:
            run = IngestionRun(
                id=uuid.UUID(run_id),
                started_at=datetime.now(timezone.utc),
                status="running",
                config_json={
                    "pipeline": "portfolio_backfill",
                    "amc_codes": amc_codes,
                    "dataset_types": dataset_types,
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None,
                    "max_files_per_amc": max_files_per_amc,
                },
            )
            session.add(run)
            session.commit()
        finally:
            session.close()

        # Determine which AMCs to process
        if amc_codes is None:
            amcs_to_process = self.registry.get_working_amcs("portfolio_disclosure")
        else:
            amcs_to_process = []
            for code in amc_codes:
                amc = self.registry.get_amc_by_code(code)
                if amc:
                    amcs_to_process.append(amc)
                else:
                    LOGGER.warning("AMC code not found: %s", code)

        for amc in amcs_to_process:
            amc_name = amc["amc_name"]
            amc_code = amc["amc_code"]

            try:
                amc_stats = self._ingest_amc_portfolios(
                    amc, start_date, end_date, max_files_per_amc, run_id
                )
                for k, v in amc_stats.items():
                    stats[k] = stats.get(k, 0) + v
                stats["amcs_processed"] += 1

            except Exception as e:
                LOGGER.error("Error ingesting portfolios for %s: %s", amc_name, e)
                stats["errors"] += 1

        # Update run record
        session = self.session_maker()
        try:
            run = session.query(IngestionRun).filter(IngestionRun.id == uuid.UUID(run_id)).first()
            if run:
                run.finished_at = datetime.now(timezone.utc)
                run.status = "completed" if stats["errors"] == 0 else "completed_with_errors"
                run.files_seen = stats["files_downloaded"]
                run.rows_inserted = stats["records_upserted"]
                run.rows_rejected = stats["errors"]
                run.error_summary = {"errors": stats["errors"]}
                session.commit()
        finally:
            session.close()

        # Update coverage metrics
        try:
            from mutual_fund_ingestion.agent.coverage import CoverageCalculator
            coverage_calc = CoverageCalculator(self.database_url)
            coverage_stats = coverage_calc.update_all_coverage()
            stats["coverage_update"] = coverage_stats
            LOGGER.info("Coverage updated: %s", coverage_stats)
        except Exception as e:
            LOGGER.warning("Failed to update coverage: %s", e)

        LOGGER.info("Portfolio backfill complete: %s", stats)
        return stats

    def _ingest_amc_portfolios(
        self,
        amc: dict[str, Any],
        start_date: date | None,
        end_date: date | None,
        max_files: int,
        run_id: str,
    ) -> dict[str, int]:
        """Ingest portfolio files for a single AMC."""
        stats = {"files_downloaded": 0, "artifacts_parsed": 0, "rows_staged": 0, "records_upserted": 0}

        amc_name = amc["amc_name"]
        capability = amc.get("capabilities", {}).get("portfolio_disclosure", {})
        strategy = capability.get("strategy", "unknown")
        seed_urls = capability.get("seed_urls", [])

        LOGGER.info("Processing %s with strategy %s", amc_name, strategy)

        # Get URLs based on strategy
        urls = self._discover_portfolio_urls(amc, capability, start_date, end_date)
        urls = urls[:max_files]

        LOGGER.info("Found %d portfolio URLs for %s", len(urls), amc_name)

        # Process each URL
        for i, url in enumerate(urls):
            try:
                LOGGER.info("Processing %d/%d: %s", i + 1, len(urls), url)
                file_stats = self._download_parse_upsert(url, amc_name, run_id)
                for k, v in file_stats.items():
                    stats[k] = stats.get(k, 0) + v
            except Exception as e:
                LOGGER.error("Failed to process %s: %s", url, e)
                stats["errors"] = stats.get("errors", 0) + 1

        return stats

    def _discover_portfolio_urls(
        self,
        amc: dict[str, Any],
        capability: dict[str, Any],
        start_date: date | None,
        end_date: date | None,
    ) -> list[str]:
        """Discover portfolio URLs for an AMC based on its capability."""
        strategy = capability.get("strategy", "unknown")
        seed_urls = capability.get("seed_urls", [])
        amc_name = amc["amc_name"]

        urls = []

        if strategy == "static_html":
            # Use static HTML discovery from seed URLs
            from mutual_fund_ingestion.agent.discovery import DiscoveryEngine
            from utils.http import HttpSettings, build_session

            settings = HttpSettings()
            session = build_session(settings)
            engine = DiscoveryEngine(session=session, settings=settings)

            for seed_url in seed_urls:
                try:
                    engine.add_urls([seed_url], None, 0)
                    
                    # Process the queue (single page for static_html)
                    while engine.url_queue:
                        url, parent, depth = engine.url_queue.popleft()
                        if url in engine.visited_urls:
                            continue
                        engine.visited_urls.add(url)

                        status_code, html = engine.fetch(url)
                        if html:
                            links = engine.extract_links(html, url)
                            for link in links:
                                score, hint = engine.score_relevance(link['url'], link.get('text', ''), link.get('title', ''))
                                if hint == "portfolio_disclosure":
                                    urls.append(link['url'])
                                # Also add to queue for deeper crawl if needed
                                if score > 0.5:
                                    engine.add_urls([link['url']], url, depth + 1)
                except Exception as e:
                    LOGGER.warning("Discovery failed for %s: %s", seed_url, e)

        elif strategy == "playwright":
            # Use Playwright-based discovery
            urls = self._discover_with_playwright(amc, capability)

        elif strategy == "playwright_vlm":
            # Use Playwright + VLM (ICICI Prudential style)
            urls = self._discover_with_playwright_vlm(amc, capability)

        else:
            LOGGER.warning("Unknown strategy %s for %s", strategy, amc_name)

        # Deduplicate
        return list(set(urls))

    def _discover_with_playwright(self, amc: dict[str, Any], capability: dict[str, Any]) -> list[str]:
        """Discover URLs using Playwright (for tabbed portals like Mirae, Invesco)."""
        # This would use the existing targeted_portfolio_ingestion.py logic
        # For now, return seed URLs as fallback
        return capability.get("seed_urls", [])

    def _discover_with_playwright_vlm(self, amc: dict[str, Any], capability: dict[str, Any]) -> list[str]:
        """Discover URLs using Playwright + VLM (for complex React apps like ICICI)."""
        # This would use icici_navigator.py logic
        # For now, return seed URLs as fallback
        return capability.get("seed_urls", [])

    def _download_parse_upsert(self, url: str, amc_name: str, run_id: str) -> dict[str, int]:
        """Download, parse, and upsert a single portfolio file."""
        stats = {"files_downloaded": 0, "artifacts_parsed": 0, "rows_staged": 0, "records_upserted": 0}

        try:
            # Use artifact processor with proper session
            session = self.session_maker()
            try:
                # Create a dataset candidate for this URL
                dataset_candidate = DatasetCandidate(
                    run_id=uuid.UUID(run_id),
                    url=url,
                    dataset_type="portfolio_disclosure",
                    file_type="xlsx",  # Will be determined from URL
                    status="discovered",
                )
                session.add(dataset_candidate)
                session.flush()

                processor = ArtifactProcessor(
                    run_id=run_id,
                    stats=stats,
                    collector=self.collector,
                    upsert_manager=self.upsert_manager,
                )
                processor.process(session, dataset_candidate)

                stats["files_downloaded"] = 1
                stats["artifacts_parsed"] = 1
                session.commit()
            finally:
                session.close()

        except Exception as e:
            LOGGER.error("Failed to download/parse/upsert %s: %s", url, e)
            stats["errors"] = stats.get("errors", 0) + 1

        return stats

    def run_incremental(
        self,
        days_back: int = 30,
        amc_codes: list[str] | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        """Run incremental portfolio update for recent reporting periods.

        Args:
            days_back: How many days back to check for new disclosures
            amc_codes: Optional AMC codes to filter
            run_id: Optional run ID

        Returns:
            Statistics dict
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days_back)

        return self.run_backfill(
            amc_codes=amc_codes,
            start_date=start_date,
            end_date=end_date,
            run_id=run_id,
        )

    def detect_gaps(
        self,
        amc_name: str | None = None,
        scheme_code: str | None = None,
        lookback_months: int = 24,
    ) -> list[dict[str, Any]]:
        """Detect missing portfolio reporting periods.

        Args:
            amc_name: Filter by AMC
            scheme_code: Filter by scheme
            lookback_months: How many months back to check

        Returns:
            List of gaps with scheme, expected_period, actual_periods
        """
        session = self.session_maker()
        try:
            query = session.query(PortfolioSnapshot)

            if scheme_code:
                query = query.join(Scheme).filter(Scheme.scheme_code == scheme_code)

            if amc_name:
                query = query.join(Scheme).join(AMC).filter(AMC.name == amc_name)

            cutoff = date.today() - timedelta(days=lookback_months * 30)
            query = query.filter(PortfolioSnapshot.reporting_date >= cutoff)

            snapshots = query.all()

            # Group by scheme
            from collections import defaultdict
            scheme_periods: dict[str, set[date]] = defaultdict(set)
            scheme_info: dict[str, dict] = {}

            for snap in snapshots:
                scheme_periods[str(snap.scheme_id)].add(snap.reporting_date)
                if snap.scheme_id not in scheme_info:
                    scheme_info[str(snap.scheme_id)] = {
                        "scheme_id": str(snap.scheme_id),
                        "scheme_code": snap.scheme.scheme_code if snap.scheme else None,
                        "scheme_name": snap.scheme.scheme_name if snap.scheme else None,
                        "amc_name": snap.scheme.amc.name if snap.scheme and snap.scheme.amc else None,
                    }

            # Find gaps - expected monthly/fortnightly periods
            gaps = []
            for scheme_id, periods in scheme_periods.items():
                if not periods:
                    continue

                info = scheme_info[scheme_id]
                min_period = min(periods)
                max_period = max(periods)

                # Generate expected monthly periods
                expected = set()
                current = date(min_period.year, min_period.month, 1)
                while current <= max_period:
                    expected.add(current)
                    # Next month
                    if current.month == 12:
                        current = date(current.year + 1, 1, 1)
                    else:
                        current = date(current.year, current.month + 1, 1)

                missing = expected - periods
                if missing:
                    gaps.append({
                        "scheme_id": str(scheme_id),
                        "scheme_code": info["scheme_code"],
                        "scheme_name": info["scheme_name"],
                        "amc_name": info["amc_name"],
                        "missing_count": len(missing),
                        "missing_periods": sorted([d.isoformat() for d in missing]),
                        "expected_range": f"{min_period} to {max_period}",
                        "captured_periods": len(periods),
                        "coverage_pct": round(len(periods) / len(expected) * 100, 1) if expected else 0,
                    })

            return sorted(gaps, key=lambda x: x["missing_count"], reverse=True)

        finally:
            session.close()

    def get_coverage_report(
        self,
        amc_name: str | None = None,
        scheme_code: str | None = None,
    ) -> dict[str, Any]:
        """Generate portfolio coverage report."""
        session = self.session_maker()
        try:
            query = session.query(PortfolioSnapshot)

            if scheme_code:
                query = query.join(Scheme).filter(Scheme.scheme_code == scheme_code)

            if amc_name:
                query = query.join(Scheme).join(AMC).filter(AMC.name == amc_name)

            snapshots = query.all()

            if not snapshots:
                return {"total_snapshots": 0, "schemes": 0, "amcs": 0, "coverage": {}}

            from collections import defaultdict
            amc_data: dict[str, dict] = defaultdict(lambda: {"schemes": set(), "snapshots": 0, "holdings": 0})
            scheme_data: dict[str, dict] = defaultdict(lambda: {"periods": set(), "holdings": 0})

            for snap in snapshots:
                amc = snap.scheme.amc if snap.scheme else None
                amc_n = amc.name if amc else "Unknown"
                amc_data[amc_n]["schemes"].add(snap.scheme_id)
                amc_data[amc_n]["snapshots"] += 1
                amc_data[amc_n]["holdings"] += len(snap.holdings) if snap.holdings else 0

                scheme_data[str(snap.scheme_id)]["periods"].add(snap.reporting_date)
                scheme_data[str(snap.scheme_id)]["holdings"] += len(snap.holdings) if snap.holdings else 0

            report = {
                "total_snapshots": len(snapshots),
                "total_holdings": sum(len(s.holdings) for s in snapshots if s.holdings),
                "schemes_covered": len(scheme_data),
                "amcs_covered": len(amc_data),
                "by_amc": {},
                "by_scheme": {},
            }

            for amc_n, data in amc_data.items():
                report["by_amc"][amc_n] = {
                    "schemes": len(data["schemes"]),
                    "snapshots": data["snapshots"],
                    "holdings": data["holdings"],
                }

            for scheme_id, data in scheme_data.items():
                periods = data["periods"]
                min_p = min(periods)
                max_p = max(periods)
                expected = 0
                current = date(min_p.year, min_p.month, 1)
                while current <= max_p:
                    expected += 1
                    if current.month == 12:
                        current = date(current.year + 1, 1, 1)
                    else:
                        current = date(current.year, current.month + 1, 1)

                scheme = session.query(Scheme).filter(Scheme.id == uuid.UUID(scheme_id)).first()
                report["by_scheme"][scheme_id] = {
                    "scheme_name": scheme.scheme_name if scheme else "Unknown",
                    "amc_name": scheme.amc.name if scheme and scheme.amc else "Unknown",
                    "periods_captured": len(periods),
                    "expected_monthly_periods": expected,
                    "coverage_pct": round(len(periods) / expected * 100, 1) if expected else 0,
                    "holdings": data["holdings"],
                }

            return report

        finally:
            session.close()