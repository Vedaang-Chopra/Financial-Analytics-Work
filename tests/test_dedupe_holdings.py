"""Tests for scripts/dedupe_holdings.py keep-latest dedupe logic (Task A3).

Runs against an in-memory SQLite fixture — no live PostgreSQL needed.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from dedupe_holdings import (  # noqa: E402
    compute_delete_ids,
    run_dedupe,
)


@pytest.fixture()
def sqlite_engine(tmp_path):
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE portfolio_holdings (
                    id VARCHAR(36) PRIMARY KEY,
                    snapshot_id VARCHAR(36) NOT NULL,
                    instrument_id VARCHAR(36),
                    security_name TEXT NOT NULL,
                    isin TEXT,
                    sector TEXT,
                    asset_class TEXT,
                    quantity NUMERIC,
                    market_value NUMERIC,
                    market_value_currency VARCHAR(8),
                    percentage_to_nav NUMERIC,
                    coupon NUMERIC,
                    maturity_date DATE,
                    rating TEXT,
                    metadata_json JSON NOT NULL DEFAULT '{}',
                    created_at TIMESTAMP NOT NULL
                )
                """
            )
        )
    return engine


def _insert(engine, hid, snap, name, isin, created_at):
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO portfolio_holdings "
                "(id, snapshot_id, instrument_id, security_name, isin, market_value_currency, metadata_json, created_at) "
                "VALUES (:id, :snap, NULL, :name, :isin, 'INR', '{}', :created)"
            ),
            {"id": hid, "snap": snap, "name": name, "isin": isin, "created": created_at},
        )


def _rows_for(engine, snap, name):
    with engine.connect() as conn:
        return [
            tuple(r)
            for r in conn.execute(
                text(
                    "SELECT id FROM portfolio_holdings "
                    "WHERE snapshot_id=:s AND security_name=:n ORDER BY id"
                ),
                {"s": snap, "n": name},
            ).all()
        ]


def test_null_isin_group_keeps_latest_created_at(sqlite_engine, tmp_path):
    e = sqlite_engine
    _insert(e, "a-old", "s1", "TREPS", None, "2026-08-20 10:00:00")
    _insert(e, "b-new", "s1", "TREPS", None, "2026-08-21 12:00:00")
    _insert(e, "c-mid", "s1", "TREPS", None, "2026-08-20 18:00:00")

    report = run_dedupe(e, backup_dir=tmp_path)

    assert report["deleted"] == 2
    assert report.get("aborted") is not True
    assert _rows_for(e, "s1", "TREPS") == [("b-new",)]


def test_tie_on_created_at_breaks_by_larger_id(sqlite_engine, tmp_path):
    e = sqlite_engine
    _insert(e, "t-aaa", "s1", "GOLD", None, "2026-08-21 09:00:00")
    _insert(e, "t-zzz", "s1", "GOLD", None, "2026-08-21 09:00:00")  # same ts

    report = run_dedupe(e, backup_dir=tmp_path)
    assert report["deleted"] == 1
    assert _rows_for(e, "s1", "GOLD") == [("t-zzz",)]  # deterministic tiebreak

    with e.connect() as conn:
        ids, actions = compute_delete_ids(conn)
    assert ids == []


def test_same_nonnull_isin_exact_duplicates_are_removed(sqlite_engine, tmp_path):
    e = sqlite_engine
    _insert(e, "x-1", "s1", "HDFC Bank", "INE005A01028", "2026-08-19 08:00:00")
    _insert(e, "x-2", "s1", "HDFC Bank", "INE005A01028", "2026-08-22 08:00:00")

    report = run_dedupe(e, backup_dir=tmp_path)
    assert report["deleted"] == 1
    assert _rows_for(e, "s1", "HDFC Bank") == [("x-2",)]


def test_distinct_nonnull_isins_are_not_touched(sqlite_engine, tmp_path):
    """Same name + different ISINs is legitimate under the composite key."""
    e = sqlite_engine
    _insert(e, "d-1", "s1", "Reliance", "INE002A01018", "2026-08-19 08:00:00")
    _insert(e, "d-2", "s1", "Reliance", "INE002A01026", "2026-08-19 09:00:00")

    report = run_dedupe(e, backup_dir=tmp_path)
    assert report["deleted"] == 0
    assert sorted(_rows_for(e, "s1", "Reliance")) == [("d-1",), ("d-2",)]
    assert report["index_created"] is True


def test_partial_index_blocks_new_null_isin_dupes(sqlite_engine, tmp_path):
    e = sqlite_engine
    _insert(e, "i-1", "s1", "CCIL", None, "2026-08-21 09:00:00")
    run_dedupe(e, backup_dir=tmp_path)
    # The partial unique index now exists and must reject a second NULL-ISIN row.
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        _insert(e, "i-2", "s1", "CCIL", None, "2026-08-22 09:00:00")


def test_re_run_is_idempotent(sqlite_engine, tmp_path):
    e = sqlite_engine
    _insert(e, "r-1", "s1", "TREPS", None, "2026-08-20 10:00:00")
    _insert(e, "r-2", "s1", "TREPS", None, "2026-08-21 10:00:00")

    first = run_dedupe(e, backup_dir=tmp_path)
    second = run_dedupe(e, backup_dir=tmp_path)

    assert first["deleted"] == 1
    assert second["deleted"] == 0
    assert _rows_for(e, "s1", "TREPS") == [("r-2",)]


def test_backup_csv_contains_all_group_rows(sqlite_engine, tmp_path):
    e = sqlite_engine
    _insert(e, "k-1", "s1", "TREPS", None, "2026-08-20 10:00:00")
    _insert(e, "k-2", "s1", "TREPS", None, "2026-08-21 10:00:00")

    report = run_dedupe(e, backup_dir=tmp_path)
    backup = Path(report["backup_path"])
    assert backup.exists()

    with backup.open() as fh:
        rows = list(csv.DictReader(fh))
    backed_ids = {r["id"] for r in rows}
    assert backed_ids == {"k-1", "k-2"}
    action = {r["id"]: r["planned_action"] for r in rows}
    assert action == {"k-1": "delete", "k-2": "keep"}


def test_abort_when_child_fk_references_holdings(sqlite_engine, tmp_path, monkeypatch):
    e = sqlite_engine
    _insert(e, "f-1", "s1", "TREPS", None, "2026-08-20 10:00:00")
    _insert(e, "f-2", "s1", "TREPS", None, "2026-08-21 10:00:00")
    monkeypatch.setattr(
        sys.modules["dedupe_holdings"],
        "find_inbound_foreign_keys",
        lambda engine, conn: [
            {
                "child_table": "hold_valuation_history",
                "child_column": "holding_id",
                "constraint_name": "fk_hvh_holding",
            }
        ],
    )

    report = run_dedupe(e, backup_dir=tmp_path)

    assert report["aborted"] is True
    assert report.get("deleted", 0) in (0, None)
    # Nothing was deleted despite duplicates existing.
    assert sorted(_rows_for(e, s1 := "s1", "TREPS")) == [("f-1",), ("f-2",)]
