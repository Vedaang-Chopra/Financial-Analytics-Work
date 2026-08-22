#!/usr/bin/env python
"""Generate the NAV data exploration notebook (05_nav_data_exploration.ipynb).

Builds a proper nbformat v4.5 notebook that:
  1. Connects to PostgreSQL (DATABASE_URL env var, docker default fallback)
  2. Inspects all 23 tables + row counts
  3. Deep-dives nav_history, schemes, amcs, quarantine, pipeline tables
  4. Interactive Plotly visualizations (inline + saved HTML)
  5. Data-quality report and summary dashboard

Run:  ./financial_env/bin/python scripts/generate_nav_exploration_notebook.py
Then: ./financial_env/bin/jupyter nbconvert --to notebook --execute --inplace ...
"""
import nbformat as nbf
from pathlib import Path

nb = nbf.v4.new_notebook()
nb.metadata["kernelspec"] = {
    "display_name": "Python 3", "language": "python", "name": "python3"
}
nb.metadata["language_info"] = {"name": "python", "version": "3.14"}

md = nbf.v4.new_markdown_cell
code = nbf.v4.new_code_cell

cells = []

# ============================================================ Title
cells.append(md(
"""# NAV Data Exploration — Mutual Fund Ingestion Pipeline

**Notebook:** `05_nav_data_exploration.ipynb`
**Purpose:** Understand what data we currently have in the database, how to fetch it,
and what it looks like — with interactive Plotly visualizations.

## What this notebook covers

| Section | Content |
|---|---|
| 1 | Database connection (PostgreSQL via Docker, `DATABASE_URL` override) |
| 2 | Full schema inspection — 23 tables, columns, row counts |
| 3 | **NAV deep dive** — coverage over time, per-AMC, distributions |
| 4 | Schemes & AMCs catalog analysis |
| 5 | Portfolio holdings overview |
| 6 | Pipeline health — ingestion runs, quarantine, staging |
| 7 | Data quality report & summary dashboard |

## How to run

```bash
# DB URL resolves via DATABASE_URL env var or api.env (db_config.py)
./financial_env/bin/python -m jupyter lab notebooks/mutual_fund_ingestion/05_nav_data_exploration.ipynb
```

The Docker Postgres (`vlmrouter-postgres`, port 5432) must be running:
`docker start vlmrouter-postgres`
"""))

# ============================================================ 1. Setup
cells.append(md("## 1. Setup & Database Connection"))
cells.append(code(
"""import os
import sys
from pathlib import Path

# Project root (works regardless of where jupyter was launched)
PROJECT_ROOT = Path.cwd()
while not (PROJECT_ROOT / "mutual_fund_ingestion").exists() and PROJECT_ROOT != PROJECT_ROOT.parent:
    PROJECT_ROOT = PROJECT_ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db_config import generic_database_url

import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio

from sqlalchemy import create_engine, text

pio.renderers.default = "notebook"
pd.set_option("display.max_columns", 50)
pd.set_option("display.width", 160)

REPORT_DIR = PROJECT_ROOT / "data" / "reports" / "mutual_funds" / "exploration"
# If the notebook was launched from notebooks/, PROJECT_ROOT may resolve to
# notebooks/ — fall back one level up so reports always land in <repo>/data/reports.
if not (PROJECT_ROOT / "data").exists() and (PROJECT_ROOT.parent / "data").exists():
    REPORT_DIR = PROJECT_ROOT.parent / "data" / "reports" / "mutual_funds" / "exploration"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
print("Project root:", PROJECT_ROOT)
print("Reports dir :", REPORT_DIR)"""
))

cells.append(md(
"""**Connection strategy:** the canonical store is PostgreSQL in Docker
(container `vlmrouter-postgres`, db `mutual_funds`, user `vlmrouter`).
Set `DATABASE_URL` to override; the default below matches the local Docker setup."""
))
cells.append(code(
"""# DSN resolution: DATABASE_URL env var > api.env (db_config.py) > local Docker default
import sys as _sys
_sys.path.insert(0, str(_ROOT))

from db_config import generic_database_url

DATABASE_URL = generic_database_url()

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    version = conn.execute(text("SELECT version()")).scalar()
    db_name = conn.execute(text("SELECT current_database()")).scalar()

print(f"Connected to : {db_name}")
print(version.split(",")[0])"""
))

