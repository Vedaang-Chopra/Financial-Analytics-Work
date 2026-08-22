-- ============================================================================
-- scheme_overlap.sql — Task D2: pairwise fund-similarity primitive
--
-- Computes the overlap coefficient between every unordered pair of schemes
-- that share a quarter:
--
--     overlap(A, B) = |A ∩ B| / min(|A|, |B|)
--
-- where A and B are the sets of DISTINCT non-null ISINs held by each scheme
-- in that quarter. The coefficient lies in [0, 1]; 1.0 means one scheme's
-- ISIN set is a strict subset of the other's.
--
-- NULL-isin holdings: EXCLUDED consistently. Holdings rows with
--   isin IS NULL or an empty/whitespace-only isin never contribute to any
--   set A or B. Rationale: there is no stable cross-scheme identifier for
--   them (the same security name can be spelled differently across AMCs),
--   so including them by name would corrupt the similarity signal. The
--   exclusion is applied identically to both sides of every pair, so the
--   coefficient remains a well-defined set measure over identified
--   securities only. n_common / n_min therefore refer to ISIN-identified
--   holdings only.
--
-- Snapshot selection: a scheme may have multiple snapshots within one
-- quarter (raw month-end filings). For each (scheme_id, qtr) we use the
-- LATEST reporting_date snapshot (ties broken by latest created_at), so
-- each scheme contributes exactly one set per quarter.
--
-- Semantics of stored columns:
--   overlap_pct — the overlap coefficient as a FRACTION in [0, 1]
--                 (multiply by 100 for a percentage).
--   n_common    — |A ∩ B| (distinct common ISINs)
--   n_min       — min(|A|, |B|)
--
-- Scale check before running (pair-count math): pairs per quarter =
-- C(n_schemes, 2). With ~389 schemes the worst case is C(389, 2) ≈ 75K
-- pairs for a single quarter; actual data has at most 241 schemes in any
-- one quarter (~29K pairs) and <50K pairs across ALL quarters combined,
-- so full pairwise computation is cheap and no >=5-common-holdings
-- restriction is needed. scripts/compute_scheme_overlap.py re-checks this
-- math and reports it at runtime.
--
-- Idempotent: TRUNCATE-and-recompute.
-- Applied by: scripts/compute_scheme_overlap.py
-- ============================================================================

CREATE TABLE IF NOT EXISTS scheme_overlap (
    qtr         date NOT NULL,
    scheme_a    uuid NOT NULL,
    scheme_b    uuid NOT NULL,
    overlap_pct numeric NOT NULL,
    n_common    integer NOT NULL,
    n_min       integer NOT NULL,
    PRIMARY KEY (qtr, scheme_a, scheme_b),
    CHECK (scheme_a < scheme_b),
    CHECK (overlap_pct >= 0 AND overlap_pct <= 1),
    CHECK (n_common <= n_min)
);

TRUNCATE TABLE scheme_overlap;

CREATE INDEX IF NOT EXISTS ix_scheme_overlap_qtr      ON scheme_overlap (qtr);
CREATE INDEX IF NOT EXISTS ix_scheme_overlap_scheme_a ON scheme_overlap (scheme_a);
CREATE INDEX IF NOT EXISTS ix_scheme_overlap_scheme_b ON scheme_overlap (scheme_b);

WITH snap_q AS (
    SELECT
        s.id AS snapshot_id,
        s.scheme_id,
        date_trunc('quarter', s.reporting_date)::date AS qtr,
        row_number() OVER (
            PARTITION BY s.scheme_id, date_trunc('quarter', s.reporting_date)
            ORDER BY s.reporting_date DESC, s.created_at DESC
        ) AS rn
    FROM portfolio_snapshots s
    WHERE s.scheme_id IS NOT NULL
),
scheme_sets AS (
    -- One distinct-ISIN set per (qtr, scheme); NULL/blank ISINs excluded.
    SELECT
        sq.qtr,
        sq.scheme_id,
        array_agg(DISTINCT h.isin ORDER BY h.isin) AS isins,
        count(DISTINCT h.isin)::int                AS n_isins
    FROM snap_q sq
    JOIN portfolio_holdings h ON h.snapshot_id = sq.snapshot_id
    WHERE sq.rn = 1
      AND h.isin IS NOT NULL
      AND btrim(h.isin) <> ''
    GROUP BY sq.qtr, sq.scheme_id
)
INSERT INTO scheme_overlap (qtr, scheme_a, scheme_b, overlap_pct, n_common, n_min)
SELECT
    a.qtr,
    a.scheme_id AS scheme_a,
    b.scheme_id AS scheme_b,
    round(common.n_common::numeric / least(a.n_isins, b.n_isins), 6) AS overlap_pct,
    common.n_common,
    least(a.n_isins, b.n_isins) AS n_min
FROM scheme_sets a
JOIN scheme_sets b
  ON a.qtr = b.qtr AND a.scheme_id < b.scheme_id
CROSS JOIN LATERAL (
    SELECT count(*)::int AS n_common
    FROM unnest(a.isins) AS x
    WHERE x = ANY (b.isins)
) AS common;
