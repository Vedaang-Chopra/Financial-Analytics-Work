"""SQLAlchemy database models and connection helpers."""
from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import (
    UUID,
    BigInteger,
    Boolean,
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
    UniqueConstraint,
    create_engine,
    func,
)
from sqlalchemy.orm import declarative_base, sessionmaker


Base: Any = declarative_base()


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    started_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(Text, nullable=False)
    config_json = Column(JSON, nullable=False, default=dict)  # type: ignore[assignment]
    pages_seen = Column(Integer, nullable=False, default=0)
    files_seen = Column(Integer, nullable=False, default=0)
    rows_inserted = Column(Integer, nullable=False, default=0)
    rows_rejected = Column(Integer, nullable=False, default=0)
    error_summary = Column(JSON, nullable=False, default=dict)


class TaskURL(Base):
    __tablename__ = "task_urls"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("ingestion_runs.id"), nullable=False)
    url = Column(Text, nullable=False)
    status = Column(Text, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())


class SourcePage(Base):
    __tablename__ = "source_pages"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("ingestion_runs.id"), nullable=False)
    url = Column(Text, nullable=False)
    canonical_url = Column(Text, nullable=True)
    parent_url = Column(Text, nullable=True)
    domain = Column(Text, nullable=True)
    title = Column(Text, nullable=True)
    status_code = Column(Integer, nullable=True)
    content_type = Column(Text, nullable=True)
    page_relevance = Column(Text, nullable=True)
    source_authority_type = Column(Text, nullable=True)
    html_snapshot_path = Column(Text, nullable=True)
    screenshot_path = Column(Text, nullable=True)
    network_log_path = Column(Text, nullable=True)
    metadata_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())

    __table_args__ = (
        Index("ix_source_pages_run_id", "run_id"),
        Index("ix_source_pages_domain", "domain"),
    )


class DiscoveredLink(Base):
    __tablename__ = "discovered_links"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("ingestion_runs.id"), nullable=False)
    source_page_id = Column(UUID(as_uuid=True), ForeignKey("source_pages.id"), nullable=True)
    url = Column(Text, nullable=False)
    anchor_text = Column(Text, nullable=True)
    link_type = Column(Text, nullable=True)
    dataset_type_hint = Column(Text, nullable=True)
    file_type_hint = Column(Text, nullable=True)
    should_follow = Column(Boolean, nullable=False, default=False)
    relevance_score = Column(Float, nullable=True)
    reason = Column(Text, nullable=True)
    metadata_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())

    __table_args__ = (Index("ix_discovered_links_run_id", "run_id"),)


class DatasetCandidate(Base):
    __tablename__ = "dataset_candidates"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("ingestion_runs.id"), nullable=False)
    source_page_id = Column(UUID(as_uuid=True), ForeignKey("source_pages.id"), nullable=True)
    url = Column(Text, nullable=False)
    dataset_type = Column(Text, nullable=True)
    provider_hint = Column(Text, nullable=True)
    download_method = Column(Text, nullable=True)
    file_type = Column(Text, nullable=True)
    requires_browser = Column(Boolean, nullable=False, default=False)
    requires_form = Column(Boolean, nullable=False, default=False)
    requires_vlm = Column(Boolean, nullable=False, default=False)
    confidence = Column(Float, nullable=True)
    status = Column(Text, nullable=False, default="discovered")
    metadata_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())

    __table_args__ = (Index("ix_dataset_candidates_dataset_type", "dataset_type"),)


class RawArtifact(Base):
    __tablename__ = "raw_artifacts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("ingestion_runs.id"), nullable=False)
    dataset_candidate_id = Column(UUID(as_uuid=True), ForeignKey("dataset_candidates.id"), nullable=True)
    source_url = Column(Text, nullable=False)
    artifact_type = Column(Text, nullable=False)
    file_type = Column(Text, nullable=True)
    content_type = Column(Text, nullable=True)
    checksum = Column(Text, nullable=True)
    size_bytes = Column(BigInteger, nullable=True)
    local_path = Column(Text, nullable=True)
    retained = Column(Boolean, nullable=False, default=False)
    fetch_timestamp = Column(DateTime(timezone=True), nullable=False, default=func.now())
    metadata_json = Column(JSON, nullable=False, default=dict)

    __table_args__ = (Index("ix_raw_artifacts_checksum", "checksum"),)


