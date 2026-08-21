"""SQLAlchemy models and idempotent upserts for screener.in ingestion."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.types import TypeDecorator, CHAR

import uuid


class GUID(TypeDecorator):
    """Platform-independent GUID: PG UUID, else CHAR(36)."""

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        return str(value)

    def process_result_value(self, value, dialect):
        return str(value) if value is not None else None

LOGGER = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------- models


class Stock(Base):
    __tablename__ = "stocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(256))
    bse_code: Mapped[str | None] = mapped_column(String(16))
    nse_code: Mapped[str | None] = mapped_column(String(16))
    sector_broad: Mapped[str | None] = mapped_column(String(128))
    sector: Mapped[str | None] = mapped_column(String(128))
    industry: Mapped[str | None] = mapped_column(String(128))
    about_text: Mapped[str | None] = mapped_column(Text)
    warehouse_id: Mapped[str | None] = mapped_column(String(32))
    company_id: Mapped[str | None] = mapped_column(String(32))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StockSnapshot(Base):
    """Append-only history of header ratios per fetch."""

    __tablename__ = "stock_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    market_cap_cr: Mapped[float | None] = mapped_column(Numeric)
    current_price: Mapped[float | None] = mapped_column(Numeric)
    high_52w: Mapped[float | None] = mapped_column(Numeric)
    low_52w: Mapped[float | None] = mapped_column(Numeric)
    stock_pe: Mapped[float | None] = mapped_column(Numeric)
    book_value: Mapped[float | None] = mapped_column(Numeric)
    dividend_yield: Mapped[float | None] = mapped_column(Numeric)
    roce_pct: Mapped[float | None] = mapped_column(Numeric)
    roe_pct: Mapped[float | None] = mapped_column(Numeric)
    face_value: Mapped[float | None] = mapped_column(Numeric)


class FinancialPeriod(Base):
    __tablename__ = "financial_periods"
    __table_args__ = (
        UniqueConstraint("stock_id", "statement_type", "period_key", name="uq_stock_stmt_period"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), index=True)
    statement_type: Mapped[str] = mapped_column(String(48), index=True)
    period_key: Mapped[str] = mapped_column(String(16))  # ISO date or 'TTM' etc.
    is_date: Mapped[bool] = mapped_column(Boolean, default=True)

    __mapper_args__ = {"eager_defaults": True}


class FinancialLineItem(Base):
    __tablename__ = "financial_line_items"
    __table_args__ = (
        UniqueConstraint("period_id", "line_item", name="uq_period_item"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    period_id: Mapped[int] = mapped_column(ForeignKey("financial_periods.id"), index=True)
    line_item: Mapped[str] = mapped_column(String(128))
    value: Mapped[float | None] = mapped_column(Numeric)


class GrowthSummary(Base):
    __tablename__ = "growth_summary"
    __table_args__ = (
        UniqueConstraint("stock_id", "metric", "window", name="uq_stock_metric_window"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), index=True)
    metric: Mapped[str] = mapped_column(String(128))
    window: Mapped[str] = mapped_column(String(32))
    value_pct: Mapped[float | None] = mapped_column(Numeric)


class PeerRow(Base):
    __tablename__ = "peer_rows"
    __table_args__ = (
        UniqueConstraint("stock_id", "peer_slug", "fetched_on", name="uq_stock_peer_day"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), index=True)
    peer_slug: Mapped[str | None] = mapped_column(String(64))
    peer_name: Mapped[str | None] = mapped_column(String(256))
    cmp_price: Mapped[float | None] = mapped_column(Numeric)
    pe: Mapped[float | None] = mapped_column(Numeric)
    market_cap_cr: Mapped[float | None] = mapped_column(Numeric)
    div_yield_pct: Mapped[float | None] = mapped_column(Numeric)
    np_qtr_cr: Mapped[float | None] = mapped_column(Numeric)
    sales_qtr_cr: Mapped[float | None] = mapped_column(Numeric)
    roce_pct: Mapped[float | None] = mapped_column(Numeric)
    fetched_on: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class PricePoint(Base):
    """Price history. Two sources share this table:
    - series='price'/'dma50'/'dma200'/'volume' — weekly, from screener's chart endpoint
    - series='daily' — daily OHLC from Yahoo Finance (deep back-history)
    """

    __tablename__ = "price_points"
    __table_args__ = (
        UniqueConstraint("stock_id", "point_date", "series", name="uq_stock_date_series"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), index=True)
    point_date: Mapped[Date] = mapped_column(Date)
    series: Mapped[str] = mapped_column(String(16))  # price|dma50|dma200|volume|daily
    close: Mapped[float | None] = mapped_column(Numeric)  # price/dma/daily close
    volume: Mapped[int | None] = mapped_column(Numeric)  # bigint-scale volumes (e.g. Adani Power)
    delivery_pct: Mapped[float | None] = mapped_column(Numeric)  # screener volume meta
    open: Mapped[float | None] = mapped_column(Numeric)  # daily only (yahoo)
    high: Mapped[float | None] = mapped_column(Numeric)  # daily only
    low: Mapped[float | None] = mapped_column(Numeric)  # daily only
    adj_close: Mapped[float | None] = mapped_column(Numeric)  # split/div-adjusted (yahoo)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("stock_id", "source_url", name="uq_stock_doc_url"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), index=True)
    doc_type: Mapped[str | None] = mapped_column(String(32))
    title: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_uuid: Mapped[str] = mapped_column(GUID(), default=lambda: str(uuid.uuid4()))
    stock_slug: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(16), default="running")
    variant: Mapped[str] = mapped_column(String(16), default="consolidated")
    sections_parsed: Mapped[dict | None] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite")
    )
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ---------------------------------------------------------------- engine


def get_engine(database_url: str):
    return create_engine(database_url, pool_pre_ping=True)


def init_db(database_url: str) -> None:
    engine = get_engine(database_url)
    Base.metadata.create_all(engine)
    LOGGER.info("Initialized schema in %s", database_url.split("@")[-1])


# ---------------------------------------------------------------- upserts


def _upsert_stock(session, payload: dict) -> Stock:
    slug = payload["slug"]
    stock = session.query(Stock).filter_by(slug=slug).one_or_none()
    if stock is None:
        stock = Stock(slug=slug)
        session.add(stock)
        session.flush()
    stock.name = payload.get("name") or stock.name
    for f in ("bse_code", "nse_code", "sector_broad", "sector", "industry",
              "about_text", "warehouse_id", "company_id"):
        v = payload.get(f)
        if v:
            setattr(stock, f, v)
    stock.last_fetched_at = datetime.now(timezone.utc)
    return stock


def _upsert_statement(session, stock_id: int, statement_type: str, parsed: dict) -> int:
    """Upsert one statement's periods+items. Returns item count written."""
    periods = parsed.get("periods") or []
    rows = parsed.get("rows") or []
    count = 0
    # cache of period rows for this statement
    existing = {
        p.period_key: p
        for p in session.query(FinancialPeriod).filter_by(stock_id=stock_id, statement_type=statement_type)
    }
    for col_idx, period_key in enumerate(periods):
        if not period_key:
            continue
        fp = existing.get(period_key)
        if fp is None:
            is_date = bool(len(period_key) == 10 and period_key[4] == "-")
            fp = FinancialPeriod(stock_id=stock_id, statement_type=statement_type,
                                 period_key=period_key, is_date=is_date)
            session.add(fp)
            session.flush()
            existing[period_key] = fp
        items = {
            i.line_item: i
            for i in session.query(FinancialLineItem).filter_by(period_id=fp.id)
        }
        for row in rows:
            label = row["label"]
            if col_idx >= len(row["values"]):
                continue
            value = row["values"][col_idx]
            item = items.get(label)
            if item is None:
                session.add(FinancialLineItem(period_id=fp.id, line_item=label, value=value))
            else:
                item.value = value
            count += 1
    return count


