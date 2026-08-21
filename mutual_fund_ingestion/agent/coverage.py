"""Coverage and Completeness Monitoring - Database models and queries for data quality tracking.

This module provides:
1. Coverage tables for NAV and Portfolio data
2. Gap detection and reporting
3. Completeness metrics at multiple granularities
4. Automated alerts for missing data
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    Text,
    UUID,
    UniqueConstraint,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from mutual_fund_ingestion.agent.db import (
    Base,
    AMC,
    AMCoverage,
    CoverageAlert,
    CoverageSnapshot,
    DatasetCoverage,
    IngestionQualityMetrics,
    NAVHistory,
    PortfolioSnapshot,
    Scheme,
    SchemeCoverage,
    get_session_maker,
)

LOGGER = logging.getLogger(__name__)


def create_coverage_tables(database_url: str) -> None:
    """Create coverage tables in database."""
    from sqlalchemy import create_engine
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)


class CoverageCalculator:
    """Calculates and updates coverage metrics."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.session_maker = get_session_maker(database_url)

    def calculate_nav_coverage(self, session: Session, scheme_id: uuid.UUID | None = None) -> dict[str, Any]:
        """Calculate NAV coverage for a scheme or all schemes."""

        query = session.query(NAVHistory)
        if scheme_id:
            query = query.filter(NAVHistory.scheme_id == scheme_id)

        records = query.all()

        if not records:
            return {
                "scheme_id": str(scheme_id) if scheme_id else None,
                "expected": 0,
                "stored": 0,
                "missing": 0,
                "coverage_pct": 0.0,
                "gaps": [],
            }

        # Group by scheme
        from collections import defaultdict
        scheme_data: dict[uuid.UUID, dict] = defaultdict(lambda: {"dates": set(), "scheme_code": None})

        for r in records:
            sid = getattr(r, 'scheme_id', None)
            if sid:
                scheme_data[sid]["dates"].add(r.nav_date)
                if not scheme_data[sid]["scheme_code"]:
                    scheme_data[sid]["scheme_code"] = r.scheme_code

        results = []
        for sid, data in scheme_data.items():
            dates = data["dates"]
            min_d = min(dates)
            max_d = max(dates)

            # Calculate expected business days
            expected = 0
            current = min_d
            while current <= max_d:
                if current.weekday() < 5:
                    expected += 1
                current += timedelta(days=1)

            missing = expected - len(dates)
            coverage = round(len(dates) / expected * 100, 1) if expected else 0

            # Find missing dates
            missing_dates = []
            current = min_d
            while current <= max_d:
                if current.weekday() < 5 and current not in dates:
                    missing_dates.append(current.isoformat())
                current += timedelta(days=1)

            scheme = session.get(Scheme, sid)
            results.append({
                "scheme_id": str(sid),
                "scheme_code": data["scheme_code"],
                "scheme_name": scheme.scheme_name if scheme else "Unknown",
                "expected": expected,
                "stored": len(dates),
                "missing": missing,
                "coverage_pct": coverage,
                "earliest": min_d.isoformat(),
                "latest": max_d.isoformat(),
                "missing_dates": missing_dates[:50],  # Limit for storage
            })

        return results if not scheme_id else results[0]

    def calculate_portfolio_coverage(self, session: Session, scheme_id: uuid.UUID | None = None) -> dict[str, Any]:
        """Calculate portfolio disclosure coverage for a scheme."""

        query = session.query(PortfolioSnapshot)
        if scheme_id:
            query = query.filter(PortfolioSnapshot.scheme_id == scheme_id)

        snapshots = query.all()

        if not snapshots:
            return {
                "scheme_id": str(scheme_id) if scheme_id else None,
                "expected": 0,
                "stored": 0,
                "missing": 0,
                "coverage_pct": 0.0,
                "gaps": [],
            }

        from collections import defaultdict
        scheme_data: dict[str, dict] = defaultdict(lambda: {"periods": set()})

        for snap in snapshots:
            sid = str(getattr(snap, 'scheme_id', ''))
            if sid:
                scheme_data[sid]["periods"].add(snap.reporting_date)

        results = []
        for sid, data in scheme_data.items():
            periods = data["periods"]
            min_p = min(periods)
            max_p = max(periods)

            # Expected monthly periods
            expected = 0
            current = date(min_p.year, min_p.month, 1)
            while current <= max_p:
                expected += 1
                if current.month == 12:
                    current = date(current.year + 1, 1, 1)
                else:
                    current = date(current.year, current.month + 1, 1)

            missing = expected - len(periods)
            coverage = round(len(periods) / expected * 100, 1) if expected else 0

            missing_periods = []
            current = date(min_p.year, min_p.month, 1)
            while current <= max_p:
                if current not in periods:
                    missing_periods.append(current.isoformat())
                if current.month == 12:
                    current = date(current.year + 1, 1, 1)
                else:
                    current = date(current.year, current.month + 1, 1)

            scheme = session.get(Scheme, uuid.UUID(sid))
            results.append({
                "scheme_id": sid,
                "scheme_name": scheme.scheme_name if scheme else "Unknown",
                "expected": expected,
                "stored": len(periods),
                "missing": missing,
                "coverage_pct": coverage,
                "earliest": min_p.isoformat(),
                "latest": max_p.isoformat(),
                "missing_periods": missing_periods[:50],
            })

        return results if not scheme_id else results[0]

    def update_all_coverage(self) -> dict[str, Any]:
        """Recalculate all coverage metrics."""
        session = self.session_maker()
        stats = {"nav_schemes": 0, "portfolio_schemes": 0, "alerts_created": 0}

        try:
            # Nav coverage
            nav_results = self.calculate_nav_coverage(session)
            for r in nav_results:
                self._upsert_scheme_coverage(session, r, "nav_history")
                stats["nav_schemes"] += 1

            # Portfolio coverage
            portfolio_results = self.calculate_portfolio_coverage(session)
            for r in portfolio_results:
                self._upsert_scheme_coverage(session, r, "portfolio_disclosure")
                stats["portfolio_schemes"] += 1

            # Aggregate to AMC level
            self._aggregate_amc_coverage(session)
            self._aggregate_dataset_coverage(session)

            # Generate alerts
            stats["alerts_created"] = self._generate_alerts(session)

            session.commit()
        except Exception as e:
            LOGGER.error("Coverage update failed: %s", e)
            session.rollback()
        finally:
            session.close()

        return stats

    def _upsert_scheme_coverage(self, session: Session, data: dict[str, Any], dataset_type: str) -> None:
        """Upsert scheme coverage record."""
        scheme_id = uuid.UUID(data["scheme_id"])

        # Check if exists
        existing = session.query(SchemeCoverage).filter(
            SchemeCoverage.scheme_id == scheme_id,
            SchemeCoverage.dataset_type == dataset_type,
        ).first()

        if existing:
            existing.earliest_stored_date = date.fromisoformat(data["earliest"])
            existing.latest_stored_date = date.fromisoformat(data["latest"])
            existing.expected_observations = data["expected"]
            existing.stored_observations = data["stored"]
            existing.missing_observations = data["missing"]
            existing.coverage_pct = data["coverage_pct"]
            existing.missing_periods_json = data.get("missing_dates") or data.get("missing_periods") or []
            existing.last_gap_check = datetime.now(timezone.utc)
            existing.status = "active" if data["stored"] > 0 else "missing"
        else:
            new = SchemeCoverage(
                scheme_id=scheme_id,
                dataset_type=dataset_type,
                earliest_stored_date=date.fromisoformat(data["earliest"]),
                latest_stored_date=date.fromisoformat(data["latest"]),
                expected_observations=data["expected"],
                stored_observations=data["stored"],
                missing_observations=data["missing"],
                coverage_pct=data["coverage_pct"],
                missing_periods_json=data.get("missing_dates") or data.get("missing_periods") or [],
                last_gap_check=datetime.now(timezone.utc),
                status="active" if data["stored"] > 0 else "missing",
            )
            session.add(new)

    def _aggregate_amc_coverage(self, session: Session) -> None:
        """Aggregate scheme coverage to AMC level."""
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        for dataset_type in ["nav_history", "portfolio_disclosure"]:
            schemes = session.query(Scheme).join(AMC).filter(Scheme.amc_id.isnot(None)).all()

            amc_groups: dict[uuid.UUID, dict] = {}
            for scheme in schemes:
                amc_id = scheme.amc_id
                if amc_id not in amc_groups:
                    amc_groups[amc_id] = {
                        "schemes": 0,
                        "with_data": 0,
                        "total_expected": 0,
                        "total_stored": 0,
                        "earliest": None,
                        "latest": None,
                    }
                group = amc_groups[amc_id]
                group["schemes"] += 1

                sc = session.query(SchemeCoverage).filter(
                    SchemeCoverage.scheme_id == scheme.id,
                    SchemeCoverage.dataset_type == dataset_type,
                ).first()

                if sc and sc.stored_observations > 0:
                    group["with_data"] += 1
                    group["total_expected"] += sc.expected_observations
                    group["total_stored"] += sc.stored_observations
                    if sc.earliest_stored_date:
                        if not group["earliest"] or sc.earliest_stored_date < group["earliest"]:
                            group["earliest"] = sc.earliest_stored_date
                    if sc.latest_stored_date:
                        if not group["latest"] or sc.latest_stored_date > group["latest"]:
                            group["latest"] = sc.latest_stored_date

            for amc_id, group in amc_groups.items():
                total_missing = group["total_expected"] - group["total_stored"]
                coverage = round(group["total_stored"] / group["total_expected"] * 100, 1) if group["total_expected"] else 0

                stmt = pg_insert(AMCoverage).values(
                    amc_id=amc_id,
                    dataset_type=dataset_type,
                    total_schemes=group["schemes"],
                    schemes_with_data=group["with_data"],
                    total_expected=group["total_expected"],
                    total_stored=group["total_stored"],
                    total_missing=total_missing,
                    coverage_pct=coverage,
                    earliest_date=group["earliest"],
                    latest_date=group["latest"],
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["amc_id", "dataset_type"],
                    set_={
                        "total_schemes": stmt.excluded.total_schemes,
                        "schemes_with_data": stmt.excluded.schemes_with_data,
                        "total_expected": stmt.excluded.total_expected,
                        "total_stored": stmt.excluded.total_stored,
                        "total_missing": stmt.excluded.total_missing,
                        "coverage_pct": stmt.excluded.coverage_pct,
                        "earliest_date": stmt.excluded.earliest_date,
                        "latest_date": stmt.excluded.latest_date,
                    },
                )
                session.execute(stmt)

    def _aggregate_dataset_coverage(self, session: Session) -> None:
        """Aggregate to dataset level."""
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        for dataset_type in ["nav_history", "portfolio_disclosure"]:
            amc_covs = session.query(AMCoverage).filter(AMCoverage.dataset_type == dataset_type).all()

            total_amcs = len(amc_covs)
            total_schemes = sum(c.total_schemes for c in amc_covs)
            total_expected = sum(c.total_expected for c in amc_covs)
            total_stored = sum(c.total_stored for c in amc_covs)
            total_missing = total_expected - total_stored
            coverage = round(total_stored / total_expected * 100, 1) if total_expected else 0

            amcs_complete = sum(1 for c in amc_covs if c.coverage_pct == 100)
            amcs_partial = sum(1 for c in amc_covs if 50 <= c.coverage_pct < 100)
            amcs_minimal = sum(1 for c in amc_covs if 0 < c.coverage_pct < 50)
            amcs_empty = sum(1 for c in amc_covs if c.coverage_pct == 0)

            earliest = min((c.earliest_date for c in amc_covs if c.earliest_date), default=None)
            latest = max((c.latest_date for c in amc_covs if c.latest_date), default=None)

            stmt = pg_insert(DatasetCoverage).values(
                dataset_type=dataset_type,
                total_amcs=total_amcs,
                total_schemes=total_schemes,
                total_expected=total_expected,
                total_stored=total_stored,
                total_missing=total_missing,
                coverage_pct=coverage,
                global_earliest=earliest,
                global_latest=latest,
                amcs_complete=amcs_complete,
                amcs_partial=amcs_partial,
                amcs_minimal=amcs_minimal,
                amcs_empty=amcs_empty,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["dataset_type"],
                set_={
                    "total_amcs": stmt.excluded.total_amcs,
                    "total_schemes": stmt.excluded.total_schemes,
                    "total_expected": stmt.excluded.total_expected,
                    "total_stored": stmt.excluded.total_stored,
                    "total_missing": stmt.excluded.total_missing,
                    "coverage_pct": stmt.excluded.coverage_pct,
                    "global_earliest": stmt.excluded.global_earliest,
                    "global_latest": stmt.excluded.global_latest,
                    "amcs_complete": stmt.excluded.amcs_complete,
                    "amcs_partial": stmt.excluded.amcs_partial,
                    "amcs_minimal": stmt.excluded.amcs_minimal,
                    "amcs_empty": stmt.excluded.amcs_empty,
                },
            )
            session.execute(stmt)

    def _generate_alerts(self, session: Session) -> int:
        """Generate alerts for coverage issues."""
        alerts_created = 0

        # Alert for schemes with < 50% coverage
        low_coverage = session.query(SchemeCoverage).filter(
            SchemeCoverage.coverage_pct < 50,
            SchemeCoverage.stored_observations > 0,
        ).all()

        for sc in low_coverage:
            existing = session.query(CoverageAlert).filter(
                CoverageAlert.scheme_id == sc.scheme_id,
                CoverageAlert.dataset_type == sc.dataset_type,
                CoverageAlert.alert_type == "low_coverage",
                CoverageAlert.status == "open",
            ).first()

            if not existing:
                scheme = session.get(Scheme, sc.scheme_id)
                alert = CoverageAlert(
                    alert_type="low_coverage",
                    severity="warning" if sc.coverage_pct >= 25 else "critical",
                    dataset_type=sc.dataset_type,
                    scheme_id=sc.scheme_id,
                    amc_id=scheme.amc_id if scheme else None,
                    message=f"Scheme {scheme.scheme_name if scheme else sc.scheme_id} has only {sc.coverage_pct}% coverage for {sc.dataset_type}",
                    details_json={
                        "coverage_pct": sc.coverage_pct,
                        "expected": sc.expected_observations,
                        "stored": sc.stored_observations,
                        "missing": sc.missing_observations,
                    },
                )
                session.add(alert)
                alerts_created += 1

        # Alert for completely missing schemes
        missing = session.query(SchemeCoverage).filter(
            SchemeCoverage.stored_observations == 0,
            SchemeCoverage.status == "missing",
        ).all()

        for sc in missing:
            existing = session.query(CoverageAlert).filter(
                CoverageAlert.scheme_id == sc.scheme_id,
                CoverageAlert.dataset_type == sc.dataset_type,
                CoverageAlert.alert_type == "no_data",
                CoverageAlert.status == "open",
            ).first()

            if not existing:
                scheme = session.get(Scheme, sc.scheme_id)
                alert = CoverageAlert(
                    alert_type="no_data",
                    severity="critical",
                    dataset_type=sc.dataset_type,
                    scheme_id=sc.scheme_id,
                    amc_id=scheme.amc_id if scheme else None,
                    message=f"Scheme {scheme.scheme_name if scheme else sc.scheme_id} has no data for {sc.dataset_type}",
                    details_json={"expected": sc.expected_observations},
                )
                session.add(alert)
                alerts_created += 1

        return alerts_created