class AMC(Base):
    __tablename__ = "amcs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    normalized_name = Column(Text, nullable=False, unique=True)
    amfi_code = Column(Text, nullable=True)
    website_url = Column(Text, nullable=True)
    source_url = Column(Text, nullable=True)
    metadata_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())

    __table_args__ = (Index("ix_amcs_normalized_name", "normalized_name"),)


class Scheme(Base):
    __tablename__ = "schemes"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    amc_id = Column(UUID(as_uuid=True), ForeignKey("amcs.id"), nullable=True)
    scheme_code = Column(Text, nullable=True, unique=True)
    scheme_name = Column(Text, nullable=False)
    normalized_scheme_name = Column(Text, nullable=False)
    category = Column(Text, nullable=True)
    sub_category = Column(Text, nullable=True)
    scheme_type = Column(Text, nullable=True)
    benchmark = Column(Text, nullable=True)
    metadata_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_schemes_scheme_code", "scheme_code"),
        Index("ix_schemes_normalized_sname", "normalized_scheme_name"),
    )


class NAVHistory(Base):
    __tablename__ = "nav_history"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scheme_id = Column(UUID(as_uuid=True), ForeignKey("schemes.id"), nullable=True)
    scheme_code = Column(Text, nullable=False)
    nav_date = Column(Date, nullable=False)
    nav_value = Column(Numeric, nullable=False)
    repurchase_price = Column(Numeric, nullable=True)
    sale_price = Column(Numeric, nullable=True)
    source_url = Column(Text, nullable=False)
    raw_artifact_id = Column(UUID(as_uuid=True), ForeignKey("raw_artifacts.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())

    __table_args__ = (
        Index("ix_nav_history_scheme_code_nav_date", "scheme_code", "nav_date"),
        # SQLite-compatible unique constraint for upsert
        Index("uq_nav_history_scheme_code_nav_date", "scheme_code", "nav_date", unique=True),
    )


class Document(Base):
    __tablename__ = "documents"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    raw_artifact_id = Column(UUID(as_uuid=True), ForeignKey("raw_artifacts.id"), nullable=True)
    document_type = Column(Text, nullable=False)
    amc_id = Column(UUID(as_uuid=True), ForeignKey("amcs.id"), nullable=True)
    scheme_id = Column(UUID(as_uuid=True), ForeignKey("schemes.id"), nullable=True)
    reporting_date = Column(Date, nullable=True)
    source_url = Column(Text, nullable=False)
    file_type = Column(Text, nullable=True)
    checksum = Column(Text, nullable=True)
    metadata_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())

    # Mirrors live Postgres constraint "documents_scheme_date_type_url_key"
    # (default NULLS DISTINCT, not deferrable). The Document upsert in
    # upserts.py relies on ON CONFLICT (scheme_id, reporting_date,
    # document_type, source_url).
    __table_args__ = (
        UniqueConstraint(
            "scheme_id",
            "reporting_date",
            "document_type",
            "source_url",
            name="documents_scheme_date_type_url_key",
        ),
    )


class Instrument(Base):
    __tablename__ = "instruments"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    isin = Column(Text, nullable=True)
    name = Column(Text, nullable=False)
    normalized_name = Column(Text, nullable=False)
    instrument_type = Column(Text, nullable=True)
    issuer = Column(Text, nullable=True)
    sector = Column(Text, nullable=True)
    metadata_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    amc_id = Column(UUID(as_uuid=True), ForeignKey("amcs.id"), nullable=True)
    scheme_id = Column(UUID(as_uuid=True), ForeignKey("schemes.id"), nullable=True)
    reporting_date = Column(Date, nullable=False)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True)
    source_url = Column(Text, nullable=False)
    parser_version = Column(Text, nullable=True)
    validation_status = Column(Text, nullable=False)
    metadata_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())

    __table_args__ = (Index("ix_portfolio_snapshots_scheme_id_reporting_date", "scheme_id", "reporting_date"),)


