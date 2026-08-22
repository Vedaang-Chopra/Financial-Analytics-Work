#!/usr/bin/env python3
"""
T2-final: Backfill schemes.category / sub_category from unioned multi-year
Wayback Machine archives of the AMFI rolling scheme master.

Source files: data/tmp/t2_wb_<YYYYMM>.csv — monthly snapshots of
https://portal.amfiindia.com/DownloadSchemeData_Po.aspx?MF=0 fetched from
web.archive.org (one per capture month, 2015-2025). ~10 captures are
truncated at exactly 1MB *at the archive itself* (x-archive-orig-content-length
= 1048576, "wayback content truncated by length"); their partial rows still
contribute to the union.

Matching passes (history-preserving; only NULL/'' categories are filled,
never overwritten; no deletes):
  1. scheme_code  -> unioned code map, later capture month wins on conflict.
                     provenance: wayback_code
  2. exact normalized name (DB normalizer: lowercase, non-alnum -> space,
     collapse, drop standalone 'mf').  provenance: wayback_name
  3. conservative fuzzy name (difflib >= 0.87 raw & stopword-stripped,
     unanimity of category among near-best candidates, >= 2 shared tokens,
     parser-garbage prefixes and FMP/series-numbered plans excluded).
     provenance: wayback_fuzzy (score + matched key + source month in
     schemes.metadata_json for audit)
  4. keyword rules -> SEBI-style category tokens (Gilt/Liquid/ELSS/...).
     provenance: keyword_rule — downstream MUST treat this as inferred,
     not ground truth.

Every update writes {"category_provenance": ..., ...} into metadata_json.

Usage:
  ./financial_env/bin/python scripts/backfill_t2_categories_wayback.py [--dry-run]
"""

import argparse
import csv
import glob
import gzip
import io
import json
import os
import re
import sys
from datetime import datetime, timezone
from difflib import SequenceMatcher

import psycopg2
import psycopg2.extras

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVE_GLOB = os.path.join(REPO_ROOT, "data", "tmp", "t2_wb_2[0-9][0-9][0-9][0-9][0-9].csv")
DB_DSN = "postgresql://vlmrouter:vlmrouter@localhost:5432/mutual_funds"


def open_archive(path):
    """Open an archive CSV; transparently decompress gzip-wrapped captures."""
    with open(path, "rb") as f:
        head = f.read(2)
    if head == b"\x1f\x8b":
        return io.TextIOWrapper(gzip.GzipFile(fileobj=open(path, "rb"), mode="rb"),
                                encoding="utf-8-sig")
    return open(path, newline="", encoding="utf-8-sig")


def normalize_name(name: str) -> str:
    """Lowercase, non-alphanumerics -> space, collapse whitespace."""
    s = re.sub(r"[^a-z0-9]+", " ", (name or "").lower())
    return re.sub(r"\s+", " ", s).strip()


def db_normalize_name(name: str) -> str:
    """DB normalizer additionally drops the standalone token 'mf'
    (verified: 'LIC NOMURA MF LIQUID FUND' -> 'lic nomura liquid fund')."""
    s = normalize_name(name)
    return re.sub(r"\s+", " ", re.sub(r"\bmf\b", "", s)).strip()


def load_archive_maps():
    """Union all monthly archives into code-> and db-normalized-name-> maps."""
    code_map = {}    # code -> (category, sub_category, yyyymm)
    name_map = {}    # db-normalized name -> (category, sub_category, yyyymm)
    files = sorted(glob.glob(ARCHIVE_GLOB))
    if not files:
        sys.exit(f"No archive files found at {ARCHIVE_GLOB}")
    # Sorted by YYYYMM in filename so later months win conflicts deterministically.
    for path in files:
        base = os.path.basename(path)
        m = re.search(r"(\d{6})", base)
        ym = m.group(1) if m else "000000"
        rows = codes = cats = 0
        try:
            with open_archive(path) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rows += 1
                    code = (row.get("Code") or "").strip()
                    cat = (row.get("Scheme Category") or "").strip()
                    stype = (row.get("Scheme Type") or "").strip()
                    sname = (row.get("Scheme Name") or "").strip()
                    if not cat:
                        continue
                    cats += 1
                    if code:
                        codes += 1
                        prev = code_map.get(code)
                        if prev is None or ym >= prev[2]:
                            code_map[code] = (cat, stype, ym)
                    if sname:
                        key = db_normalize_name(sname)
                        prev = name_map.get(key)
                        if prev is None or ym >= prev[2]:
                            name_map[key] = (cat, stype, ym)
        except Exception as e:  # noqa: BLE001 - report and continue with other months
            print(f"  WARN: failed parsing {base}: {e}")
            continue
        print(f"  {base}: {rows} rows ({codes} coded, categorized)")
    return code_map, name_map