def save_fig_helper():
    return (
        'def save_fig(fig, name):\n'
        '    """Save a figure as standalone HTML next to the notebook reports."""\n'
        '    path = REPORT_DIR / f"{name}.html"\n'
        '    fig.write_html(path, include_plotlyjs="cdn")\n'
        '    print("saved:", path)\n'
        '    return fig\n'
    )

# ============================================================ 2. Schema inspection
cells.append(md(
"""## 2. Schema Inspection — what tables exist?

Every table in `public`, its row count, and its columns. This is the map of
**how to fetch the data**: each row below is queryable directly.
"""
))
cells.append(code(save_fig_helper() + '''
TABLE_QUERY = """
SELECT c.relname AS table_name,
       COALESCE(n_live_tup, 0) AS est_rows
FROM pg_stat_user_tables ps
JOIN pg_class c ON c.oid = ps.relid
ORDER BY c.relname
"""

with engine.connect() as conn:
    tables = pd.read_sql(text(TABLE_QUERY), conn)

# Exact counts for the small tables, estimated for big ones is fine here;
# do exact for everything since our volumes are modest.
exact_counts = {}
with engine.connect() as conn:
    for t in tables["table_name"]:
        exact_counts[t] = conn.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar()
tables["rows"] = tables["table_name"].map(exact_counts)
tables.drop(columns="est_rows", inplace=True)
tables.sort_values("rows", ascending=False, inplace=True)

fig = px.bar(
    tables, x="rows", y="table_name", orientation="h",
    title="Row Count per Table (entire public schema)",
    labels={"rows": "Rows", "table_name": ""},
    color="rows", color_continuous_scale="Teal",
    height=650,
)
fig.update_layout(yaxis={"categoryorder": "total ascending"}, showlegend=False)
save_fig(fig, "02_table_row_counts")
fig.show()
tables'''
))

cells.append(md("**Column inventory** — every table with its columns and types."))
cells.append(code(
'''SCHEMA_QUERY = """
SELECT table_name, ordinal_position AS col_pos, column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
ORDER BY table_name, ordinal_position
"""

with engine.connect() as conn:
    schema_df = pd.read_sql(text(SCHEMA_QUERY), conn)

for t in tables["table_name"]:
    cols = schema_df[schema_df.table_name == t]
    printable = ", ".join(f"{r.column_name}:{r.data_type[:12]}" for r in cols.itertuples())
    print(f"{t} ({exact_counts[t]:>7,} rows)")
    print(f"   {printable}\\n")'''
))

# ============================================================ 3. NAV deep dive
cells.append(md(
"""## 3. NAV Deep Dive — the core dataset

`nav_history` stores one row per *(scheme_code, nav_date)*. Key questions:

1. **How much history do we have?** (dates covered, rows per date)
2. **Which schemes have the deepest history?**
3. **What do NAV values look like?** (distribution by scheme type/AMC)
4. **Where are the gaps?**
"""
))
cells.append(code(
'''NAV_OVERVIEW = """
SELECT count(*)                       AS total_rows,
       count(distinct scheme_code)    AS distinct_schemes,
       count(distinct nav_date)       AS distinct_dates,
       min(nav_date)                  AS earliest_date,
       max(nav_date)                  AS latest_date,
       round(avg(nav_value)::numeric, 2) AS avg_nav,
       min(nav_value)                 AS min_nav,
       max(nav_value)                 AS max_nav
FROM nav_history
"""

with engine.connect() as conn:
    overview = pd.read_sql(text(NAV_OVERVIEW), conn)

o = overview.iloc[0]
print(f"Total NAV rows      : {o.total_rows:>12,}")
print(f"Distinct schemes    : {o.distinct_schemes:>12,}")
print(f"Distinct NAV dates  : {o.distinct_dates:>12,}")
print(f"Date range          : {o.earliest_date} -> {o.latest_date}")
print(f"NAV value range     : {o.min_nav} -> {o.max_nav} (avg {o.avg_nav})")
overview'''
))

