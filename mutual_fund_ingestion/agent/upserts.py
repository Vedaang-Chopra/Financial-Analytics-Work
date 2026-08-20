"""Canonical upsert functions — extracted from ``runner.py`` per ``REFACTOR_runner.md``."""
from __future__ import annotations

import logging
import uuid
from datetime import date
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from .db import (
    AMC,
    NAVHistory,
    PortfolioHolding,
    PortfolioSnapshot,
    Scheme,
    ValidationResult,
)
from utils.text_utils import normalize_amc_name


if TYPE_CHECKING:
    from sqlalchemy.orm import Session


LOGGER = logging.getLogger(__name__)


class UpsertManager:
    """Holds all canonical upsert methods.

    Extracted from ``runner.py`` per ``docs/04_in_progress/REFACTOR_runner.md``.
    All methods accept a ``Session`` so the runner retains commit control.
    """

    def upsert_canonical(
        self,
        session: Session,
        records: list[dict[str, Any]],
        dataset_type: str,
        raw_artifact_id: uuid.UUID,
        source_url: str,
        stats: dict[str, Any],
    ) -> None:
        if dataset_type == "nav_history":
            self.upsert_nav_history(session, records, raw_artifact_id, source_url, stats)
        elif dataset_type == "amc_provider_list":
            self.upsert_amcs(session, records, raw_artifact_id, source_url, stats)
        elif dataset_type == "scheme_master":
            self.upsert_schemes(session, records, raw_artifact_id, source_url, stats)
        elif dataset_type == "portfolio_disclosure":
            self.upsert_portfolio(session, records, raw_artifact_id, source_url, stats)
        # Add more dataset types as needed

    def upsert_nav_history(
        self,
        session: Session,
        records: list[dict[str, Any]],
        raw_artifact_id: uuid.UUID,
        source_url: str,
        stats: dict[str, Any],
    ) -> None:
        """Upsert NAV records to ``nav_history`` table."""
        for record in records:
            scheme_code = record.get("scheme_code")
            nav_date_str = record.get("nav_date")
            nav_value = record.get("nav_value")

            if not all([scheme_code, nav_date_str, nav_value]):
                continue

            if not isinstance(nav_date_str, str):
                LOGGER.warning("Invalid date type %s for scheme %s", type(nav_date_str), scheme_code)
                continue

            try:
                nav_date = date.fromisoformat(nav_date_str)
            except ValueError:
                LOGGER.warning("Invalid date %s for scheme %s", nav_date_str, scheme_code)
                continue

            # Resolve or create scheme FK
            scheme = session.execute(
                select(Scheme).where(Scheme.scheme_code == scheme_code)
            ).scalar_one_or_none()

            if not scheme:
                # Create scheme with minimal info
                scheme = Scheme(
                    scheme_code=scheme_code,
                    scheme_name=f"Scheme {scheme_code}",
                    normalized_scheme_name=normalize_amc_name(f"Scheme {scheme_code}"),
                )
                session.add(scheme)
                session.flush()

            stmt = insert(NAVHistory).values(
                scheme_id=scheme.id,
                scheme_code=scheme_code,
                nav_date=nav_date,
                nav_value=nav_value,
                source_url=source_url,
                raw_artifact_id=raw_artifact_id,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["scheme_code", "nav_date"],
                set_={
                    "nav_value": stmt.excluded.nav_value,
                    "source_url": stmt.excluded.source_url,
                    "raw_artifact_id": stmt.excluded.raw_artifact_id,
                },
            )
            session.execute(stmt)
            stats["rows_inserted"] = stats.get("rows_inserted", 0) + 1

    def upsert_amcs(
        self,
        session: Session,
        records: list[dict[str, Any]],
        raw_artifact_id: uuid.UUID,
        source_url: str,
        stats: dict[str, Any],
    ) -> None:
        """Upsert AMC records to ``amcs`` table."""
        for record in records:
            name = record.get("name")
            if not name:
                continue

            normalized = normalize_amc_name(name)

            stmt = insert(AMC).values(
                name=name,
                normalized_name=normalized,
                website_url=record.get("website_url"),
                source_url=source_url,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["normalized_name"],
                set_={
                    "name": stmt.excluded.name,
                    "website_url": stmt.excluded.website_url,
                    "source_url": stmt.excluded.source_url,
                },
            )
            session.execute(stmt)
            stats["rows_inserted"] = stats.get("rows_inserted", 0) + 1

    def upsert_schemes(
        self,
        session: Session,
        records: list[dict[str, Any]],
        raw_artifact_id: uuid.UUID,
        source_url: str,
        stats: dict[str, Any],
    ) -> None:
        """Upsert scheme records to ``schemes`` table."""
        for record in records:
            scheme_code = record.get("scheme_code")
            scheme_name = record.get("scheme_name") or record.get("name")
            amc_name = record.get("amc_name")
            category = record.get("category")
            sub_category = record.get("sub_category")

            if not scheme_name:
                continue

            normalized = normalize_amc_name(scheme_name)

            # Resolve AMC FK if amc_name provided
            amc_id = None
            if amc_name:
                amc = session.execute(
                    select(AMC).where(AMC.normalized_name == normalize_amc_name(amc_name))
                ).scalar_one_or_none()
                if amc:
                    amc_id = amc.id

            stmt = insert(Scheme).values(
                amc_id=amc_id,
                scheme_code=scheme_code,
                scheme_name=scheme_name,
                normalized_scheme_name=normalized,
                category=category,
                sub_category=sub_category,
            )
            conflict_elements = ["scheme_code"] if scheme_code else ["normalized_scheme_name"]
            stmt = stmt.on_conflict_do_update(
                index_elements=conflict_elements,
                set_={
                    "scheme_name": stmt.excluded.scheme_name,
                    "normalized_scheme_name": stmt.excluded.normalized_scheme_name,
                    "category": stmt.excluded.category,
                    "sub_category": stmt.excluded.sub_category,
                },
            )
            session.execute(stmt)
            stats["rows_inserted"] = stats.get("rows_inserted", 0) + 1

    def upsert_portfolio(
        self,
        session: Session,
        records: list[dict[str, Any]],
        raw_artifact_id: uuid.UUID,
        source_url: str,
        stats: dict[str, Any],
    ) -> None:
        """Upsert portfolio records to ``portfolio_snapshots`` and ``portfolio_holdings``."""
        from collections import defaultdict

        from .db import Document, Instrument

        # Group by scheme + date to create snapshots
        snapshots: dict[tuple, list[dict[str, Any]]] = defaultdict(list)

        for record in records:
            scheme_name = record.get("scheme_name")
            reporting_date_str = record.get("reporting_date") or record.get("date")

            if not scheme_name:
                continue

            try:
                reporting_date = (
                    date.fromisoformat(reporting_date_str) if reporting_date_str else date.today()
                )
            except ValueError:
                reporting_date = date.today()

            # Resolve or create scheme
            scheme = session.execute(
                select(Scheme).where(Scheme.normalized_scheme_name == normalize_amc_name(scheme_name))
            ).scalar_one_or_none()

            if not scheme:
                scheme = session.execute(
                    select(Scheme).where(Scheme.scheme_name.ilike(f"%{scheme_name}%"))
                ).scalar_one_or_none()

            if not scheme:
                # Create scheme with minimal info
                scheme = Scheme(
                    scheme_name=scheme_name,
                    normalized_scheme_name=normalize_amc_name(scheme_name),
                )
                session.add(scheme)
                session.flush()

            key = (scheme.id, reporting_date)
            snapshots[key].append(record)

        for (scheme_id, reporting_date), holdings in snapshots.items():
            # Create portfolio snapshot
            snapshot = PortfolioSnapshot(
                scheme_id=scheme_id,
                reporting_date=reporting_date,
                source_url=source_url,
                parser_version="portfolio_excel_v1",
                validation_status="validated",
            )
            session.add(snapshot)
            session.flush()

            # Create document record
            doc = Document(
                document_type="portfolio_disclosure",
                scheme_id=scheme_id,
                reporting_date=reporting_date,
                source_url=source_url,
                file_type="xlsx",
            )
            session.add(doc)
            session.flush()

            snapshot.document_id = doc.id

            # Create holdings
            for holding in holdings:
                security_name = holding.get("security_name")
                if not security_name:
                    continue

                isin = holding.get("isin")
                sector = holding.get("sector")

                # Resolve or create instrument
                if isin:
                    instrument = session.execute(
                        select(Instrument).where(Instrument.isin == isin)
                    ).scalar_one_or_none()
                else:
                    instrument = None

                if not instrument:
                    instrument = Instrument(
                        isin=isin,
                        name=security_name,
                        normalized_name=normalize_amc_name(security_name),
                        sector=sector,
                    )
                    session.add(instrument)
                    session.flush()

                # Create holding
                portfolio_holding = PortfolioHolding(
                    snapshot_id=snapshot.id,
                    instrument_id=instrument.id,
                    security_name=security_name,
                    isin=isin,
                    sector=sector,
                    asset_class=holding.get("asset_class"),
                    quantity=holding.get("quantity"),
                    market_value=holding.get("market_value"),
                    percentage_to_nav=holding.get("percentage_to_nav"),
                )
                session.add(portfolio_holding)
                stats["rows_inserted"] = stats.get("rows_inserted", 0) + 1

            stats["rows_inserted"] = stats.get("rows_inserted", 0) + 1  # snapshot

    def write_validation_result(
        self,
        session: Session,
        entity_type: str,
        check_name: str,
        severity: str,
        status: str,
        message: str | None,
    ) -> None:
        """Write a ``validation_results`` record."""
        vr = ValidationResult(
            run_id=uuid.UUID(self._run_id),
            entity_type=entity_type,
            check_name=check_name,
            severity=severity,
            status=status,
            message=message,
        )
        session.add(vr)

    # ------------------------------------------------------------------
    # The run_id is set by the runner before calling these methods.
    # We store it here so write_validation_result can use it.
    # ------------------------------------------------------------------
    _run_id: str = ""

    def set_run_id(self, run_id: str) -> None:
        self._run_id = run_id