class PortfolioHolding(Base):
    __tablename__ = "portfolio_holdings"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    snapshot_id = Column(UUID(as_uuid=True), ForeignKey("portfolio_snapshots.id"), nullable=False)
    instrument_id = Column(UUID(as_uuid=True), ForeignKey("instruments.id"), nullable=True)
    security_name = Column(Text, nullable=False)
    isin = Column(Text, nullable=True)
    sector = Column(Text, nullable=True)
    asset_class = Column(Text, nullable=True)
    quantity = Column(Numeric, nullable=True)
    market_value = Column(Numeric, nullable=True)
    market_value_currency = Column(Text, nullable=False, default="INR")
    percentage_to_nav = Column(Numeric, nullable=True)
    coupon = Column(Numeric, nullable=True)
    maturity_date = Column(Date, nullable=True)
    rating = Column(Text, nullable=True)
    metadata_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())

    __table_args__ = (
        Index("ix_portfolio_holdings_isin", "isin"),
        Index("ix_portfolio_holdings_security_name", "security_name"),
    )


class StagingRow(Base):
    __tablename__ = "staging_rows"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("ingestion_runs.id"), nullable=False)
    raw_artifact_id = Column(UUID(as_uuid=True), ForeignKey("raw_artifacts.id"), nullable=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True)
    dataset_type = Column(Text, nullable=False)
    sheet_name = Column(Text, nullable=True)
    row_number = Column(Integer, nullable=True)
    raw_row_json = Column(JSON, nullable=False)
    parsed_fields_json = Column(JSON, nullable=False, default=dict)
    parser_name = Column(Text, nullable=True)
    parser_confidence = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())


class ValidationResult(Base):
    __tablename__ = "validation_results"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("ingestion_runs.id"), nullable=False)
    entity_type = Column(Text, nullable=False)
    entity_id = Column(UUID(as_uuid=True), nullable=True)
    check_name = Column(Text, nullable=False)
    severity = Column(Text, nullable=False)
    status = Column(Text, nullable=False)
    message = Column(Text, nullable=True)
    metadata_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())


class QuarantineRow(Base):
    __tablename__ = "quarantine_rows"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("ingestion_runs.id"), nullable=False)
    raw_artifact_id = Column(UUID(as_uuid=True), ForeignKey("raw_artifacts.id"), nullable=True)
    dataset_type = Column(Text, nullable=True)
    reason = Column(Text, nullable=False)
    raw_data_json = Column(JSON, nullable=True)
    parser_error = Column(Text, nullable=True)
    retryable = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())


class RetryQueue(Base):
    __tablename__ = "retry_queue"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("ingestion_runs.id"), nullable=False)
    url = Column(Text, nullable=False)
    task_type = Column(Text, nullable=False)
    failure_reason = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(Text, nullable=False, default="pending")
    retryable = Column(Boolean, nullable=False, default=True)
    metadata_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())

    __table_args__ = (Index("ix_retry_queue_status", "status"),)


class CoverageSnapshot(Base):
    __tablename__ = "coverage_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    snapshot_date = Column(Date, nullable=False, default=lambda: date.today())
    dataset_type = Column(Text, nullable=False)  # nav_history, portfolio_disclosure
    amc_id = Column(UUID(as_uuid=True), ForeignKey("amcs.id"), nullable=True)
    scheme_id = Column(UUID(as_uuid=True), ForeignKey("schemes.id"), nullable=True)

    # Coverage metrics
    expected_count = Column(Integer, nullable=False, default=0)
    actual_count = Column(Integer, nullable=False, default=0)
    missing_count = Column(Integer, nullable=False, default=0)
    coverage_pct = Column(Float, nullable=False, default=0.0)

    # Date range info
    earliest_date = Column(Date, nullable=True)
    latest_date = Column(Date, nullable=True)
    expected_start = Column(Date, nullable=True)
    expected_end = Column(Date, nullable=True)

    # Metadata
    metadata_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())

    __table_args__ = (
        UniqueConstraint("snapshot_date", "dataset_type", "amc_id", "scheme_id", name="uq_coverage_snapshot"),
        Index("ix_coverage_snapshot_date_type", "snapshot_date", "dataset_type"),
        Index("ix_coverage_snapshot_amc", "amc_id"),
        Index("ix_coverage_snapshot_scheme", "scheme_id"),
    )