def save_payload(database_url: str, payload: dict, peers: list[dict] | None = None,
                 raw_path: str | None = None, price_history: list[dict] | None = None) -> str:
    """Persist one company parse result. Returns run_uuid."""
    engine = get_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    run_uuid = str(uuid.uuid4())
    counts: dict = {}
    try:
        run = IngestionRun(run_uuid=run_uuid, stock_slug=payload["slug"], status="running")
        session.add(run)

        stock = _upsert_stock(session, payload)
        session.flush()

        # snapshot (append-only)
        tr = payload.get("top_ratios") or {}
        snap = StockSnapshot(stock_id=stock.id)
        for f in ("market_cap_cr", "current_price", "high_52w", "low_52w", "stock_pe",
                  "book_value", "dividend_yield", "roce_pct", "roe_pct", "face_value"):
            setattr(snap, f, tr.get(f))
        session.add(snap)
        counts["snapshot"] = 1

        # statements
        stmt_counts = {}
        for stype, parsed in (payload.get("financials") or {}).items():
            stmt_counts[stype] = _upsert_statement(session, stock.id, stype, parsed)
        for stype, parsed in (payload.get("shareholding") or {}).items():
            stmt_counts[stype] = _upsert_statement(session, stock.id, stype, parsed)
        counts["statements"] = stmt_counts
        counts["line_items_total"] = sum(stmt_counts.values())

        # growth summary
        g_count = 0
        for g in payload.get("growth") or []:
            existing = (
                session.query(GrowthSummary)
                .filter_by(stock_id=stock.id, metric=g["metric"], window=g["window"])
                .one_or_none()
            )
            if existing:
                existing.value_pct = g["value_pct"]
            else:
                session.add(GrowthSummary(stock_id=stock.id, metric=g["metric"],
                                          window=g["window"], value_pct=g["value_pct"]))
            g_count += 1
        counts["growth"] = g_count

        # peers
        p_count = 0
        for p in peers or []:
            today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            existing = (
                session.query(PeerRow)
                .filter(
                    PeerRow.stock_id == stock.id,
                    PeerRow.peer_slug == p.get("peer_slug"),
                    PeerRow.fetched_on >= today,
                )
                .one_or_none()
            )
            if existing:
                for f in ("peer_name", "cmp_price", "pe", "market_cap_cr", "div_yield_pct",
                          "np_qtr_cr", "sales_qtr_cr", "roce_pct"):
                    setattr(existing, f, p.get(f))
            else:
                session.add(PeerRow(stock_id=stock.id, **{k: p.get(k) for k in (
                    "peer_slug", "peer_name", "cmp_price", "pe", "market_cap_cr",
                    "div_yield_pct", "np_qtr_cr", "sales_qtr_cr", "roce_pct")}))
            p_count += 1
        counts["peers"] = p_count

        # documents
        d_count = 0
        for d in payload.get("documents") or []:
            existing = (
                session.query(Document)
                .filter_by(stock_id=stock.id, source_url=d["url"])
                .one_or_none()
            )
            if not existing:
                session.add(Document(stock_id=stock.id, doc_type=d.get("doc_type"),
                                     title=d.get("title"), source_url=d["url"]))
                d_count += 1
        counts["documents_new"] = d_count

        # price history (chart endpoint series)
        ph_count = 0
        for pt in price_history or []:
            existing = (
                session.query(PricePoint)
                .filter_by(stock_id=stock.id, point_date=pt["point_date"], series=pt["series"])
                .one_or_none()
            )
            if existing:
                existing.close = pt.get("close")
                existing.volume = pt.get("volume")
                existing.delivery_pct = pt.get("delivery_pct")
                existing.open = pt.get("open")
                existing.high = pt.get("high")
                existing.low = pt.get("low")
                existing.adj_close = pt.get("adj_close")
            else:
                session.add(PricePoint(
                    stock_id=stock.id, point_date=pt["point_date"], series=pt["series"],
                    close=pt.get("close"), volume=pt.get("volume"),
                    delivery_pct=pt.get("delivery_pct"),
                    open=pt.get("open"), high=pt.get("high"), low=pt.get("low"),
                    adj_close=pt.get("adj_close"),
                ))
            ph_count += 1
        counts["price_points"] = ph_count

        counts["raw_artifact"] = raw_path
        run.sections_parsed = counts
        run.status = "success"
        run.finished_at = datetime.now(timezone.utc)
        session.commit()
        LOGGER.info("Saved %s (%s): %s", payload["slug"], run_uuid, counts)
        return run_uuid
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def record_failure(database_url: str, slug: str, variant: str, error: str) -> None:
    engine = get_engine(database_url)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        session.add(IngestionRun(stock_slug=slug, status="failed", variant=variant,
                                 error=str(error)[:2000],
                                 finished_at=datetime.now(timezone.utc)))
        session.commit()
