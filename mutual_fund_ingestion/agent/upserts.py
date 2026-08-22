"""Canonical upsert functions — extracted from ``runner.py`` per ``REFACTOR_runner.md``."""
from __future__ import annotations

import logging
import uuid
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from sqlalchemy import func, select
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

# Words that never identify an AMC on their own
_AMC_STOP_WORDS = {
    "mutual", "fund", "asset", "management", "company", "ltd", "limited",
    "india", "the", "of", "and", "scheme", "plan", "direct", "regular",
    "growth", "idcw", "dividend", "payout", "reinvestment", "re-investment",
}

# Brand aliases: token found in scheme name -> AMC normalized_name
_AMC_BRAND_ALIASES = {
    "parag": "ppfas",
    "parikh": "ppfas",
    "ppfas": "ppfas",
    "reliance": "nippon india",
    "absl": "aditya birla sun life",
    "sun life": "aditya birla sun life",
    "franklin": "franklin templeton",
    "quantum": "quantum",
}


def _resolve_amc_for_scheme_name(session: Session, scheme_name: str) -> AMC | None:
    """Resolve AMC for a scheme by matching AMC name tokens against the scheme name.

    AMFI scheme names typically start with the AMC name (e.g.
    "Aditya Birla Sun Life Banking & PSU Debt Fund" -> Aditya Birla Sun Life
    Mutual Fund). Match the longest AMC normalized name contained in the
    normalized scheme name; fall back to a leading-token match and finally
    brand aliases (e.g. "Parag Parikh" -> PPFAS).
    """
    amcs_by_norm: dict[str, AMC] = {}
    for amc in session.query(AMC).all():
        if amc.normalized_name and amc.normalized_name not in ("amfi", "sebi"):
            amcs_by_norm[amc.normalized_name] = amc

    normalized_scheme = normalize_amc_name(scheme_name)

    best: AMC | None = None
    best_len = 0
    for norm, amc in amcs_by_norm.items():
        if norm in normalized_scheme and len(norm) > best_len:
            best = amc
            best_len = len(norm)

    if best:
        return best

    # Fallback: match on distinctive leading tokens (e.g. "hdfc")
    scheme_tokens = [
        t for t in normalized_scheme.split()
        if t not in _AMC_STOP_WORDS and len(t) > 2
    ]
    for token in scheme_tokens[:3]:
        for norm, amc in amcs_by_norm.items():
            if token in norm.split():
                return amc

    # Fallback: brand aliases ("parag parikh" -> ppfas)
    for alias, target_norm in _AMC_BRAND_ALIASES.items():
        if alias in normalized_scheme and target_norm in amcs_by_norm:
            return amcs_by_norm[target_norm]

    return None


_AMC_SOURCES_YAML = Path(__file__).resolve().parents[2] / "configs" / "amc_sources.yaml"


