"""Alembic environment for the mutual_funds PostgreSQL database.

Resolves the database URL the same way as the ingestion scripts
(see scripts/backfill_amfi_nav_history.py): DATABASE_URL env var,
falling back to the local default.
"""
from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make the repo root importable when alembic is invoked from anywhere.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mutual_fund_ingestion.agent.db import Base  # noqa: E402

from db_config import generic_database_url  # noqa: E402

# Importing agent.db registers all ORM models on Base.metadata.
target_metadata = Base.metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def get_database_url() -> str:
    # -x database_url=... takes precedence (scratch-DB verification),
    # then DATABASE_URL/MF_DATABASE_URL env vars or api.env (db_config.py).
    url = context.get_x_argument(as_dictionary=True).get("database_url")
    if url:
        return url
    return generic_database_url()


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL without a DB connection)."""
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode with an Engine + connection."""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_database_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
