-- consensus_panel.sql
-- Materialized view: per-(isin, quarter) fund-holder consensus panel.
--
-- Grain: one row per (isin, qtr) where qtr = date_trunc('quarter', reporting_date).
-- Answers: "which stocks did small-cap funds agree on in quarter t?"
--   e.g. SELECT * FROM consensus_panel
--        WHERE qtr = '2026-07-01' ORDER BY holders_smallcap DESC LIMIT 20;
--
-- Join path: portfolio_holdings -> portfolio_snapshots -> schemes
--            LEFT JOIN instruments (for security names)
--
-- Columns:
--   isin                              holding ISIN
--   qtr                               quarter start date (date_trunc('quarter', reporting_date))
--   instrument_name                   from instruments (may be NULL)
--   holders_total                     count(DISTINCT scheme_id) holding the ISIN in the quarter
--   holders_smallcap                  schemes whose category ILIKE '%small%'
--   holders_largecap / _midcap /
--     _flexicap / _elss / _index      other common category segments (ILIKE-based)
--   holders_other_category            schemes with a non-null category matching no segment above
--   avg_pct_to_nav                    mean percentage_to_nav across distinct schemes
--                                     (scheme-level mean: each scheme counted once)
--   max_pct_to_nav                    largest single-fund position weight
--   latest_aum_cr_basis               how many contributing schemes had a usable AUM figure
--   total_aum_weighted_exposure_cr    sum over schemes of pct_to_nav/100 * latest_aum_cr
--                                     (rupee exposure in Rs crore, using each scheme's most
--                                     recent reported average AUM within the 12 months ending
--                                     at the quarter's last day)
--
-- AUM join rule: for each scheme-quarter, take the latest scheme_aum_history.month_start
-- with month_start <= last day of quarter AND month_start > last day of quarter - 12 months.
-- Schemes without a fresh-enough AUM row contribute pct_to_nav but not weighted exposure.
--
-- Refresh: see scripts/create_consensus_view.py (--refresh, uses REFRESH MATERIALIZED VIEW).
-- This file is safe to re-run as-is: it starts with DROP MATERIALIZED VIEW IF EXISTS.
-- Table/index names are intentionally unqualified so tests can apply this file inside a
-- scratch schema by setting search_path.

DROP MATERIALIZED VIEW IF EXISTS consensus_panel;

CREATE MATERIALIZED VIEW consensus_panel AS
WITH dated_holdings AS (
    SELECT
        ph.isin                                   AS isin,
        date_trunc('quarter', ps.reporting_date)  AS qtr_ts,
        ps.scheme_id                              AS scheme_id,
        s.category                                AS category,
        ph.percentage_to_nav                      AS percentage_to_nav,
        (
            SELECT sah.avg_aum_cr
            FROM scheme_aum_history sah
            WHERE sah.scheme_id = ps.scheme_id
              AND sah.month_start <= (date_trunc('quarter', ps.reporting_date)
                                      + interval '3 months - 1 day')::date
              AND sah.month_start >  (date_trunc('quarter', ps.reporting_date)
                                      + interval '3 months - 1 day')::date - interval '12 months'
            ORDER BY sah.month_start DESC
            LIMIT 1
        )                                          AS latest_aum_cr
    FROM portfolio_holdings ph
    JOIN portfolio_snapshots ps ON ps.id = ph.snapshot_id
    LEFT JOIN schemes s ON s.id = ps.scheme_id
    WHERE ph.isin IS NOT NULL
      AND btrim(ph.isin) <> ''
),
scheme_level AS (
    -- collapse duplicate rows within one scheme-quarter (e.g. partial disclosures)
    SELECT DISTINCT
        isin,
        qtr_ts,
        scheme_id,
        category,
        latest_aum_cr,
        max(percentage_to_nav) AS pct_to_nav
    FROM dated_holdings
    GROUP BY isin, qtr_ts, scheme_id, category, latest_aum_cr
)
SELECT
    sl.isin::text                                                    AS isin,
    sl.qtr_ts::date                                                  AS qtr,
    i.name                                                           AS instrument_name,
    count(DISTINCT sl.scheme_id)                                     AS holders_total,
    count(DISTINCT sl.scheme_id)
        FILTER (WHERE sl.category ILIKE '%small%')                   AS holders_smallcap,
    count(DISTINCT sl.scheme_id)
        FILTER (WHERE sl.category ILIKE '%large%')                   AS holders_largecap,
    count(DISTINCT sl.scheme_id)
        FILTER (WHERE sl.category ILIKE '%mid%')                     AS holders_midcap,
    count(DISTINCT sl.scheme_id)
        FILTER (WHERE sl.category ILIKE '%flexi%'
             OR sl.category ILIKE '%multi%')                         AS holders_flexicap,
    count(DISTINCT sl.scheme_id)
        FILTER (WHERE sl.category ILIKE '%elss%')                    AS holders_elss,
    count(DISTINCT sl.scheme_id)
        FILTER (WHERE sl.category ILIKE '%index%')                   AS holders_index,
    count(DISTINCT sl.scheme_id)
        FILTER (WHERE sl.category IS NOT NULL
                 AND sl.category NOT ILIKE '%small%'
                 AND sl.category NOT ILIKE '%large%'
                 AND sl.category NOT ILIKE '%mid%'
                 AND sl.category NOT ILIKE '%flexi%'
                 AND sl.category NOT ILIKE '%multi%'
                 AND sl.category NOT ILIKE '%elss%'
                 AND sl.category NOT ILIKE '%index%')                AS holders_other_category,
    round(avg(sl.pct_to_nav), 6)                                     AS avg_pct_to_nav,
    max(sl.pct_to_nav)                                               AS max_pct_to_nav,
    count(DISTINCT sl.scheme_id)
        FILTER (WHERE sl.latest_aum_cr IS NOT NULL)                  AS latest_aum_cr_basis,
    round(sum(sl.pct_to_nav * sl.latest_aum_cr / 100.0)::numeric, 4) AS total_aum_weighted_exposure_cr
FROM scheme_level sl
LEFT JOIN instruments i ON i.isin = sl.isin
GROUP BY sl.isin, sl.qtr_ts, i.name;

-- Lookup indexes: single-ISIN history and quarter-wide rankings.
CREATE UNIQUE INDEX IF NOT EXISTS ux_consensus_panel_isin_qtr
    ON consensus_panel (isin, qtr);
CREATE INDEX IF NOT EXISTS ix_consensus_panel_qtr_holders_smallcap
    ON consensus_panel (qtr, holders_smallcap DESC);