class SchemeCoverage(Base):
    __tablename__ = "scheme_coverage"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scheme_id = Column(UUID(as_uuid=True), ForeignKey("schemes.id"), nullable=False, unique=True)
    dataset_type = Column(Text, nullable=False)  # nav_history, portfolio_disclosure

    # Date range
    earliest_source_date = Column(Date, nullable=True)
    latest_source_date = Column(Date, nullable=True)
    earliest_stored_date = Column(Date, nullable=True)
    latest_stored_date = Column(Date, nullable=True)

    # Counts
    expected_observations = Column(Integer, nullable=False, default=0)
    stored_observations = Column(Integer, nullable=False, default=0)
    missing_observations = Column(Integer, nullable=False, default=0)
    coverage_pct = Column(Float, nullable=False, default=0.0)

    # Gap details
    missing_periods_json = Column(JSON, nullable=False, default=list)
    last_gap_check = Column(DateTime(timezone=True), nullable=True)

    # Status
    status = Column(Text, nullable=False, default="active")  # active, discontinued, merged, missing
    last_updated = Column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("scheme_id", "dataset_type", name="uq_scheme_coverage"),
        Index("ix_scheme_coverage_status", "status"),
        Index("ix_scheme_coverage_pct", "coverage_pct"),
    )


class AMCoverage(Base):
    __tablename__ = "amc_coverage"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    amc_id = Column(UUID(as_uuid=True), ForeignKey("amcs.id"), nullable=False, unique=True)
    dataset_type = Column(Text, nullable=False)

    # Aggregated counts
    total_schemes = Column(Integer, nullable=False, default=0)
    schemes_with_data = Column(Integer, nullable=False, default=0)
    total_expected = Column(Integer, nullable=False, default=0)
    total_stored = Column(Integer, nullable=False, default=0)
    total_missing = Column(Integer, nullable=False, default=0)
    coverage_pct = Column(Float, nullable=False, default=0.0)

    # Date range
    earliest_date = Column(Date, nullable=True)
    latest_date = Column(Date, nullable=True)

    last_updated = Column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("amc_id", "dataset_type", name="uq_amc_coverage"),
        Index("ix_amc_coverage_pct", "coverage_pct"),
    )


class DatasetCoverage(Base):
    __tablename__ = "dataset_coverage"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_type = Column(Text, nullable=False, unique=True)  # nav_history, portfolio_disclosure, etc.

    # Global counts
    total_amcs = Column(Integer, nullable=False, default=0)
    total_schemes = Column(Integer, nullable=False, default=0)
    total_expected = Column(Integer, nullable=False, default=0)
    total_stored = Column(Integer, nullable=False, default=0)
    total_missing = Column(Integer, nullable=False, default=0)
    coverage_pct = Column(Float, nullable=False, default=0.0)

    # Date range
    global_earliest = Column(Date, nullable=True)
    global_latest = Column(Date, nullable=True)

    # Quality metrics
    amcs_complete = Column(Integer, nullable=False, default=0)  # 100% coverage
    amcs_partial = Column(Integer, nullable=False, default=0)   # 50-99%
    amcs_minimal = Column(Integer, nullable=False, default=0)   # 1-49%
    amcs_empty = Column(Integer, nullable=False, default=0)     # 0%

    last_updated = Column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())

    __table_args__ = (Index("ix_dataset_coverage_pct", "coverage_pct"),)


class CoverageAlert(Base):
    __tablename__ = "coverage_alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_type = Column(Text, nullable=False)  # gap_detected, coverage_drop, new_scheme_missing, stale_data
    severity = Column(Text, nullable=False)  # info, warning, critical

    # Scope
    dataset_type = Column(Text, nullable=False)
    amc_id = Column(UUID(as_uuid=True), ForeignKey("amcs.id"), nullable=True)
    scheme_id = Column(UUID(as_uuid=True), ForeignKey("schemes.id"), nullable=True)

    # Details
    message = Column(Text, nullable=False)
    details_json = Column(JSON, nullable=False, default=dict)

    # Status
    status = Column(Text, nullable=False, default="open")  # open, acknowledged, resolved
    acknowledged_by = Column(Text, nullable=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())

    __table_args__ = (
        Index("ix_coverage_alert_status", "status"),
        Index("ix_coverage_alert_type", "alert_type"),
        Index("ix_coverage_alert_scheme", "scheme_id"),
    )