cells.append(md("### 3.1 Rows per NAV date — where is the mass?"))
cells.append(code(
'''ROWS_PER_DATE = """
SELECT nav_date, count(*) AS rows, count(distinct scheme_code) AS schemes
FROM nav_history
GROUP BY nav_date
ORDER BY nav_date
"""

with engine.connect() as conn:
    per_date = pd.read_sql(text(ROWS_PER_DATE), conn)

fig = go.Figure()
fig.add_trace(go.Bar(x=per_date.nav_date, y=per_date.rows,
                     name="NAV rows", marker_color="#2a9d8f"))
fig.add_trace(go.Scatter(x=per_date.nav_date, y=per_date.schemes,
                         name="distinct schemes", mode="lines",
                         line=dict(color="#e76f51", width=2)))
fig.update_layout(
    title="NAV Rows Stored per Date — snapshot coverage vs scattered historical rows",
    xaxis_title="NAV date", yaxis_title="Count", barmode="overlay",
    height=450,
)
save_fig(fig, "03_01_rows_per_date")
fig.show()

top_dates = per_date.sort_values("rows", ascending=False).head(10)
print("Top 10 dates by stored rows:")
top_dates'''
))

cells.append(md(
"""### 3.2 The snapshot problem — visualizing what history really means

AMFI's `NAVAll.txt` is a *current snapshot*. Rows with old dates are segregated /
wound-up schemes, not a time series. This chart makes that obvious.
"""))
cells.append(code(
'''per_date["is_latest"] = per_date.nav_date == per_date.nav_date.max()
cutoff = per_date.rows.quantile(0.5)

fig = px.scatter(
    per_date, x="nav_date", y="rows", color="rows",
    color_continuous_scale="Viridis",
    title="Each dot = one NAV date. One dense band = daily snapshots; long tail = stale/segregated rows",
    labels={"rows": "rows stored for this date"},
    height=420,
)
fig.add_hline(y=cutoff, line_dash="dash", annotation_text="median")
save_fig(fig, "03_02_snapshot_vs_tail")
fig.show()

n_dense = int((per_date.rows > 1000).sum())
n_sparse = int((per_date.rows <= 1000).sum())
print(f"Dense snapshot dates (>1000 rows): {n_dense}")
print(f"Sparse dates (<=1000 rows)      : {n_sparse}")
print(f"\\n=> True time-series depth: ~{n_dense} trading days "
      f"({per_date[per_date.rows > 1000].nav_date.min()} -> "
      f"{per_date[per_date.rows > 1000].nav_date.max()})")'''
))

cells.append(md("### 3.3 Scheme depth — how many dates does each scheme have?"))
cells.append(code(
'''DEPTH_PER_SCHEME = """
SELECT scheme_code, count(*) AS n_dates,
       min(nav_date) AS first_date, max(nav_date) AS last_date,
       count(*) FILTER (WHERE nav_value > 0) AS nonzero_dates
FROM nav_history
GROUP BY scheme_code
"""

with engine.connect() as conn:
    depth = pd.read_sql(text(DEPTH_PER_SCHEME), conn)

fig = px.histogram(
    depth, x="n_dates", nbins=60, log_y=True,
    title="Distribution of History Depth per Scheme (log y-axis)",
    labels={"n_dates": "number of NAV dates stored", "count": "schemes"},
    color_discrete_sequence=["#457b9d"],
)
fig.update_layout(height=420)
save_fig(fig, "03_03_scheme_depth_histogram")
fig.show()

print("Depth percentiles:")
print(depth.n_dates.describe(percentiles=[0.25, 0.5, 0.75, 0.95]).round(1))'''
))

