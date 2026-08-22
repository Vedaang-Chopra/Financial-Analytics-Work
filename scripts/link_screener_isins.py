#!/usr/bin/env python
"""Link screener.stocks -> mutual_funds.instruments via ISIN.

Populates three additive columns on screener.stocks:
  isin             TEXT   NULL  - matched ISIN from mutual_funds.instruments
  match_confidence REAL   NULL  - 0..100 score of the best match
  match_method     TEXT   NULL  - how it matched ('exact_normalized_name',
                                  'fuzzy_name', or 'ambiguous'/'below_threshold'
                                  provenance for NULLs)

Matching strategy (never fabricates):
  1. Exact match on normalized name (confidence 100).
  2. Fuzzy fallback: token-set overlap + difflib sequence ratio (score <85 -> NULL).
  3. Ambiguity guard: if the top two candidate scores tie above the threshold,
     no ISIN is written (method='ambiguous') rather than guessing.

Idempotent: re-running recomputes every row deterministically.
Usage:
    ./financial_env/bin/python scripts/link_screener_isins.py [--dry-run]
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path

import psycopg2

REPO_ROOT = Path(__file__).resolve().parent.parent

MUTUAL_FUNDS_DSN = "postgresql://vlmrouter:vlmrouter@localhost:5432/mutual_funds"
SCREENER_DSN = "postgresql://vlmrouter:vlmrouter@localhost:5432/screener"

MATCH_THRESHOLD = 85.0

# Tokens stripped from company names before comparison.
_SUFFIX_TOKENS = {
    "ltd", "ltd.", "limited", "lte", "co", "co.", "company", "corp",
    "corp.", "corporation", "inc", "inc.", "plc", "llp", "the",
}
# Debt-instrument markers: an instrument whose raw name contains these is a
# bond/CP/NCD/PTC, not the equity — never link it to a screener equity stock
# unless its cleaned name still equals the stock name exactly.
_DEBT_MARKER_RE = re.compile(
    r"\b(cp|ncd|ptc|bond|debenture|sr|series|tranche)\b|\d{2}[a-z]{3}\d{2,4}\b",
    re.IGNORECASE,
)


def normalize_name(name: str) -> str:
    """Normalize a company name to a comparable token string."""
    s = name.lower().strip()
    s = s.replace("&", " and ")
    # '**' and other footnote markers
    s = s.replace("*", " ")
    # punctuation -> spaces
    s = re.sub(r"[^a-z0-9]+", " ", s)
    tokens = [t for t in s.split() if t]
    # drop pure-number tokens (dates, series numbers)
    tokens = [t for t in tokens if not t.isdigit()]
    # drop corporate-suffix tokens (keep at least one token)
    trimmed = [t for t in tokens if t not in _SUFFIX_TOKENS]
    return " ".join(trimmed if trimmed else tokens)


def similarity(stock_norm: str, inst_norm: str) -> float:
    """0..100 similarity between two normalized names.

    Combines token-set Jaccard with difflib SequenceMatcher so both
    word-order-independent overlap and character-level closeness count.
    """
    if not stock_norm or not inst_norm:
        return 0.0
    if stock_norm == inst_norm:
        return 100.0
    a_tokens, b_tokens = set(stock_norm.split()), set(inst_norm.split())
    union = a_tokens | b_tokens
    jaccard = len(a_tokens & b_tokens) / len(union) * 100.0 if union else 0.0
    seq = difflib.SequenceMatcher(None, stock_norm, inst_norm).ratio() * 100.0
    return round(max(jaccard, seq), 2)


def is_debt_instrument(raw_name: str) -> bool:
    return bool(_DEBT_MARKER_RE.search(raw_name))


def isin_series(isin: str) -> str | None:
    """Indian ISINs (INE…): characters 8-9 encode the security series.

    '01' is the issuer's primary/equity series; higher numbers are later
    issues (NCDs, CPs). Empirically verified against this DB: every
    screener-equity match carries series '01'.
    """
    if isinstance(isin, str) and len(isin) == 12:
        return isin[7:9]
    return None


def find_best_match(
    stock_name: str,
    instruments: list[dict],
    threshold: float = MATCH_THRESHOLD,
):
    """Return (isin, confidence, method) for one stock, or (None, score_or_None, reason).

    `instruments` is a list of {"isin": str|None, "name": str} dicts.
    Never returns an isin below `threshold`; ties above threshold are reported
    as ambiguous instead of guessed.
    """
    stock_norm = normalize_name(stock_name)

    scored = []
    for inst in instruments:
        isin = inst.get("isin")
        if not isin:
            continue
        inst_norm = normalize_name(inst["name"])
        score = similarity(stock_norm, inst_norm)
        if score < threshold:
            continue
        # Debt instruments must match essentially exactly (cleaned names equal)
        # to be eligible — avoids linking a CP/NCD to the issuing company.
        if is_debt_instrument(inst["name"]) and score < 99.99:
            continue
        scored.append((score, isin, inst["name"]))

    if not scored:
        return (None, None, "below_threshold")

    scored.sort(key=lambda x: (-x[0], x[1]))
    # Exact matches can be ambiguous if several ISINs share the cleaned name
    # (equity + NCD series of the same issuer). Break ties by ISIN series:
    # series '01' is the issuer's primary (equity) series; later series are
    # debt. If the tie still stands, refuse to guess.
    exact_hits = [s for s in scored if s[0] >= 99.99]
    if len(exact_hits) > 1 and len({s[1] for s in exact_hits}) > 1:
        by_series = sorted(exact_hits, key=lambda s: isin_series(s[1]) or "zz")
        lowest = isin_series(by_series[0][1])
        if lowest == "01" and sum(1 for s in exact_hits if isin_series(s[1]) == "01") == 1:
            return (by_series[0][1], 97.0, "exact_name_isin_series_tiebreak")
        return (None, 100.0, "ambiguous")

    best_score, best_isin, best_name = scored[0]

    if best_score >= 99.99:
        return (best_isin, best_score, "exact_normalized_name")

    # Ambiguity guard: another instrument ties (or nearly ties) the best fuzzy
    # score — refuse to guess.
    if len(scored) > 1 and scored[1][0] >= best_score - 0.01:
        return (None, best_score, "ambiguous")

    return (best_isin, best_score, "fuzzy_name")


def fetch_instruments(dsn: str) -> list[dict]:
    with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("SELECT isin, name FROM instruments WHERE isin IS NOT NULL AND isin <> ''")
        return [{"isin": r[0], "name": r[1]} for r in cur.fetchall()]


def fetch_stocks(dsn: str) -> list[dict]:
    with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("SELECT id, slug, name FROM stocks ORDER BY id")
        return [{"id": r[0], "slug": r[1], "name": r[2]} for r in cur.fetchall()]


def ensure_columns(dsn: str) -> None:
    with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("ALTER TABLE stocks ADD COLUMN IF NOT EXISTS isin TEXT")
        cur.execute("ALTER TABLE stocks ADD COLUMN IF NOT EXISTS match_confidence REAL")
        cur.execute("ALTER TABLE stocks ADD COLUMN IF NOT EXISTS match_method TEXT")


def apply_matches(dsn: str, results: list[dict], dry_run: bool) -> int:
    """Write match results back to stocks. Returns rows updated."""
    updated = 0
    with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
        for r in results:
            cur.execute(
                """
                UPDATE stocks
                   SET isin = %s,
                       match_confidence = %s,
                       match_method = %s
                 WHERE id = %s
                """,
                (r["isin"], r["match_confidence"], r["match_method"], r["id"]),
            )
            updated += cur.rowcount
    return updated


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="Compute and print stats without writing")
    args = ap.parse_args(argv)

    instruments = fetch_instruments(MUTUAL_FUNDS_DSN)
    stocks = fetch_stocks(SCREENER_DSN)
    print(f"instruments with ISIN: {len(instruments)}")
    print(f"screener stocks:       {len(stocks)}")

    results = []
    for st in stocks:
        isin, conf, method = find_best_match(st["name"], instruments)
        results.append({**st, "isin": isin, "match_confidence": conf, "match_method": method})

    matched = sum(1 for r in results if r["isin"])
    methods: dict[str, int] = {}
    for r in results:
        methods[r["match_method"]] = methods.get(r["match_method"], 0) + 1

    print("\n--- match stats ---")
    print(f"matched:   {matched}/{len(results)} ({matched / len(results):.1%})")
    for m, n in sorted(methods.items(), key=lambda kv: -kv[1]):
        print(f"  {m:<22} {n}")

    unmatched = [r for r in results if not r["isin"]]
    if unmatched:
        print("\nunmatched stocks:")
        for r in unmatched:
            print(f"  {r['slug']:<14} {r['name']}  (method={r['match_method']})")

    borderline = sorted(
        (r for r in results if r["match_method"] == "fuzzy_name"),
        key=lambda r: r["match_confidence"],
    )
    if borderline:
        print("\nlowest-confidence fuzzy matches (review these):")
        for r in borderline[:10]:
            print(f"  {r['name']} -> {r['isin']} @ {r['match_confidence']}")

    if args.dry_run:
        print("\n[dry-run] no changes written")
        return 0

    ensure_columns(SCREENER_DSN)
    n = apply_matches(SCREENER_DSN, results, args.dry_run)
    print(f"\nwrote {n} rows to screener.stocks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