class IngestionQualityMetrics(Base):
    __tablename__ = "ingestion_quality_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("ingestion_runs.id"), nullable=False, unique=True)
    dataset_type = Column(Text, nullable=False)

    # Input metrics
    sources_discovered = Column(Integer, nullable=False, default=0)
    files_discovered = Column(Integer, nullable=False, default=0)
    files_downloaded = Column(Integer, nullable=False, default=0)
    files_skipped_duplicate = Column(Integer, nullable=False, default=0)
    files_failed = Column(Integer, nullable=False, default=0)

    # Processing metrics
    artifacts_parsed = Column(Integer, nullable=False, default=0)
    rows_parsed = Column(Integer, nullable=False, default=0)
    rows_valid = Column(Integer, nullable=False, default=0)
    rows_quarantined = Column(Integer, nullable=False, default=0)
    rows_upserted = Column(Integer, nullable=False, default=0)
    rows_updated = Column(Integer, nullable=False, default=0)

    # Quality ratios
    parse_success_rate = Column(Float, nullable=True)
    validation_pass_rate = Column(Float, nullable=True)
    upsert_success_rate = Column(Float, nullable=True)

    # Error breakdown
    errors_by_type = Column(JSON, nullable=False, default=dict)
    errors_by_provider = Column(JSON, nullable=False, default=dict)

    # Timing
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Float, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())

    __table_args__ = (
        Index("ix_quality_metrics_run", "run_id"),
        Index("ix_quality_metrics_dataset", "dataset_type"),
    )


class IndexPrice(Base):
    __tablename__ = "index_prices"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
                server_default=func.gen_random_uuid())
    index_symbol = Column(Text, nullable=False)
    trade_date = Column(Date, nullable=False)
    close = Column(Numeric, nullable=False)
    source_url = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())

    __table_args__ = (
        UniqueConstraint("index_symbol", "trade_date", name="uq_index_prices_symbol_date"),
        Index("ix_index_prices_symbol_date", "index_symbol", "trade_date"),
    )


class SchemeAumHistory(Base):
    """Monthly/quarterly average AUM (₹ crore) per scheme.

    Primary source: AMFI scheme-wise Average AUM API
    (https://www.amfiindia.com/api/average-aum-schemewise) — quarterly
    periods keyed by AMFI scheme code; month_start is the first day of
    the reporting period's opening month (quarterly data lands on the
    quarter's first day).
    """

    __tablename__ = "scheme_aum_history"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
                server_default=func.gen_random_uuid())
    scheme_id = Column(UUID(as_uuid=True), ForeignKey("schemes.id"), nullable=True)
    month_start = Column(Date, nullable=False)
    avg_aum_cr = Column(Numeric, nullable=True)
    source_url = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())

    __table_args__ = (
        UniqueConstraint("scheme_id", "month_start", name="uq_scheme_aum_history_scheme_month"),
        Index("ix_scheme_aum_history_scheme_month", "scheme_id", "month_start"),
    )


class SecurityPrice(Base):
    """Daily closing price/volume for one security (NSE bhavcopy)."""

    __tablename__ = "security_prices"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    isin = Column(Text, nullable=False)
    trade_date = Column(Date, nullable=False)
    close = Column(Numeric, nullable=False)
    volume = Column(BigInteger, nullable=True)
    source_url = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())

    __table_args__ = (
        UniqueConstraint("isin", "trade_date", name="uq_security_prices_isin_trade_date"),
        Index("ix_security_prices_isin_date", "isin", "trade_date"),
    )


def create_tables(database_url: str) -> None:
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)


def get_session_maker(database_url: str) -> Any:
    engine = create_engine(database_url)
    return sessionmaker(bind=engine)