# --------------------------------------------------------------------------
# Pass 3: conservative fuzzy matching
# --------------------------------------------------------------------------
STOPWORDS = {"and", "of", "the", "in", "for"}
FUZZY_MIN_RATIO = 0.87
FUZZY_BAND = 0.03

# Parser-garbage prefixes: rows whose "name" is a document artifact.
GARBAGE_PREFIXES = (
    "name of the scheme", "portfolio", "half yearly", "monthly portfolio",
    "instrument level", "derivatives disclosure", "factsheet",
)
# FMP / series-numbered plans: names like 'fmp series 268 1281d' span debt
# categories by underlying — unmatchable by name without the master row.
SERIES_PLAN_RE = re.compile(r"\bfmp\b|\bseries\s+\d+\b|\b\d{3,4}d\b")


def is_garbage(norm: str) -> bool:
    return norm.startswith(GARBAGE_PREFIXES) or bool(SERIES_PLAN_RE.search(norm))


def build_name_index(name_map):
    """token -> set(name_map keys) for candidate generation."""
    index = {}
    for k in name_map:
        for t in set(k.split()):
            index.setdefault(t, set()).add(k)
    return index


def strip_stopwords(s):
    return " ".join(t for t in s.split() if t not in STOPWORDS)


def fuzzy_match(norm, name_map, index, stripped_cache):
    """Conservative second-chance matcher.

    Candidates: archive names sharing >= 2 tokens with `norm`, ranked by
    shared-token count (capped at 300). Score = max of difflib ratio on raw
    and stopword-stripped strings; a length pre-filter skips hopeless pairs.
    Accept only if best >= FUZZY_MIN_RATIO AND all candidates within
    FUZZY_BAND of the best agree on a single category. Single-token names
    (AMC ticker codes like 'axis100') and garbage/series rows never match.
    Returns (category, sub_category, score, matched_key) or None.
    """
    toks = norm.split()
    if len(toks) < 2 or is_garbage(norm):
        return None
    cand_count = {}
    for t in set(toks):
        for k in index.get(t, ()):
            cand_count[k] = cand_count.get(k, 0) + 1
    if not cand_count:
        return None
    ranked = sorted(cand_count.items(), key=lambda kv: -kv[1])[:300]
    norm_sw = strip_stopwords(norm)
    n_len = len(norm)
    best_r, best_k = 0.0, None
    scored = []
    for k, _shared in ranked:
        k_stripped, k_sw = stripped_cache[k]
        if abs(n_len - len(k_stripped)) > (1 - FUZZY_MIN_RATIO) * max(n_len, len(k_stripped)) * 2:
            continue
        r = max(SequenceMatcher(None, norm, k_stripped).ratio(),
                SequenceMatcher(None, norm_sw, k_sw).ratio())
        scored.append((r, k))
        if r > best_r:
            best_r, best_k = r, k
    if best_k is None or best_r < FUZZY_MIN_RATIO:
        return None
    cats = {name_map[k][0] for r, k in scored if r >= best_r - FUZZY_BAND}
    if len(cats) != 1:
        return None
    hit = name_map[best_k]
    return hit[0], hit[1] or None, best_r, best_k