cells.append(md(
"""### 3.4 Sample NAV trends — the deepest-history schemes

Pick the schemes with the most stored dates and plot their NAV trajectories.
*(Interactive: zoom, hover, toggle schemes in the legend.)*
"""
))
cells.append(code(
'''TOP_SCHEMES = """
WITH ranked AS (
    SELECT scheme_code, count(*) AS n_dates
    FROM nav_history
    GROUP BY scheme_code
    ORDER BY n_dates DESC
    LIMIT 8
)
SELECT nh.scheme_code,
       COALESCE(s.scheme_name, 'Scheme ' || nh.scheme_code) AS label,
       nh.nav_date, nh.nav_value
FROM nav_history nh
JOIN ranked r USING (scheme_code)
LEFT JOIN schemes s USING (scheme_code)
ORDER BY nh.scheme_code, nh.nav_date
"""

with engine.connect() as conn:
    trends = pd.read_sql(text(TOP_SCHEMES), conn)

fig = px.line(
    trends, x="nav_date", y="nav_value", color="label",
    title=f"NAV Trends — top {trends.label.nunique()} schemes by stored history",
    labels={"nav_date": "", "nav_value": "NAV (₹)", "label": ""},
)
fig.update_layout(height=500, legend=dict(orientation="h", y=-0.15))
save_fig(fig, "03_04_top_scheme_trends")
fig.show()'''
))

cells.append(md("### 3.5 NAV value distribution across the whole table"))
cells.append(code(
'''NAV_DIST = """
SELECT nav_value FROM nav_history WHERE nav_value > 0
"""

with engine.connect() as conn:
    nav_vals = pd.read_sql(text(NAV_DIST), conn)

fig = make_subplots(rows=1, cols=2, subplot_titles=("Linear scale", "Log scale"))
fig.add_trace(go.Histogram(x=nav_vals.nav_value, nbinsx=120,
                           marker_color="#2a9d8f", showlegend=False), row=1, col=1)
fig.add_trace(go.Histogram(x=np.log10(nav_vals.nav_value), nbinsx=120,
                           marker_color="#264653", showlegend=False), row=1, col=2)
fig.update_layout(title="NAV Value Distribution (log10 axis on right)", height=400)
fig.update_xaxes(title_text="NAV (₹)", row=1, col=1)
fig.update_xaxes(title_text="log10(NAV)", row=1, col=2)
save_fig(fig, "03_05_nav_distribution")
fig.show()'''
))

# ============================================================ 4. Schemes & AMCs
cells.append(md("## 4. Schemes & AMCs Catalog"))
cells.append(code(
'''AMC_COVERAGE = """
SELECT a.id AS amc_uuid, a.name AS amc_name,
       count(DISTINCT s.scheme_code)                    AS n_schemes,
       count(DISTINCT nh.scheme_code)                   AS n_schemes_with_nav
FROM amcs a
LEFT JOIN schemes s        ON s.amc_id = a.id
LEFT JOIN nav_history nh   ON nh.scheme_code = s.scheme_code
GROUP BY a.id, a.name
ORDER BY n_schemes_with_nav DESC, n_schemes DESC
"""

with engine.connect() as conn:
    amc_cov = pd.read_sql(text(AMC_COVERAGE), conn)

amc_plot = amc_cov.head(25).melt(
    id_vars=["amc_name"], value_vars=["n_schemes", "n_schemes_with_nav"],
    var_name="metric", value_name="count"
)

fig = px.bar(
    amc_plot, x="count", y="amc_name", color="metric", orientation="h",
    barmode="group",
    title="Top 25 AMCs — registered schemes vs schemes that actually have NAV data",
    labels={"amc_name": "", "count": "count"},
    color_discrete_map={"n_schemes": "#a8dadc", "n_schemes_with_nav": "#1d3557"},
    height=750,
)
fig.update_layout(yaxis={"categoryorder": "total ascending"})
save_fig(fig, "04_amc_coverage")
fig.show()
amc_cov.head(30)'''
))

