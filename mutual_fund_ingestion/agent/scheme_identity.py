"""Scheme Identity Layer - Canonical scheme identification with AMFI code/ISIN mapping.

This module provides:
1. Scheme identity resolution using official identifiers (AMFI scheme code, ISIN)
2. Mapping between different naming conventions across sources
3. Handling of scheme renames, mergers, discontinuations
4. Plan/option (Direct/Regular, Growth/IDCW) normalization
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from mutual_fund_ingestion.agent.db import (
    AMC,
    Scheme,
    Instrument,
    get_session_maker,
)
from utils.text_utils import normalize_amc_name

LOGGER = logging.getLogger(__name__)


@dataclass
class SchemeIdentity:
    """Resolved scheme identity with all identifiers."""
    scheme_id: uuid.UUID | None = None
    scheme_code: str | None = None
    scheme_name: str | None = None
    normalized_name: str | None = None
    amc_id: uuid.UUID | None = None
    amc_name: str | None = None
    plan: str | None = None  # Direct, Regular
    option: str | None = None  # Growth, IDCW, Dividend
    isin_div_payout: str | None = None
    isin_div_reinvestment: str | None = None
    category: str | None = None
    sub_category: str | None = None
    confidence: float = 0.0
    match_method: str = "unknown"
    aliases: list[str] = field(default_factory=list)


class SchemeIdentityResolver:
    """Resolves scheme identities from various sources using official identifiers."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.session_maker = get_session_maker(database_url)
        self._scheme_code_cache: dict[str, Scheme] = {}
        self._isin_cache: dict[str, Scheme] = {}
        self._normalized_name_cache: dict[str, list[Scheme]] = {}

    def _load_caches(self, session: Session) -> None:
        """Load scheme caches from database."""
        schemes = session.query(Scheme).all()
        for scheme in schemes:
            if scheme.scheme_code:
                self._scheme_code_cache[scheme.scheme_code] = scheme
            # Cache ISINs from metadata
            if scheme.metadata_json:
                isin_payout = scheme.metadata_json.get("isin_div_payout")
                isin_reinv = scheme.metadata_json.get("isin_div_reinvestment")
                if isin_payout:
                    self._isin_cache[isin_payout] = scheme
                if isin_reinv:
                    self._isin_cache[isin_reinv] = scheme
            if scheme.normalized_scheme_name:
                if scheme.normalized_scheme_name not in self._normalized_name_cache:
                    self._normalized_name_cache[scheme.normalized_scheme_name] = []
                self._normalized_name_cache[scheme.normalized_scheme_name].append(scheme)

    def resolve_from_amfi_nav_row(self, row: dict[str, Any], session: Session) -> SchemeIdentity:
        """Resolve scheme from AMFI NAV row (scheme_code, ISINs, name, plan, option)."""
        identity = SchemeIdentity()

        # Primary: scheme_code (most reliable)
        scheme_code = row.get("scheme_code", "").strip()
        if scheme_code:
            identity.scheme_code = scheme_code
            if scheme_code in self._scheme_code_cache:
                scheme = self._scheme_code_cache[scheme_code]
                identity.scheme_id = scheme.id
                identity.confidence = 1.0
                identity.match_method = "scheme_code_exact"
                return self._populate_from_scheme(identity, scheme)

        # Secondary: ISIN matching
        isin_payout = row.get("isin_div_payout", "").strip()
        isin_reinv = row.get("isin_div_reinvestment", "").strip()
        for isin in [isin_payout, isin_reinv]:
            if isin and isin in self._isin_cache:
                scheme = self._isin_cache[isin]
                identity.scheme_id = scheme.id
                identity.scheme_code = scheme.scheme_code
                identity.isin_div_payout = isin_payout
                identity.isin_div_reinvestment = isin_reinv
                identity.confidence = 0.95
                identity.match_method = "isin_exact"
                return self._populate_from_scheme(identity, scheme)

        # Tertiary: Name matching with plan/option
        scheme_name = row.get("scheme_name", "").strip()
        plan = row.get("plan", "").strip()
        option = row.get("option", "").strip()

        if scheme_name:
            identity = self._resolve_by_name(scheme_name, plan, option, session)
            if identity.confidence > 0:
                return identity

        # Last resort: Create new scheme entry
        identity = SchemeIdentity(
            scheme_code=scheme_code or None,
            scheme_name=scheme_name or None,
            plan=plan or None,
            option=option or None,
            isin_div_payout=isin_payout or None,
            isin_div_reinvestment=isin_reinv or None,
            normalized_name=normalize_amc_name(scheme_name) if scheme_name else None,
            confidence=0.1,
            match_method="new_creation",
        )
        return identity

    def _resolve_by_name(
        self,
        scheme_name: str,
        plan: str | None,
        option: str | None,
        session: Session,
    ) -> SchemeIdentity:
        """Resolve scheme by name with fuzzy matching."""
        identity = SchemeIdentity(scheme_name=scheme_name, plan=plan, option=option)
        normalized = normalize_amc_name(scheme_name)

        # Exact normalized name match
        if normalized in self._normalized_name_cache:
            candidates = self._normalized_name_cache[normalized]
            if len(candidates) == 1:
                scheme = candidates[0]
                identity.scheme_id = scheme.id
                identity.confidence = 0.9
                identity.match_method = "normalized_name_exact"
                return self._populate_from_scheme(identity, scheme)
            elif len(candidates) > 1:
                # Disambiguate by plan/option
                for scheme in candidates:
                    if self._match_plan_option(scheme, plan, option):
                        identity.scheme_id = scheme.id
                        identity.confidence = 0.85
                        identity.match_method = "normalized_name_plan_option"
                        return self._populate_from_scheme(identity, scheme)
                # Take first if no plan/option match
                scheme = candidates[0]
                identity.scheme_id = scheme.id
                identity.confidence = 0.7
                identity.match_method = "normalized_name_ambiguous"
                return self._populate_from_scheme(identity, scheme)

        # Fuzzy name search
        schemes = session.query(Scheme).filter(
            Scheme.normalized_scheme_name.ilike(f"%{normalized}%")
        ).limit(5).all()

        if schemes:
            # Score candidates
            best_scheme = None
            best_score = 0.0
            for scheme in schemes:
                score = self._name_similarity(normalized, scheme.normalized_scheme_name)
                if plan and option:
                    if self._match_plan_option(scheme, plan, option):
                        score += 0.2
                if score > best_score:
                    best_score = score
                    best_scheme = scheme

            if best_scheme and best_score > 0.6:
                identity.scheme_id = best_scheme.id
                identity.confidence = min(best_score, 0.8)
                identity.match_method = "fuzzy_name"
                return self._populate_from_scheme(identity, best_scheme)

        identity.confidence = 0.0
        identity.match_method = "no_match"
        return identity

    def _match_plan_option(self, scheme: Scheme, plan: str | None, option: str | None) -> bool:
        """Check if scheme matches plan/option."""
        if not plan and not option:
            return True
        metadata = scheme.metadata_json or {}
        scheme_plan = metadata.get("plan", "").lower()
        scheme_option = metadata.get("option", "").lower()

        plan_match = not plan or plan.lower() == scheme_plan
        option_match = not option or option.lower() == scheme_option

        return plan_match and option_match

    def _name_similarity(self, name1: str, name2: str) -> float:
        """Calculate name similarity (simple token overlap)."""
        tokens1 = set(name1.lower().split())
        tokens2 = set(name2.lower().split())
        if not tokens1 or not tokens2:
            return 0.0
        intersection = tokens1 & tokens2
        union = tokens1 | tokens2
        return len(intersection) / len(union)

    def _populate_from_scheme(self, identity: SchemeIdentity, scheme: Scheme) -> SchemeIdentity:
        """Populate identity fields from scheme record."""
        identity.scheme_id = scheme.id
        identity.scheme_code = scheme.scheme_code
        identity.scheme_name = scheme.scheme_name
        identity.normalized_name = scheme.normalized_scheme_name
        identity.amc_id = scheme.amc_id
        identity.category = scheme.category
        identity.sub_category = scheme.sub_category

        # Extract plan/option from metadata
        metadata = scheme.metadata_json or {}
        identity.plan = metadata.get("plan")
        identity.option = metadata.get("option")
        identity.isin_div_payout = metadata.get("isin_div_payout")
        identity.isin_div_reinvestment = metadata.get("isin_div_reinvestment")

        return identity

    def resolve_from_portfolio_row(
        self,
        row: dict[str, Any],
        amc_name: str,
        reporting_date: date | None,
        session: Session,
    ) -> SchemeIdentity:
        """Resolve scheme from portfolio disclosure row."""
        identity = SchemeIdentity()

        # Portfolio files typically have scheme_name from filename or sheet
        scheme_name = (
            row.get("scheme_name")
            or row.get("zip_scheme_name")
            or row.get("sheet_name")
            or ""
        ).strip()

        if not scheme_name:
            identity.confidence = 0.0
            identity.match_method = "no_scheme_name"
            return identity

        # Clean up scheme name
        scheme_name = self._clean_scheme_name(scheme_name)
        identity.scheme_name = scheme_name

        # Resolve AMC first
        amc = session.query(AMC).filter(AMC.normalized_name == normalize_amc_name(amc_name)).first()
        if amc:
            identity.amc_id = amc.id
            identity.amc_name = amc.name

            # Search schemes under this AMC
            schemes = session.query(Scheme).filter(Scheme.amc_id == amc.id).all()
            for scheme in schemes:
                if self._name_similarity(normalize_amc_name(scheme_name), scheme.normalized_scheme_name) > 0.7:
                    identity.scheme_id = scheme.id
                    identity.confidence = 0.8
                    identity.match_method = "portfolio_name_amc_scoped"
                    return self._populate_from_scheme(identity, scheme)

        # Fallback to global name search
        return self._resolve_by_name(scheme_name, None, None, session)

    def _clean_scheme_name(self, name: str) -> str:
        """Clean scheme name from portfolio files."""
        # Remove common suffixes
        suffixes = [
            r"\s*[-_]\s*(IDCW|Growth|Direct|Regular|Plan)$",
            r"\s*\([^)]*\)$",  # Remove trailing parentheticals
            r"\s*-?\s*(Direct|Regular)\s*(Plan)?$",
        ]
        cleaned = name
        for pattern in suffixes:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
        return cleaned.strip()

    def get_or_create_scheme(self, identity: SchemeIdentity, session: Session) -> Scheme:
        """Get existing scheme or create new one from identity."""
        if identity.scheme_id:
            scheme = session.get(Scheme, identity.scheme_id)
            if scheme:
                return scheme

        if identity.scheme_code:
            scheme = session.query(Scheme).filter(Scheme.scheme_code == identity.scheme_code).first()
            if scheme:
                return scheme

        # Create new scheme
        scheme = Scheme(
            scheme_code=identity.scheme_code,
            scheme_name=identity.scheme_name or f"Scheme {identity.scheme_code}",
            normalized_scheme_name=identity.normalized_name or normalize_amc_name(identity.scheme_name or ""),
            amc_id=identity.amc_id,
            category=identity.category,
            sub_category=identity.sub_category,
            metadata_json={
                "plan": identity.plan,
                "option": identity.option,
                "isin_div_payout": identity.isin_div_payout,
                "isin_div_reinvestment": identity.isin_div_reinvestment,
                "resolved_from": identity.match_method,
                "resolution_confidence": identity.confidence,
            } if any([identity.plan, identity.option, identity.isin_div_payout, identity.isin_div_reinvestment]) else {},
        )
        session.add(scheme)
        session.flush()

        # Update caches
        if scheme.scheme_code:
            self._scheme_code_cache[scheme.scheme_code] = scheme
        if scheme.normalized_scheme_name:
            if scheme.normalized_scheme_name not in self._normalized_name_cache:
                self._normalized_name_cache[scheme.normalized_scheme_name] = []
            self._normalized_name_cache[scheme.normalized_scheme_name].append(scheme)

        return scheme

    def resolve_instrument(self, row: dict[str, Any], session: Session) -> Instrument | None:
        """Resolve instrument from holding row using ISIN."""
        isin = row.get("isin")
        if isin and isin.strip():
            isin = isin.strip()
            # Check cache first
            if isin in self._isin_cache:
                scheme = self._isin_cache[isin]
                # Look for instrument with this ISIN
                instrument = session.query(Instrument).filter(Instrument.isin == isin).first()
                if instrument:
                    return instrument

            # Create new instrument
            instrument = Instrument(
                isin=isin,
                name=row.get("security_name", "Unknown"),
                normalized_name=normalize_amc_name(row.get("security_name", "Unknown")),
                sector=row.get("sector"),
                instrument_type=row.get("asset_class"),
            )
            session.add(instrument)
            session.flush()
            return instrument

        # No ISIN - match by name
        security_name = row.get("security_name", "").strip()
        if security_name:
            instrument = session.query(Instrument).filter(
                Instrument.normalized_name == normalize_amc_name(security_name)
            ).first()
            if instrument:
                return instrument

            instrument = Instrument(
                isin=None,
                name=security_name,
                normalized_name=normalize_amc_name(security_name),
                sector=row.get("sector"),
                instrument_type=row.get("asset_class"),
            )
            session.add(instrument)
            session.flush()
            return instrument

        return None


