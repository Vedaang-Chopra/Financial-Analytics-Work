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
    merge_parents: set[str] = set()
    for path in version_files:
        source = path.read_text(encoding="utf-8")
        rev_id = None
        down_rev = None
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith("revision") or stripped.startswith("down_revision"):
                which = "rev" if stripped.startswith("revision") else "down"
                # A merge revision's down_revision is a tuple of parent ids,
                # possibly spanning multiple lines; collect all quoted ids.
                joined = stripped
                if "(" in joined and ")" not in joined:
                    k = source.index(stripped)
                    end = source.index(")", k)
                    joined = source[k:end + 1].replace("\n", " ")
                vals = _extract_literals(joined)
                if which == "rev":
                    rev_id = vals[0] if vals else None
                else:
                    down_rev = vals[0] if vals else None
                    merge_parents.update(vals[1:])
        assert rev_id is not None, f"{path.name} missing revision id"
        revisions[rev_id] = down_rev

    child_revs = {d for d in revisions.values() if d} | merge_parents
    heads = [r for r in revisions if r not in child_revs]
    assert len(heads) == 1, f"expected exactly 1 head revision, found: {heads}"


def _extract_literal(line: str) -> str | None:
    """Extract the assigned literal from e.g. `revision: str = 'abc'`."""
    vals = _extract_literals(line)
    return vals[0] if vals else None


def _extract_literals(line: str) -> list[str]:
    """Extract ALL quoted string literals from an assignment line/tuple."""
    import re

    return re.findall(r"""['"]([A-Za-z0-9_]+)['"]""", line)