# --------------------------------------------------------------------------
# Pass 4: keyword rules -> SEBI-style categories (provenance: keyword_rule)
# Ordered, first match wins; deliberately unambiguous tokens only.
# --------------------------------------------------------------------------
KEYWORD_RULES = [
    (r"\bgold etf\b|\bgold exchange traded", "Other Scheme - Gold ETF"),
    (r"\bsilver etf\b", "Other Scheme - Other ETFs"),
    (r"\betf\b", "Other Scheme - Other ETFs"),
    (r"ultra short duration", "Debt Scheme - Ultra Short Duration Fund"),
    (r"\blow duration\b", "Debt Scheme - Low Duration Fund"),
    (r"\bshort duration\b", "Debt Scheme - Short Duration Fund"),
    (r"\bmoney market\b", "Debt Scheme - Money Market Fund"),
    (r"\bovernight\b", "Debt Scheme - Overnight Fund"),
    (r"\bgilt\b", "Debt Scheme - Gilt Fund"),
    (r"\bcorporate bond\b", "Debt Scheme - Corporate Bond Fund"),
    (r"banking and psu|banking psu", "Debt Scheme - Banking and PSU Fund"),
    (r"\bcredit risk\b", "Debt Scheme - Credit Risk Fund"),
    (r"\bfloater\b", "Debt Scheme - Floater Fund"),
    (r"\bdynamic bond\b", "Debt Scheme - Dynamic Bond"),
    (r"\blong duration\b", "Debt Scheme - Long Duration Fund"),
    (r"\bliquid\b", "Debt Scheme - Liquid Fund"),
    (r"\belss\b|tax saver|tax saving", "Equity Scheme - ELSS"),
    (r"\bindex\b.*\bfund\b|\bfund\b.*\bindex\b", "Other Scheme - Index Funds"),
    (r"\barbitrage\b", "Hybrid Scheme - Arbitrage Fund"),
    (r"balanced advantage|dynamic asset allocation", "Hybrid Scheme - Dynamic Asset Allocation or Balanced Advantage"),
    (r"\bequity savings\b", "Hybrid Scheme - Equity Savings"),
    (r"\baggressive hybrid\b", "Hybrid Scheme - Aggressive Hybrid Fund"),
    (r"\bconservative hybrid\b", "Hybrid Scheme - Conservative Hybrid Fund"),
    (r"\bmulti asset\b", "Hybrid Scheme - Multi Asset Allocation"),
    (r"large (and |&) mid ?cap|large mid cap", "Equity Scheme - Large & Mid Cap Fund"),
    (r"\bmid ?cap\b", "Equity Scheme - Mid Cap Fund"),
    (r"\bsmall ?cap\b", "Equity Scheme - Small Cap Fund"),
    (r"\blarge ?cap\b", "Equity Scheme - Large Cap Fund"),
    (r"\bflexi ?cap\b", "Equity Scheme - Flexi Cap Fund"),
    (r"\bmulti ?cap\b", "Equity Scheme - Multi Cap Fund"),
    (r"\bvalue fund\b|\bvalue\b", "Equity Scheme - Value Fund"),
    (r"\bfocused\b", "Equity Scheme - Focused Fund"),
    (r"\bdividend yield\b", "Equity Scheme - Dividend Yield Fund"),
    (r"\bcontra\b", "Equity Scheme - Contra Fund"),
    (r"\bretirement\b", "Solution Oriented Scheme - Retirement Fund"),
    (r"\bchildren\b|children s", "Solution Oriented Scheme - Children s Fund"),
    (r"fund of fund|\bfof\b", "Other Scheme - FoF Domestic"),
]


def keyword_match(norm):
    """Return (category, rule_pattern) for the first rule whose pattern is
    found in the normalized name; None if no rule applies."""
    for pat, cat in KEYWORD_RULES:
        if re.search(pat, norm):
            return cat, pat
    return None


# --------------------------------------------------------------------------
def backup_rows(cur, out_path):
    """Dump every row we might touch (uncategorized) before any UPDATE."""
    cur.execute(
        """
        SELECT id, scheme_code, scheme_name, normalized_scheme_name,
               category, sub_category
        FROM schemes
        WHERE category IS NULL OR category = ''
        ORDER BY id
        """
    )
    n = 0
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "scheme_code", "scheme_name",
                    "normalized_scheme_name", "category", "sub_category"])
        for r in cur.fetchall():
            w.writerow(r)
            n += 1
    print(f"Backup: {n} uncategorized rows -> {out_path}")
    return n