class SchemeMappingManager:
    """Manages scheme mapping tables for cross-source reconciliation."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.session_maker = get_session_maker(database_url)

    def record_mapping(
        self,
        source_scheme_name: str,
        source_identifier: str,
        source_type: str,  # 'amfi_nav', 'portfolio_disclosure', 'amc_website'
        canonical_scheme_id: uuid.UUID,
        confidence: float,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record a mapping from source identifier to canonical scheme."""
        session = self.session_maker()
        try:
            # This would ideally use a dedicated scheme_mappings table
            # For now, store in scheme metadata
            scheme = session.get(Scheme, canonical_scheme_id)
            if scheme:
                mappings = scheme.metadata_json.get("source_mappings", [])
                mappings.append({
                    "source_name": source_scheme_name,
                    "source_identifier": source_identifier,
                    "source_type": source_type,
                    "confidence": confidence,
                    "metadata": metadata or {},
                })
                scheme.metadata_json["source_mappings"] = mappings
                session.commit()
        finally:
            session.close()

    def get_mappings_for_scheme(self, scheme_id: uuid.UUID) -> list[dict[str, Any]]:
        """Get all source mappings for a scheme."""
        session = self.session_maker()
        try:
            scheme = session.get(Scheme, scheme_id)
            if scheme and scheme.metadata_json:
                return scheme.metadata_json.get("source_mappings", [])
            return []
        finally:
            session.close()

    def find_scheme_by_source_identifier(
        self,
        source_identifier: str,
        source_type: str,
    ) -> Scheme | None:
        """Find canonical scheme by source identifier."""
        session = self.session_maker()
        try:
            schemes = session.query(Scheme).all()
            for scheme in schemes:
                mappings = scheme.metadata_json.get("source_mappings", [])
                for mapping in mappings:
                    if mapping.get("source_identifier") == source_identifier and mapping.get("source_type") == source_type:
                        return scheme
            return None
        finally:
            session.close()