def get_coverage_report(database_url: str, dataset_type: str | None = None) -> dict[str, Any]:
    """Get comprehensive coverage report."""
    session = get_session_maker(database_url)()
    try:
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "datasets": {},
        }

        dataset_types = [dataset_type] if dataset_type else ["nav_history", "portfolio_disclosure"]

        for dt in dataset_types:
            # Dataset level
            entry: dict[str, Any] = {}
            ds_cov = session.query(DatasetCoverage).filter(DatasetCoverage.dataset_type == dt).first()
            if ds_cov:
                entry.update({
                    "total_amcs": ds_cov.total_amcs,
                    "total_schemes": ds_cov.total_schemes,
                    "total_expected": ds_cov.total_expected,
                    "total_stored": ds_cov.total_stored,
                    "total_missing": ds_cov.total_missing,
                    "coverage_pct": ds_cov.coverage_pct,
                    "global_earliest": ds_cov.global_earliest.isoformat() if ds_cov.global_earliest else None,
                    "global_latest": ds_cov.global_latest.isoformat() if ds_cov.global_latest else None,
                    "amcs_complete": ds_cov.amcs_complete,
                    "amcs_partial": ds_cov.amcs_partial,
                    "amcs_minimal": ds_cov.amcs_minimal,
                    "amcs_empty": ds_cov.amcs_empty,
                })

            # AMC level
            amc_covs = session.query(AMCoverage).filter(AMCoverage.dataset_type == dt).all()
            entry["by_amc"] = {}
            for amc_cov in amc_covs:
                amc = session.get(AMC, amc_cov.amc_id)
                entry["by_amc"][str(amc_cov.amc_id)] = {
                    "amc_name": amc.name if amc else "Unknown",
                    "total_schemes": amc_cov.total_schemes,
                    "schemes_with_data": amc_cov.schemes_with_data,
                    "total_expected": amc_cov.total_expected,
                    "total_stored": amc_cov.total_stored,
                    "total_missing": amc_cov.total_missing,
                    "coverage_pct": amc_cov.coverage_pct,
                    "earliest": amc_cov.earliest_date.isoformat() if amc_cov.earliest_date else None,
                    "latest": amc_cov.latest_date.isoformat() if amc_cov.latest_date else None,
                }
            report["datasets"][dt] = entry

        # Open alerts
        alerts = session.query(CoverageAlert).filter(CoverageAlert.status == "open").all()
        report["alerts"] = []
        for alert in alerts:
            scheme = session.get(Scheme, alert.scheme_id) if alert.scheme_id else None
            amc = session.get(AMC, alert.amc_id) if alert.amc_id else None
            report["alerts"].append({
                "id": str(alert.id),
                "type": alert.alert_type,
                "severity": alert.severity,
                "dataset_type": alert.dataset_type,
                "amc": amc.name if amc else None,
                "scheme": scheme.scheme_name if scheme else None,
                "message": alert.message,
                "details": alert.details_json,
                "created_at": alert.created_at.isoformat(),
            })

        return report

    finally:
        session.close()