def _registered_domain(netloc: str) -> str:
    """Reduce a netloc to its registrable domain (last two labels, www. stripped)."""
    host = netloc.lower().split("@")[-1].split(":")[0]
    parts = host.split(".")
    if parts and parts[0] == "www":
        parts = parts[1:]
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def resolve_amc_by_source_url(
    session: Session,
    source_url: str,
    config_path: Path | str | None = None,
) -> AMC | None:
    """Resolve an AMC by matching the source URL's domain against ``amc_sources.yaml``.

    Each entry in the curated source registry carries a ``seed_url`` and an
    ``amc_name``; when the disclosure source URL shares a registered domain
    with a seed URL, the entry's AMC is looked up (by normalized name). Used
    as the fallback when the scheme itself cannot provide an ``amc_id``.
    """
    try:
        src_domain = _registered_domain(urlparse(source_url).netloc)
    except ValueError:
        return None
    if not src_domain or "." not in src_domain:
        return None

    path = Path(config_path) if config_path else _AMC_SOURCES_YAML
    if not path.exists():
        LOGGER.warning("AMC source registry not found at %s; skipping URL-domain AMC resolution", path)
        return None

    import yaml

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    for entry in data.get("sources", []) or []:
        seed_url = entry.get("seed_url") or ""
        try:
            seed_domain = _registered_domain(urlparse(seed_url).netloc)
        except ValueError:
            continue
        if seed_domain != src_domain:
            continue
        amc_name = entry.get("amc_name")
        if not amc_name:
            continue
        return session.execute(
            select(AMC).where(AMC.normalized_name == normalize_amc_name(amc_name))
        ).scalar_one_or_none()
    return None


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
        checksum: str | None = None,
        amc_name: str | None = None,
    ) -> None:
        if dataset_type == "nav_history":
            self.upsert_nav_history(session, records, raw_artifact_id, source_url, stats)
        elif dataset_type == "amc_provider_list":
            self.upsert_amcs(session, records, raw_artifact_id, source_url, stats)
        elif dataset_type == "scheme_master":
            self.upsert_schemes(session, records, raw_artifact_id, source_url, stats)
        elif dataset_type == "portfolio_disclosure":
            self.upsert_portfolio(
                session, records, raw_artifact_id, source_url, stats,
                checksum=checksum, amc_name=amc_name,
            )
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

            record_scheme_name = record.get("scheme_name")
            record_plan = record.get("plan")
            record_option = record.get("option")
            record_isin_payout = record.get("isin_div_payout")
            record_isin_reinv = record.get("isin_div_reinvestment")

            if not scheme:
                # Create scheme with real name and metadata from AMFI row
                display_name = record_scheme_name or f"Scheme {scheme_code}"
                extra_meta: dict[str, Any] = {}
                if record_plan:
                    extra_meta["plan"] = record_plan
                if record_option:
                    extra_meta["option"] = record_option
                if record_isin_payout and record_isin_payout != "-":
                    extra_meta["isin_div_payout"] = record_isin_payout
                if record_isin_reinv and record_isin_reinv != "-":
                    extra_meta["isin_div_reinvestment"] = record_isin_reinv

                scheme = Scheme(
                    scheme_code=scheme_code,
                    scheme_name=display_name,
                    normalized_scheme_name=normalize_amc_name(display_name),
                    metadata_json=extra_meta,
                )
                session.add(scheme)
                session.flush()
            else:
                # Backfill missing identity fields on existing schemes (e.g. "Scheme 12345" placeholders)
                needs_update = False
                if record_scheme_name and (
                    not scheme.scheme_name or scheme.scheme_name.startswith("Scheme ")
                ):
                    scheme.scheme_name = record_scheme_name
                    scheme.normalized_scheme_name = normalize_amc_name(record_scheme_name)
                    needs_update = True

                meta = dict(scheme.metadata_json or {})
                if record_plan and not meta.get("plan"):
                    meta["plan"] = record_plan
                    needs_update = True
                if record_option and not meta.get("option"):
                    meta["option"] = record_option
                    needs_update = True
                if record_isin_payout and record_isin_payout != "-" and not meta.get("isin_div_payout"):
                    meta["isin_div_payout"] = record_isin_payout
                    needs_update = True
                if record_isin_reinv and record_isin_reinv != "-" and not meta.get("isin_div_reinvestment"):
                    meta["isin_div_reinvestment"] = record_isin_reinv
                    needs_update = True

                if needs_update:
                    scheme.metadata_json = meta

            # Resolve AMC linkage from scheme name (once per scheme)
            if scheme.amc_id is None and record_scheme_name:
                amc = _resolve_amc_for_scheme_name(session, record_scheme_name)
                if amc:
                    scheme.amc_id = amc.id

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

            # Resolve AMC FK: explicit amc_name, then amc_hint metadata, then scheme-name pattern
            amc_id = None
            if amc_name:
                amc = session.execute(
                    select(AMC).where(AMC.normalized_name == normalize_amc_name(amc_name))
                ).scalar_one_or_none()
                if amc:
                    amc_id = amc.id
            if amc_id is None:
                hint = record.get("amc_hint") or record.get("amc_name")
                if hint:
                    amc = session.execute(
                        select(AMC).where(AMC.normalized_name == normalize_amc_name(hint))
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
            # amc_id is intentionally absent from set_: never wipe an existing link
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
        checksum: str | None = None,
        amc_name: str | None = None,
    ) -> None:
        """Upsert portfolio records to ``portfolio_snapshots`` and ``portfolio_holdings``.

        ``amc_name`` (from the ingestion layer) is stamped onto every record as
        ``amc_hint`` so schemes created or matched here get linked to their AMC.
        """
        from collections import defaultdict

        from .db import Document, Instrument, RawArtifact

        if amc_name:
            for record in records:
                record.setdefault("amc_hint", amc_name)

        # Get checksum from raw_artifact if not provided
        if checksum is None:
            raw_artifact = session.get(RawArtifact, raw_artifact_id)
            if raw_artifact is not None:
                cs = getattr(raw_artifact, 'checksum', None)
                if cs:
                    checksum = str(cs)

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

            # Resolve or create scheme (first() - multiple schemes may share a name)
            scheme = session.execute(
                select(Scheme).where(Scheme.normalized_scheme_name == normalize_amc_name(scheme_name))
            ).scalars().first()

            if not scheme:
                scheme = session.execute(
                    select(Scheme).where(Scheme.scheme_name.ilike(f"%{scheme_name}%"))
                ).scalars().first()

            # AMC linkage: hint metadata, then name-pattern resolution
            amc = None
            hint = record.get("amc_hint")
            if hint:
                amc = session.execute(
                    select(AMC).where(AMC.normalized_name == normalize_amc_name(hint))
                ).scalar_one_or_none()
            if amc is None and scheme and scheme.amc_id is None:
                amc = _resolve_amc_for_scheme_name(session, scheme_name)

            if not scheme:
                # Create scheme with minimal info (AMC-linked when resolvable)
                scheme = Scheme(
                    scheme_name=scheme_name,
                    normalized_scheme_name=normalize_amc_name(scheme_name),
                    amc_id=amc.id if amc is not None else None,
                )
                session.add(scheme)
                session.flush()
            elif scheme.amc_id is None and amc is not None:
                scheme.amc_id = amc.id

            key = (scheme.id, reporting_date)
            snapshots[key].append(record)

        # Snapshot-level AMC: prefer the scheme's amc_id; fall back to
        # resolving via the source URL domain against configs/amc_sources.yaml.
        snapshot_amc_ids: dict[tuple, Any] = {}
        needs_url_fallback = False
        for (scheme_id, _reporting_date), _holdings in snapshots.items():
            scheme_row = session.get(Scheme, scheme_id)
            amc_id = scheme_row.amc_id if scheme_row is not None else None
            if amc_id is None:
                needs_url_fallback = True
            snapshot_amc_ids[(scheme_id, _reporting_date)] = amc_id

        url_amc_id = None
        if needs_url_fallback:
            url_amc = resolve_amc_by_source_url(session, source_url)
            if url_amc is not None:
                url_amc_id = url_amc.id

        for (scheme_id, reporting_date), holdings in snapshots.items():
            # Upsert portfolio snapshot (on conflict: update source_url, parser_version, validation_status)
            snap_amc_id = snapshot_amc_ids[(scheme_id, reporting_date)] or url_amc_id
            stmt = insert(PortfolioSnapshot).values(
                scheme_id=scheme_id,
                reporting_date=reporting_date,
                amc_id=snap_amc_id,
                source_url=source_url,
                parser_version="portfolio_excel_v1",
                validation_status="validated",
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["scheme_id", "reporting_date"],
                set_={
                    # coalesce: refresh the link when resolved, never wipe an
                    # existing amc_id if this pass failed to resolve one
                    "amc_id": func.coalesce(stmt.excluded.amc_id, PortfolioSnapshot.amc_id),
                    "source_url": stmt.excluded.source_url,
                    "parser_version": stmt.excluded.parser_version,
                    "validation_status": stmt.excluded.validation_status,
                },
            ).returning(PortfolioSnapshot.id)
            result = session.execute(stmt)
            snapshot_id = result.scalar_one()

            # Upsert document record with provenance linkage
            doc_stmt = insert(Document).values(
                document_type="portfolio_disclosure",
                scheme_id=scheme_id,
                reporting_date=reporting_date,
                source_url=source_url,
                file_type="xlsx",
                raw_artifact_id=raw_artifact_id,
                checksum=checksum,
            )
            doc_stmt = doc_stmt.on_conflict_do_update(
                index_elements=["scheme_id", "reporting_date", "document_type", "source_url"],
                set_={
                    "file_type": doc_stmt.excluded.file_type,
                    "raw_artifact_id": doc_stmt.excluded.raw_artifact_id,
                    "checksum": doc_stmt.excluded.checksum,
                },
            ).returning(Document.id)
            doc_result = session.execute(doc_stmt)
            doc_id = doc_result.scalar_one()

            # Update snapshot with document_id
            session.execute(
                PortfolioSnapshot.__table__.update()
                .where(PortfolioSnapshot.id == snapshot_id)
                .values(document_id=doc_id)
            )

            # Create holdings (upsert on snapshot_id + security_name + isin).
            # Dedupe by (security_name, isin): Postgres enforces a partial
            # unique (snapshot_id, security_name) WHERE isin IS NULL, and the
            # 3-col ON CONFLICT target can't match NULL isins — so repeated
            # NULL-isin rows (e.g. ICICI swap legs) must collapse to one here.
            seen_holdings: set[tuple[str, Any]] = {
                (name, isin)
                for name, isin in session.execute(
                    select(
                        PortfolioHolding.security_name,
                        PortfolioHolding.isin,
                    ).where(PortfolioHolding.snapshot_id == snapshot_id)
                ).all()
            }
            deduped: list[dict[str, Any]] = []
            for holding in holdings:
                security_name = holding.get("security_name")
                if not security_name:
                    continue
                hkey = (str(security_name), str(holding.get("isin")))
                if hkey in seen_holdings:
                    continue
                seen_holdings.add(hkey)
                deduped.append(holding)

            for holding in deduped:

                isin = holding.get("isin")
                sector = holding.get("sector")
                rating = holding.get("rating")

                # Resolve or create instrument.
                # Valid ISIN: look up by ISIN first (existing behavior).
                instrument = None
                if isin:
                    instrument = session.execute(
                        select(Instrument).where(Instrument.isin == isin)
                    ).scalars().first()

                if not instrument and not isin:
                    # Missing ISIN: resolve by normalized_name fallback instead
                    # of blind-inserting a duplicate NULL-ISIN row every time.
                    normalized_name = normalize_amc_name(security_name)
                    instrument = session.execute(
                        select(Instrument)
                        .where(
                            Instrument.isin.is_(None),
                            Instrument.normalized_name == normalized_name,
                        )
                        .order_by(Instrument.created_at)
                        .limit(1)
                    ).scalars().first()

                if not instrument:
                    instrument = Instrument(
                        isin=isin,
                        name=security_name,
                        normalized_name=normalize_amc_name(security_name),
                        sector=sector,
                    )
                    session.add(instrument)
                    session.flush()

                # Upsert holding (on conflict: update fields)
                holding_stmt = insert(PortfolioHolding).values(
                    snapshot_id=snapshot_id,
                    instrument_id=instrument.id,
                    security_name=security_name,
                    isin=isin,
                    sector=sector,
                    rating=rating,
                    asset_class=holding.get("asset_class"),
                    quantity=holding.get("quantity"),
                    market_value=holding.get("market_value"),
                    percentage_to_nav=holding.get("percentage_to_nav"),
                    coupon=holding.get("coupon"),
                    maturity_date=holding.get("maturity_date"),
                )
                holding_stmt = holding_stmt.on_conflict_do_update(
                    index_elements=["snapshot_id", "security_name", "isin"],
                    set_={
                        "instrument_id": holding_stmt.excluded.instrument_id,
                        "sector": holding_stmt.excluded.sector,
                        "rating": holding_stmt.excluded.rating,
                        "asset_class": holding_stmt.excluded.asset_class,
                        "quantity": holding_stmt.excluded.quantity,
                        "market_value": holding_stmt.excluded.market_value,
                        "percentage_to_nav": holding_stmt.excluded.percentage_to_nav,
                        "coupon": holding_stmt.excluded.coupon,
                        "maturity_date": holding_stmt.excluded.maturity_date,
                    },
                )
                session.execute(holding_stmt)
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