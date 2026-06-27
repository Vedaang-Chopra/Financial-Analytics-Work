# Tasks: Demo Notebook for Mutual Fund Ingestion System

**Spec:** docs/specs/009_demo_notebook.md (TBD - this is a documentation task)
**Plan:** This is a Layer 1 (Notebook) task - no spec/plan required for notebooks
**Status:** In Progress
**Current Phase:** 1

---

## Phase 1: Create Comprehensive Demo Notebook

*Purpose: Build a single notebook that demonstrates the entire working pipeline - Phase 1A, 1B, and Agent - with live execution capability.*
*Depends on: existing artifacts and working CLI commands*

- [ ] **Task 1.1** — Create `notebooks/mutual_fund_ingestion/00_demo_system_overview.ipynb`
  - Notebook structure: Setup → Phase 1A (Source Registry) → Phase 1B (Provider Profiling) → Task-URL Agent → Live Demos
  - Load existing artifacts from `data/raw/mutual_funds/` and `data/reports/`
  - Show HTML reports embedded or linked
  - Include live execution cells with `--dry-run` and small `--limit` options
  - Verify: `./financial_env/bin/jupyter nbconvert --execute --to notebook --output /dev/null notebooks/mutual_fund_ingestion/00_demo_system_overview.ipynb 2>&1 | grep -i error || echo "OK"`

- [ ] **Task 1.2** — Add Phase 1A section: Source Registry inspection
  - Load `source_registry.latest.json` and display as interactive table
  - Show merge decisions and provenance
  - Include cell to run `bootstrap-sources --dry-run`
  - Link to `source_registry_report.html`
  - Verify: Notebook cell executes and displays 55 sources

- [ ] **Task 1.3** — Add Phase 1B section: Provider Profiling inspection
  - Load `provider_profiles.latest.json` and display strategy distribution
  - Show candidate links per provider
  - Include live profiling cell: `profile-providers --limit 3`
  - Show debug artifacts (static HTML, rendered HTML, screenshots, network logs)
  - Verify: Notebook cell executes and shows at least 2 providers with `success` status

- [ ] **Task 1.4** — Add Task-URL Agent section
  - Show `init-db` and `run-agent` commands
  - Include dry-run cell (no network dependency)
  - Show 17 database tables schema
  - Include live agent run with small limits
  - Verify: Dry-run cell executes without network error (may show timeout, which is expected)

- [ ] **Task 1.5** — Add AMFI Live Fetch section
  - Show `amfi_disclosure` CLI commands
  - Include bounded discovery and download cells
  - Show fetched file metadata
  - Verify: Discovery cell runs (network may timeout but command structure works)

### ✅ Checkpoint 1

*All items must pass before completing.*

- [ ] Notebook exists at `notebooks/mutual_fund_ingestion/00_demo_system_overview.ipynb`
- [ ] Notebook executes top-to-bottom without unhandled exceptions (network timeouts OK if caught)
- [ ] All existing artifacts load and display correctly
- [ ] Live demo cells have sensible bounds (--limit, --dry-run) to avoid long waits

**Human sign-off required:** YES — review notebook execution output.

---

## Phase 2: Optional - Additional Focused Notebooks

*Purpose: Create specialized notebooks for deeper dives if needed.*
*Depends on: Phase 1 complete*

- [ ] **Task 2.1** `[P]` — Create provider profiling deep-dive notebook (if Phase 1 shows need)
- [ ] **Task 2.2** `[P]` — Create agent DB inspection notebook

### ✅ Checkpoint 2

- [ ] Any additional notebooks execute cleanly

**Human sign-off required:** NO