def verify(cur, label):
    """Verbatim coverage counts: overall + panel basis (portfolio_snapshots)."""
    queries = [
        ("overall",
         """SELECT count(*) AS total,
                   count(*) FILTER (WHERE category IS NOT NULL AND category <> '') AS categorized
            FROM schemes"""),
        ("panel_basis",
         """SELECT count(DISTINCT ps.scheme_id) AS panel_total,
                   count(DISTINCT ps.scheme_id) FILTER (
                       WHERE s.category IS NOT NULL AND s.category <> '') AS panel_categorized
            FROM portfolio_snapshots ps
            JOIN schemes s ON s.id = ps.scheme_id"""),
        ("provenance",
         """SELECT COALESCE(metadata_json::jsonb->>'category_provenance', 'pre_existing') AS src,
                   count(*) FROM schemes
                WHERE category IS NOT NULL AND category <> ''
                GROUP BY 1 ORDER BY 2 DESC"""),
    ]
    results = {}
    print(f"\n=== Coverage {label} ===")
    for name, q in queries:
        cur.execute(q)
        rows = cur.fetchall()
        results[name] = rows
        if name == "overall":
            row = rows[0]
            pct = 100.0 * row[1] / row[0] if row[0] else 0.0
            print(f"  overall : {row[1]}/{row[0]} categorized = {pct:.2f}%")
        elif name == "panel_basis":
            row = rows[0]
            pct = 100.0 * row[1] / row[0] if row[0] else 0.0
            print(f"  panel   : {row[1]}/{row[0]} distinct scheme_ids categorized = {pct:.2f}%")
        else:
            print("  provenance of categorized rows:")
            for src, cnt in rows:
                print(f"    {src}: {cnt}")
    print()
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="Compute match counts without writing to the DB.")
    args = ap.parse_args()

    print("Loading Wayback archive maps ...")
    code_map, name_map = load_archive_maps()
    print(f"Unioned maps: {len(code_map)} codes, {len(name_map)} names")

    conn = psycopg2.connect(DB_DSN)
    conn.autocommit = False
    cur = conn.cursor()

    verify(cur, "BEFORE")

    date_tag = datetime.now(timezone.utc).strftime("%Y%m%d")
    backup_path = os.path.join(REPO_ROOT, "data", "tmp",
                               f"backup_t2_categories_{date_tag}.csv")
    backup_rows(cur, backup_path)

    # --- Pass 1: match by scheme_code ------------------------------------
    cur.execute(
        """
        SELECT id, scheme_code FROM schemes
        WHERE (category IS NULL OR category = '')
          AND scheme_code IS NOT NULL
        """
    )
    rows = cur.fetchall()
    updates = []          # (category, sub_category, prov_dict, sid)
    matched_ids = set()
    for sid, code in rows:
        hit = code_map.get((code or "").strip())
        if hit and hit[0]:
            prov = {"category_provenance": "wayback_code",
                    "category_source_month": hit[2]}
            updates.append((hit[0], hit[1] or None, prov, sid))
            matched_ids.add(sid)
    print(f"Pass 1 (scheme_code): {len(updates)}/{len(rows)} matched")

    # --- Pass 2: exact normalized-name fallback ---------------------------
    cur.execute(
        """
        SELECT id, COALESCE(normalized_scheme_name, ''), scheme_code
        FROM schemes
        WHERE category IS NULL OR category = ''
        """
    )
    all_open = cur.fetchall()
    name_hits = 0
    for sid, norm, code in all_open:
        if sid in matched_ids:
            continue
        hit = name_map.get(norm or "")
        if hit and hit[0]:
            prov = {"category_provenance": "wayback_name",
                    "category_source_month": hit[2]}
            updates.append((hit[0], hit[1] or None, prov, sid))
            matched_ids.add(sid)
            name_hits += 1
    print(f"Pass 2 (normalized name): {name_hits} additional matched")

    # --- Pass 3: conservative fuzzy-name fallback -------------------------
    index = build_name_index(name_map)
    stripped_cache = {k: (k, strip_stopwords(k)) for k in name_map}
    fuzzy_hits = 0
    for sid, norm, code in all_open:
        if sid in matched_ids:
            continue
        m = fuzzy_match(norm or "", name_map, index, stripped_cache)
        if m:
            cat, sub, score, key = m
            prov = {"category_provenance": "wayback_fuzzy",
                    "match_score": round(score, 4),
                    "matched_key": key}
            updates.append((cat, sub, prov, sid))
            matched_ids.add(sid)
            fuzzy_hits += 1
    print(f"Pass 3 (fuzzy name >= {FUZZY_MIN_RATIO}): {fuzzy_hits} additional matched")

    # --- Pass 4: keyword-rule fallback (marked inferred) ------------------
    keyword_hits = 0
    for sid, norm, code in all_open:
        if sid in matched_ids:
            continue
        km = keyword_match(norm or "")
        if km:
            cat, pat = km
            prov = {"category_provenance": "keyword_rule", "rule": pat}
            updates.append((cat, None, prov, sid))
            matched_ids.add(sid)
            keyword_hits += 1
    print(f"Pass 4 (keyword rules): {keyword_hits} additional matched")

    total_open = len(all_open)
    print(f"Total planned updates: {len(updates)} of {total_open} open rows")

    if not args.dry_run and updates:
        psycopg2.extras.execute_values(
            cur,
            """
            UPDATE schemes AS s
            SET category = d.category,
                sub_category = COALESCE(NULLIF(s.sub_category, ''), d.sub_category),
                metadata_json = (s.metadata_json::jsonb || d.prov::jsonb)::json,
                updated_at = now()
            FROM (VALUES %s) AS d(category, sub_category, prov, id)
            WHERE s.id = d.id::uuid
              AND (s.category IS NULL OR s.category = '')
            """,
            [(c, s, json.dumps(p), i) for c, s, p, i in updates],
            page_size=1000,
        )
        conn.commit()
        print(f"Committed updates (last page rowcount {cur.rowcount}; "
              f"planned {len(updates)}; backup {os.path.basename(backup_path)})")
    elif args.dry_run:
        conn.rollback()
        print("DRY RUN: no changes committed.")

    verify(cur, "AFTER")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
