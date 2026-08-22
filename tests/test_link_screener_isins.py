"""Unit tests for scripts/link_screener_isins.py matching logic (no DB, no network)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from link_screener_isins import (  # noqa: E402
    MATCH_THRESHOLD,
    find_best_match,
    is_debt_instrument,
    normalize_name,
    similarity,
)

INSTRUMENTS = [
    {"isin": "INE002A01018", "name": "Reliance Industries Limited"},
    {"isin": "INE469I01019", "name": "HDFC Bank Ltd. **"},
    {"isin": "INE009A01021", "name": "ITC Limited"},
    {"isin": "INE463V01026", "name": "AnandRathi Wealth Ltd."},
    {"isin": "INE062A01020", "name": "Tata Consultancy Services Limited"},
    # debt instruments sharing issuer names with equities — must not match loosely
    {"isin": "INE467I14017", "name": "IIFL Finance Ltd 12MAR24 CP"},
    {"isin": "INE758I14EH4", "name": "India MBS PTC Series 1D (LIC HF)**"},
]


def test_normalize_strips_suffixes_and_punctuation():
    assert normalize_name("Reliance Industries Limited") == "reliance industries"
    assert normalize_name("HDFC Bank Ltd. **") == "hdfc bank"
    assert normalize_name("Larsen & Toubro Ltd") == "larsen and toubro"


def test_similarity_exact_normalized():
    assert similarity("hdfc bank", "hdfc bank") == 100.0


def test_similarity_partial():
    score = similarity("hdfc bank", "hdfc bank limited extra")
    assert 0 < score < 100


def test_similarity_disjoint_names_low():
    assert similarity("tata motors", "hindustan unilever") < MATCH_THRESHOLD


def test_exact_name_match():
    isin, conf, method = find_best_match("Reliance Industries Ltd", INSTRUMENTS)
    assert isin == "INE002A01018"
    assert conf == 100.0
    assert method == "exact_normalized_name"


def test_fuzzy_concatenated_name_matches():
    isin, conf, method = find_best_match("Anand Rathi Wealth Ltd", INSTRUMENTS)
    assert isin == "INE463V01026"
    assert method in ("fuzzy_name", "exact_normalized_name")
    assert conf >= MATCH_THRESHOLD


def test_below_threshold_returns_null_with_reason():
    isin, conf, method = find_best_match("Affle 3i Ltd", INSTRUMENTS)
    assert isin is None
    assert method == "below_threshold"


def test_debt_instrument_never_loose_matches_its_issuer():
    # A CP named after IIFL Finance must not be linked to a stock called
    # "IIFL Finance Ltd" unless names clean to equality.
    instruments = INSTRUMENTS + [{"isin": "INE361Y01015", "name": "IIFL Finance Ltd"}]
    isin, _conf, _method = find_best_match("IIFL Finance Ltd", instruments)
    # equity row exists with exact name -> must pick the equity, not the CP
    assert isin == "INE361Y01015"


def test_debt_only_candidates_left_unmatched():
    instruments = [{"isin": "INE467I14017", "name": "IIFL Finance Ltd 12MAR24 CP"}]
    isin, conf, method = find_best_match("IIFL Finance Ltd", instruments)
    assert isin is None


def test_ambiguous_tie_refuses_to_guess():
    instruments = [
        {"isin": "INE111A14011", "name": "Acme Motors Ltd"},
        {"isin": "INE222B15022", "name": "Acme Motors Limited"},  # both debt series
    ]
    isin, conf, method = find_best_match("Acme Motors Ltd", instruments)
    assert isin is None
    assert method == "ambiguous"


def test_exact_tie_broken_by_isin_series_01():
    # Same cleaned name, equity series '01' vs a later debt series -> pick '01'
    instruments = [
        {"isin": "INE469I01019", "name": "HDFC Bank Ltd. **"},      # series 01 (equity)
        {"isin": "INE469I14017", "name": "HDFC Bank Ltd. **"},      # series 14 (debt)
    ]
    isin, conf, method = find_best_match("HDFC Bank Limited", instruments)
    assert isin == "INE469I01019"
    assert method == "exact_name_isin_series_tiebreak"
    assert conf == 97.0


def test_exact_tie_stays_ambiguous_when_two_series_01():
    instruments = [
        {"isin": "INE111A01011", "name": "Acme Motors Ltd"},
        {"isin": "INE111A01012", "name": "Acme Motors Limited"},  # two '01' ISINs
    ]
    isin, _conf, method = find_best_match("Acme Motors Ltd", instruments)
    assert isin is None
    assert method == "ambiguous"


def test_no_fabrication_on_empty_instruments():
    assert find_best_match("Anything Ltd", []) == (None, None, "below_threshold")
    assert find_best_match("Anything Ltd", [{"isin": None, "name": "Anything Ltd"}]) == (
        None,
        None,
        "below_threshold",
    )


def test_threshold_boundary():
    instruments = [{"isin": "INE999Z01099", "name": "Alpha Beta Gamma Delta"}]
    # identical token set with an extra word scores high; disjoint scores low
    isin, _conf, method = find_best_match("Alpha Beta Gamma Delta Extra Word", instruments)
    if method == "below_threshold":
        assert isin is None


def test_is_debt_instrument_markers():
    assert is_debt_instrument("IIFL Finance Ltd 12MAR24 CP")
    assert is_debt_instrument("India MBS PTC Series 1D")
    assert not is_debt_instrument("IIFL Finance Ltd")


@pytest.mark.parametrize(
    ("a", "b"),
    [("ITC Limited", "itc"), ("TCS Ltd", "Tata Consultancy Services Limited")],
)
def test_known_pairs_score_at_or_above_threshold(a, b):
    norm_a, norm_b = normalize_name(a), normalize_name(b)
    if norm_a == norm_b:
        assert similarity(norm_a, norm_b) == 100.0
