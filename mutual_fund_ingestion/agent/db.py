"""SQLAlchemy database models and connection helpers."""
from __future__ import annotations

import uuid
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


def create_tables(database_url: str) -> None:
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)


def get_session_maker(database_url: str) -> Any:
    engine = create_engine(database_url)
    return sessionmaker(bind=engine)