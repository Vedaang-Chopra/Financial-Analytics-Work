"""Tests for the Alembic migration foundation (task C1)."""
from __future__ import annotations

import configparser
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = REPO_ROOT / "alembic.ini"
VERSIONS_DIR = REPO_ROOT / "migrations" / "versions"


def test_alembic_ini_exists_and_loads() -> None:
    assert ALEMBIC_INI.exists(), "alembic.ini missing at repo root"
    parser = configparser.RawConfigParser()
    assert parser.read(ALEMBIC_INI), "alembic.ini could not be parsed"
    assert parser.has_section("alembic"), "alembic.ini missing [alembic] section"
    script_location = parser.get("alembic", "script_location")
    # %(here)s is interpolated by alembic, not configparser by default
    resolved = script_location.replace("%(here)s", str(REPO_ROOT))
    assert (Path(resolved) / "env.py").exists(), f"env.py not found at {resolved}"


def test_env_py_targets_project_metadata() -> None:
    env_py = (REPO_ROOT / "migrations" / "env.py").read_text(encoding="utf-8")
    assert "mutual_fund_ingestion.agent.db" in env_py
    assert "DATABASE_URL" in env_py


def test_single_head_revision_exists() -> None:
    version_files = sorted(VERSIONS_DIR.glob("*.py"))
    assert version_files, "no revision files under migrations/versions/"

    revisions: dict[str, str | None] = {}
    for path in version_files:
        source = path.read_text(encoding="utf-8")
        rev_id = None
        down_rev = None
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith("revision"):
                rev_id = _extract_literal(stripped)
            elif stripped.startswith("down_revision"):
                down_rev = _extract_literal(stripped)
        assert rev_id is not None, f"{path.name} missing revision id"
        revisions[rev_id] = down_rev

    child_revs = {d for d in revisions.values() if d}
    heads = [r for r in revisions if r not in child_revs]
    assert len(heads) == 1, f"expected exactly 1 head revision, found: {heads}"


def _extract_literal(line: str) -> str | None:
    """Extract the assigned literal from e.g. `revision: str = 'abc'`."""
    _, _, value = line.partition("=")
    value = value.strip().rstrip(",").strip()
    for quote in ("'", '"'):
        if value.startswith(quote) and value.endswith(quote):
            return value[1:-1]
    if value.lower() == "none":
        return None
    return value or None
