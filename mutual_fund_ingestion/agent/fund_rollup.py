"""Fund-level rollup resolver (plan task E1).

AMFI scheme codes are plan-level: "Parag Parikh Flexi Cap Fund-Direct-Growth"
and "...-Regular-IDCW" are distinct ``schemes`` rows holding identical
portfolios. Counting them separately inflates consensus by up to ~2x per
dual-plan fund. This module derives the missing fund-level entity by stripping
plan/option tokens from the scheme name and grouping within an AMC.

Ambiguity policy (deliberately conservative — over-merging creates fake
consensus, under-merging just leaves counts conservative):
  * Only schemes within the SAME AMC (or both amc_id NULL) group together.
  * A base-name group merges into one fund only if member schemes' holding
    overlap in their latest shared snapshot is >= MIN_HOLDING_OVERLAP (0.90),
    or holding data is unavailable for all members (nothing to contradict).
  * Ambiguous groups are left unlinked and reported, never force-merged.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

# Tokens that mark plan/option/structure variants of one fund. Stripped from
# the scheme name to recover the fund's base name.
_PLAN_TOKEN_RE = re.compile(
    r"\b("
    r"direct|regular|idcw|reinvestment|payout|dividend|growth"
    r"|\d{1,2}\s*%|"                      # "10%", "5 %"
    r"monthly|quarterly|annual|weekly|"   # frequency variants
    r"plan|option"
    r")\b",
    re.IGNORECASE,
)

_WHITESPACE_RE = re.compile(r"[^a-z0-9]+")

# Trailing connector words left dangling after token stripping ("... fund plan").
_TRAILING_FILLER_RE = re.compile(r"[\s\-–]*(?:\b(?:plan|option|scheme)\b[\s\-–]*)+$", re.IGNORECASE)


# Parenthetical descriptors ("(An open-ended dynamic equity scheme investing
# ...)") are prose, not identity — dropped BEFORE token stripping so verbose
# disclosure names group with clean AMFI master names.
_PAREN_RE = re.compile(r"\([^)]*\)")


def normalize_base_name(scheme_name: str) -> str:
    """Strip parentheticals + plan/option tokens and normalize -> fund base key."""
    name = _PAREN_RE.sub(" ", scheme_name)
    name = _PLAN_TOKEN_RE.sub(" ", name)
    key = _WHITESPACE_RE.sub(" ", name.casefold()).strip()
    return _TRAILING_FILLER_RE.sub("", " " + key + " ").strip()


def base_display_name(scheme_name: str) -> str:
    """Human-readable base name: strip tokens, tidy whitespace/punctuation."""
    name = _PLAN_TOKEN_RE.sub(" ", scheme_name)
    name = re.sub(r"\s+", " ", name)
    name = re.sub(r"\(\s*[)\-–\s]*", "(", name)   # "( -" / "( )" debris from stripping
    name = re.sub(r"[\-–\s]+\)", ")", name)       # dangling closers
    name = name.replace("()", "").strip(" -–")
    name = re.sub(r"\s+\)", ")", name)
    return _TRAILING_FILLER_RE.sub("", name).strip(" -–( ") or scheme_name.strip()


def group_schemes_by_base(
    schemes: list[dict[str, Any]],
) -> dict[tuple[str | None, str], list[dict[str, Any]]]:
    """Group scheme dicts ({id, scheme_name, amc_id}) by (amc_id, base).

    Schemes with NULL amc_id only group among themselves (key (None, base)):
    a NULL-AMC scheme must never merge into an identified AMC's fund.
    """
    groups: dict[tuple[str | None, str], list[dict[str, Any]]] = defaultdict(list)
    for s in schemes:
        key = (s.get("amc_id"), normalize_base_name(s["scheme_name"]))
        groups[key].append(s)
    return groups


def holding_overlap(
    holdings_a: set[str] | None, holdings_b: set[str] | None
) -> float | None:
    """Overlap coefficient |A∩B| / min(|A|,|B|); None when either side unknown.

    Empty-but-known portfolios count as known (overlap of two empties = 1.0:
    no contradiction). Unknown is represented by passing None explicitly.
    """
    if holdings_a is None or holdings_b is None:
        return None
    n_min = min(len(holdings_a), len(holdings_b))
    if n_min == 0:
        return 1.0
    return len(holdings_a & holdings_b) / n_min


MIN_HOLDING_OVERLAP = 0.90


def resolve_group_merge(
    overlaps: list[float | None],
    min_overlap: float = MIN_HOLDING_OVERLAP,
) -> bool:
    """Decide whether a base-name group may merge into one fund.

    Rule: every KNOWN pairwise overlap must be >= min_overlap; groups whose
    pairs are all unknown have nothing to contradict and merge (conservative
    in practice because same-AMC + same-base-name rarely differs).
    """
    known = [o for o in overlaps if o is not None]
    if not known:
        return True
    return all(o >= min_overlap for o in known)