cells.append(md("### 4.1 Scheme name patterns — plan keywords across scheme names"))
cells.append(code(
'''# plan/option columns live in parsed NAV payloads, not yet in canonical schemes;
# profile what we DO have: keyword prevalence in scheme names.
NAME_PATTERNS = """
SELECT
  count(*)                                                        AS all_schemes,
  count(*) FILTER (WHERE scheme_name ~* '\\\\mdirect\\\\m')          AS mentions_direct,
  count(*) FILTER (WHERE scheme_name ~* 'regular')                AS mentions_regular,
  count(*) FILTER (WHERE scheme_name ~* 'growth')                 AS mentions_growth,
  count(*) FILTER (WHERE scheme_name ~* 'idcw|dividend')          AS mentions_idcw,
  count(*) FILTER (WHERE scheme_name ~* 'fund of fund|fof')       AS mentions_fof,
  count(*) FILTER (WHERE category IS NOT NULL)                    AS with_category
FROM schemes
"""

with engine.connect() as conn:
    pm = pd.read_sql(text(NAME_PATTERNS), conn).iloc[0]

plot_df = pd.DataFrame({
    "pattern": ["Direct", "Regular", "Growth", "IDCW/Dividend", "FoF", "Categorized"],
    "schemes": [pm.mentions_direct, pm.mentions_regular, pm.mentions_growth,
                pm.mentions_idcw, pm.mentions_fof, pm.with_category],
})

fig = px.bar(
    plot_df.sort_values("schemes"), x="schemes", y="pattern", orientation="h",
    title=f"Scheme name keyword prevalence — {pm.all_schemes:,} schemes total",
    labels={"pattern": "", "schemes": "schemes"},
    color="schemes", color_continuous_scale="Teal",
    height=380,
)
save_fig(fig, "04_01_scheme_name_patterns")
fig.show()'''
))

# ============================================================ 5. Portfolio
cells.append(md("## 5. Portfolio Holdings Overview"))
cells.append(code(
'''PORTFOLIO_TOP = """
SELECT ph.security_name,
       count(*)                        AS appearances,
       round(avg(ph.percentage_to_nav)::numeric, 3) AS avg_pct_nav
FROM portfolio_holdings ph
WHERE ph.security_name IS NOT NULL
GROUP BY ph.security_name
ORDER BY appearances DESC, avg_pct_nav DESC
LIMIT 20
"""

with engine.connect() as conn:
    port_top = pd.read_sql(text(PORTFOLIO_TOP), conn)

fig = px.bar(
    port_top.sort_values("appearances"), x="appearances", y="security_name",
    orientation="h", color="avg_pct_nav", color_continuous_scale="Sunsetdark",
    title="Most-Held Securities Across Disclosed Portfolios",
    labels={"security_name": "", "appearances": "times disclosed", "avg_pct_nav": "avg % of NAV"},
    height=600,
)
save_fig(fig, "05_portfolio_top_holdings")
fig.show()'''
))

# ============================================================ 6. Pipeline health
cells.append(md(
"""## 6. Pipeline Health — runs, quarantine, staging

How did the data get here, and what got rejected on the way?
"""
))
cells.append(code(
'''RUNS_Q = """
SELECT status, count(*) AS runs,
       coalesce(sum(files_seen), 0)   AS files_seen,
       coalesce(sum(rows_inserted), 0) AS rows_inserted,
       coalesce(sum(rows_rejected), 0) AS rows_rejected
FROM ingestion_runs
GROUP BY status ORDER BY runs DESC
"""
QUARANTINE_Q = """
SELECT reason, count(*) AS rows FROM quarantine_rows GROUP BY reason ORDER BY rows DESC
"""
STAGING_Q = """
SELECT dataset_type, count(*) AS staged_rows FROM staging_rows GROUP BY dataset_type
"""

with engine.connect() as conn:
    runs_df = pd.read_sql(text(RUNS_Q), conn)
    quar_df = pd.read_sql(text(QUARANTINE_Q), conn)
    stag_df = pd.read_sql(text(STAGING_Q), conn)

print("=== Ingestion runs by status ===")
display(runs_df)
print("\\n=== Quarantined rows by reason ===")
display(quar_df if len(quar_df) else pd.DataFrame({"reason": ["(none)"], "rows": [0]}))
print("\\n=== Staging rows by dataset ===")
display(stag_df if len(stag_df) else pd.DataFrame({"dataset_type": ["(none)"], "staged_rows": [0]}))'''
))

