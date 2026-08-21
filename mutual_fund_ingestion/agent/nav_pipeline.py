"""NAV Ingestion Pipeline - Dedicated pipeline for NAV data.

This is a separate pipeline from portfolio ingestion, focused specifically on:
- Daily NAV history from AMFI (primary source)
- NAV from AMC websites (secondary/corroborative)
- Scheme code / ISIN mapping
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
    NAVHistory,
    Scheme,
    RawArtifact,
    IngestionRun,
    get_session_maker,
)
from mutual_fund_ingestion.agent.parser import parse_file
from mutual_fund_ingestion.agent.source_registry import get_registry
from mutual_fund_ingestion.agent.upserts import UpsertManager
from utils.http import HttpSettings, build_session

LOGGER = logging.getLogger(__name__)


class NAVPipeline:
    """Dedicated pipeline for NAV data ingestion."""

    def __init__(
        self,
        database_url: str,
        config: dict[str, Any] | None = None,
    ):
        self.database_url = database_url
        self.config = config or {}
        self.session_maker = get_session_maker(database_url)
        self.upsert_manager = UpsertManager()
        self.registry = get_registry()
        self.http_settings = HttpSettings()
        self.session = build_session(self.http_settings)

    def run_backfill(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        amc_filter: list[str] | None = None,
        max_days_per_request: int = 90,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        """Run historical NAV backfill.

        Args:
            start_date: Start date for backfill (default: 5 years ago)
            end_date: End date for backfill (default: today)
            amc_filter: Optional list of AMC codes to filter
            max_days_per_request: Max days per AMFI request (default 90)
            run_id: Optional run ID for tracking

        Returns:
            Statistics dict
        """
        if run_id is None:
            run_id = str(uuid.uuid4())

        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=5 * 365)

        stats = {
            "run_id": run_id,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "requests_made": 0,
            "files_downloaded": 0,
            "records_parsed": 0,
            "records_upserted": 0,
            "errors": 0,
            "gaps_detected": 0,
        }

        LOGGER.info("Starting NAV backfill from %s to %s", start_date, end_date)

        # Create ingestion run record
        session = self.session_maker()
        try:
            run = IngestionRun(
                id=uuid.UUID(run_id),
                started_at=datetime.now(timezone.utc),
                status="running",
                config_json={
                    "pipeline": "nav_backfill",
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "amc_filter": amc_filter,
                },
            )
            session.add(run)
            session.commit()
        finally:
            session.close()

        # Get NAV dataset config
        nav_dataset = self.registry.get_dataset("nav_history")
        if not nav_dataset:
            LOGGER.error("NAV dataset config not found in registry")
            return stats

        # Iterate date ranges in 90-day windows
        current_start = start_date
        while current_start <= end_date:
            current_end = min(current_start + timedelta(days=max_days_per_request - 1), end_date)

            try:
                window_stats = self._fetch_nav_window(
                    current_start, current_end, amc_filter, run_id
                )
                for k, v in window_stats.items():
                    stats[k] = stats.get(k, 0) + v

                stats["requests_made"] += 1

            except Exception as e:
                LOGGER.error("Error fetching NAV window %s-%s: %s", current_start, current_end, e)
                stats["errors"] += 1

            current_start = current_end + timedelta(days=1)

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

        LOGGER.info("NAV backfill complete: %s", stats)
        return stats

    def _fetch_nav_window(
            self,
            start_date: date,
            end_date: date,
            amc_filter: list[str] | None,
            run_id: str,
        ) -> dict[str, int]:
            """Fetch NAV for a single date window."""
            stats = {"files_downloaded": 0, "records_parsed": 0, "records_upserted": 0}

            # AMFI provides full current NAV data via direct URLs
            # We'll use the direct download and filter by date
            nav_urls = [
                "https://portal.amfiindia.com/spages/NAVAll.txt",  # Complete NAV
                "https://portal.amfiindia.com/spages/NAVOpen.txt",  # Open Ended
                "https://portal.amfiindia.com/spages/NAVClose.txt",  # Close Ended
                "https://portal.amfiindia.com/spages/NAVInterval.txt",  # Interval Fund
            ]

            LOGGER.info("Fetching NAV from AMFI direct URLs")

            for url in nav_urls:
                try:
                    LOGGER.info("Downloading %s", url)
                    resp = self.session.get(url, timeout=60)
                    resp.raise_for_status()

                    content = resp.content
                    content_type = resp.headers.get("Content-Type", "")

                    stats["files_downloaded"] += 1

                    # Parse
                    metadata = {
                        "source_url": url,
                        "run_id": run_id,
                        "date_range": f"{start_date} to {end_date}",
                    }
                    result = parse_file("nav_history", "text", content, metadata)

                    stats["records_parsed"] += len(result.records)

                    if result.records:
                        # Filter records by date range
                        filtered_records = []
                        for record in result.records:
                            nav_date = date.fromisoformat(record["nav_date"])
                            if start_date <= nav_date <= end_date:
                                filtered_records.append(record)

                        LOGGER.info("Filtered to %d records in date range %s to %s", len(filtered_records), start_date, end_date)

                        if filtered_records:
                            # Upsert
                            session = self.session_maker()
                            try:
                                from mutual_fund_ingestion.agent.db import RawArtifact

                                import hashlib
                                checksum = hashlib.sha256(content).hexdigest()
                                raw_artifact = RawArtifact(
                                    run_id=uuid.UUID(run_id),
                                    source_url=url,
                                    artifact_type="file",
                                    file_type="text",
                                    content_type=content_type,
                                    size_bytes=len(content),
                                    checksum=checksum,
                                )
                                session.add(raw_artifact)
                                session.flush()

                                self.upsert_manager.upsert_canonical(
                                    session,
                                    filtered_records,
                                    "nav_history",
                                    raw_artifact.id,  # type: ignore[arg-type]
                                    url,
                                    stats,
                                )
                                session.commit()
                            finally:
                                session.close()

                except Exception as e:
                    LOGGER.error("Failed to fetch NAV from %s: %s", url, e)
                    stats["errors"] = stats.get("errors", 0) + 1

            return stats

    def run_incremental(
        self,
        days_back: int = 2,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        """Run incremental NAV update for recent days.

        Args:
            days_back: How many days back to fetch (default 2 for weekend coverage)
            run_id: Optional run ID

        Returns:
            Statistics dict
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days_back)

        return self.run_backfill(start_date=start_date, end_date=end_date, run_id=run_id)

    def detect_gaps(
        self,
        scheme_code: str | None = None,
        amc_name: str | None = None,
        lookback_days: int = 365,
    ) -> list[dict[str, Any]]:
        """Detect missing NAV dates for schemes.

        Args:
            scheme_code: Specific scheme to check (optional)
            amc_name: Filter by AMC (optional)
            lookback_days: How far back to check

        Returns:
            List of gaps with scheme_code, expected_date, actual_dates
        """
        session = self.session_maker()
        try:
            query = session.query(NAVHistory)
            if scheme_code:
                query = query.filter(NAVHistory.scheme_code == scheme_code)

            cutoff = date.today() - timedelta(days=lookback_days)
            query = query.filter(NAVHistory.nav_date >= cutoff)

            records = query.all()

            # Group by scheme
            from collections import defaultdict
            scheme_dates: dict[str, set[date]] = defaultdict(set)
            for r in records:
                scheme_dates[r.scheme_code].add(r.nav_date)

            # Find gaps (business days without NAV)
            gaps = []
            for code, dates in scheme_dates.items():
                if not dates:
                    continue
                min_date = min(dates)
                max_date = max(dates)
                expected = set()
                current = min_date
                while current <= max_date:
                    if current.weekday() < 5:  # Business days only
                        expected.add(current)
                    current += timedelta(days=1)

                missing = expected - dates
                if missing:
                    gaps.append({
                        "scheme_code": code,
                        "missing_count": len(missing),
                        "missing_dates": sorted([d.isoformat() for d in missing]),
                        "expected_range": f"{min_date} to {max_date}",
                        "coverage_pct": round(len(dates) / len(expected) * 100, 1) if expected else 0,
                    })

            return sorted(gaps, key=lambda x: x["missing_count"], reverse=True)

        finally:
            session.close()

    def get_coverage_report(
        self,
        amc_name: str | None = None,
        scheme_code: str | None = None,
    ) -> dict[str, Any]:
        """Generate NAV coverage report."""
        session = self.session_maker()
        try:
            query = session.query(NAVHistory)

            if scheme_code:
                query = query.filter(NAVHistory.scheme_code == scheme_code)

            records = query.all()

            if not records:
                return {"total_records": 0, "schemes": 0, "date_range": None, "coverage": {}}

            from collections import defaultdict
            scheme_data: dict[str, dict] = defaultdict(lambda: {"dates": set(), "amc": None})

            for r in records:
                scheme_data[r.scheme_code]["dates"].add(r.nav_date)

            # Get scheme info
            schemes = session.query(Scheme).all()
            scheme_map = {s.scheme_code: s for s in schemes if s.scheme_code}

            report = {
                "total_records": len(records),
                "schemes_covered": len(scheme_data),
                "date_range": {
                    "earliest": min(min(d["dates"]) for d in scheme_data.values()).isoformat(),
                    "latest": max(max(d["dates"]) for d in scheme_data.values()).isoformat(),
                },
                "by_scheme": {},
            }

            for code, data in scheme_data.items():
                scheme = scheme_map.get(code)
                dates = data["dates"]
                min_d = min(dates)
                max_d = max(dates)
                expected_days = sum(1 for d in (min_d + timedelta(i) for i in range((max_d - min_d).days + 1)) if d.weekday() < 5)
                report["by_scheme"][code] = {
                    "scheme_name": scheme.scheme_name if scheme else "Unknown",
                    "amc_name": scheme.amc.name if scheme and scheme.amc else "Unknown",
                    "record_count": len(dates),
                    "date_range": f"{min_d} to {max_d}",
                    "expected_business_days": expected_days,
                    "coverage_pct": round(len(dates) / expected_days * 100, 1) if expected_days else 0,
                }

            return report

        finally:
            session.close()