cells.append(code(
'''fig = make_subplots(rows=1, cols=2, specs=[[{"type": "domain"}, {"type": "domain"}]],
                    subplot_titles=("Run statuses", "Quarantine reasons"))
if len(runs_df):
    fig.add_trace(go.Pie(labels=runs_df.status, values=runs_df.runs, hole=0.55), row=1, col=1)
if len(quar_df):
    fig.add_trace(go.Pie(labels=quar_df.reason, values=quar_df.rows, hole=0.55), row=1, col=2)
else:
    fig.add_trace(go.Pie(labels=["clean ✅"], values=[1], hole=0.55,
                         marker_colors=["#2a9d8f"]), row=1, col=2)
fig.update_layout(title="Pipeline Health at a Glance", height=420)
save_fig(fig, "06_pipeline_health")
fig.show()'''
))

# ============================================================ 7. Quality + dashboard
cells.append(md(
"""## 7. Data Quality Report & Summary Dashboard

Automated checks against expectations for this pipeline.
"""
))
cells.append(code(
'''checks = []

def check(name, ok, detail):
    checks.append({"check": name, "status": "✅ pass" if ok else "❌ FAIL", "detail": detail})

check("NAV rows exist", o.total_rows > 0, f"{o.total_rows:,} rows")
check("≥1000 schemes with NAV", o.distinct_schemes >= 1000, f"{o.distinct_schemes:,} schemes")
check("Latest snapshot within 3 days",
      pd.Timestamp(o.latest_date) >= pd.Timestamp.today().normalize() - pd.Timedelta(days=3),
      f"latest={o.latest_date}")
dense_days = int((per_date.rows > 1000).sum())
check("≥5 dense daily snapshots", dense_days >= 5, f"{dense_days} dense days")
zero_nav = int((nav_vals.nav_value == 0).sum()) if len(nav_vals) else 0
check("No zero-NAV rows in canonical", zero_nav == 0, f"{zero_nav} zero-NAV rows")
dupes_q = """
SELECT count(*) FROM (
    SELECT scheme_code, nav_date, count(*)
    FROM nav_history GROUP BY scheme_code, nav_date HAVING count(*) > 1
) d
"""
with engine.connect() as conn:
    dupes = conn.execute(text(dupes_q)).scalar()
check("No duplicate (scheme, date) keys", dupes == 0, f"{dupes} duplicate keys")

quality_df = pd.DataFrame(checks)
quality_df'''
))

cells.append(code(
'''# ---- Summary dashboard figure ----
kpi = [
    ("NAV rows", f"{o.total_rows:,}"),
    ("Schemes w/ NAV", f"{o.distinct_schemes:,}"),
    ("Dates covered", f"{o.distinct_dates:,}"),
    ("Dense snapshots", f"{dense_days}"),
    ("AMCs tracked", f"{len(amc_cov):,}"),
    ("Portfolio holdings", f"{exact_counts.get('portfolio_holdings', 0):,}"),
]

fig = go.Figure()
for i, (label, value) in enumerate(kpi):
    fig.add_trace(go.Indicator(
        mode="number", value=float(value.replace(",", "")),
        title={"text": f"<span style='font-size:13px'>{label}</span>",
               "font": {"size": 14}},
        number={"font": {"size": 26}},
        domain={"row": i // 3, "column": i % 3},
    ))
fig.update_layout(
    grid={"rows": 2, "columns": 3},
    title="<b>Database Summary Dashboard</b>",
    height=380,
)
save_fig(fig, "07_summary_dashboard")
fig.show()'''
))

cells.append(md(
"""## How to extend this notebook

- **Fetch more NAV:** `python -m mutual_fund_ingestion nav incremental --days-back N`
  or `nav backfill --start YYYY-MM-DD --end YYYY-MM-DD` (see MASTER_STATE.md CLI list).
- **Query raw:** anything above is plain SQL, e.g.
  `docker exec -it vlmrouter-postgres psql -U vlmrouter -d mutual_funds -c "select ..."`
- **Add AMC comparisons:** join `nav_history` -> `schemes` -> `amcs` on
  `scheme_code` / `amc_id`.
- All figures are also written to `data/reports/mutual_funds/exploration/*.html`.
"""))

nb.cells = cells

out = Path("notebooks/mutual_fund_ingestion/05_nav_data_exploration.ipynb")
out.write_text(nbf.writes(nb))
print(f"Wrote {out} ({len(cells)} cells)")
