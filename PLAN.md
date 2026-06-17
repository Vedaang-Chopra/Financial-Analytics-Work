# Codebase Audit + Implementation Plan

## 1. Codebase Audit

### 1.1 Module Structure

```
mutual_fund_ingestion/
├── __init__.py              # Phase 1 re-exports only (no agent public API)
├── __main__.py              # Entry point: main() → cli.main()
├── cli.py                   # Layer 2: build_parser() + main()
├── models.py                # Layer 5: Phase 1 domain dataclasses
├── http.py                  # Layer 5: delegates to utils/http.py
├── extract.py               # Layer 5: Phase 1 EvidenceParser + extract_page_evidence()
├── browser.py               # Layer 4: Phase 1 render_reference_html() + inspect_with_browser()
├── profiler.py              # Layer 4: Phase 1B provider profiling
├── registry.py              # Layer 5: Phase 1A YAML loading
├── source_discovery.py      # Layer 4: Phase 1A AMFI/SEBI discovery
├── source_registry.py       # Layer 3: Phase 1A candidate merging
├── artifacts.py             # Layer 3: Phase 1B JSONL + snapshot persistence
├── reports.py               # Layer 3: Phase 1B HTML/CSV reports
└── agent/
    ├── __init__.py
    ├── config.py            # Layer 5: AgentConfig dataclass
    ├── models.py            # Layer 5: ParserResult, AgentResult, record types
    ├── db.py                # Layer 5: 17 SQLAlchemy tables
    ├── discovery.py         # Layer 4: DiscoveryEngine + LinkExtractor
    ├── browser.py           # Layer 4: extract_with_browser()
    ├── extract.py           # Layer 4: ArtifactCollector
    ├── validate.py          # Layer 4: validation + quarantine + retry
    ├── vlm.py               # Layer 4: VLMClient ABC + Null/Ollama impl
    ├── runner.py            # Layer 3: IngestionRunner (BROKEN - no DB writes)
    └── parser/
        ├── __init__.py      # Layer 4: ParserRouter
        ├── nav.py           # Layer 4: parse_nav_text/parse_nav_csv
        ├── amc.py           # Layer 4: parse_amc_html
        └── portfolio.py     # Layer 4: parse_portfolio_excel

utils/
├── __init__.py
├── http.py                 # Layer 5: HttpSettings + build_session()
├── url_utils.py            # Layer 5: canonical_url, file_type_from_url, safe_name, slugify
└── text_utils.py           # Layer 5: normalize_amc_name
```

### 1.2 Duplicate / Obsolete / Phase-Only Code

| File | Status | Action |
|---|---|---|
| `mutual_fund_ingestion/http.py` | ✅ OK — thin delegate to `utils/http.py` | Keep as-is (backward compat) |
| `mutual_fund_ingestion/extract.py` EvidenceParser | Phase 1 only | Keep (used by Phase 1A/1B) |
| `mutual_fund_ingestion/agent/discovery.py` LinkExtractor | Duplicated logic | Rename from `EvidenceParser` to `LinkExtractor` to avoid confusion; keep as-is since agent is self-contained |
| `mutual_fund_ingestion/agent/discovery.py` EvidenceParser | Duplicate removed | Replace with `LinkExtractor` class |
| `amfi_disclosure/` | Obsolete prototype | Leave as-is; not referenced |
| `Code Base/` | Legacy experiments | Leave as-is |
| `Dataset/` | Historical fixtures | Keep for parser tests |

### 1.3 Phase 1A/1B Reuse Decisions

| Phase 1A/1B Code | Reuse in agent? | Decision |
|---|---|---|
| `utils/http.py` HttpSettings + build_session | ✅ Yes | `agent/discovery.py`, `agent/extract.py` already import this |
| `utils/url_utils.py` canonical_url + file_type_from_url + safe_name | ✅ Yes | `agent/discovery.py`, `agent/extract.py` already import this |
| `utils/text_utils.py` normalize_amc_name | ✅ Yes | Available for canonical upsert |
| Phase 1 `EvidenceParser` (extract.py) | ❌ No | Agent has self-contained `LinkExtractor` |
| Phase 1 `extract_page_evidence` (extract.py) | ❌ No | Agent uses its own `DiscoveryEngine.classify_dataset` |
| Phase 1 `HttpSettings` (mutual_fund_ingestion/http.py) | ✅ Yes via utils | Already consolidated |
| Phase 1 `profiler.py` | ❌ No | Agent has its own discovery logic |
| Phase 1 `artifacts.py` | ❌ No | Agent uses `ArtifactCollector` |
| Phase 1 `source_registry.py` | ❌ No | Phase 1A bootstrap; not needed at runtime |

### 1.4 Missing Links in Runtime Path

**Current broken path:**
```
runner.run()
  → discovery.add_urls()
  → while queue: discovery.fetch() → extract_links() → score_relevance()
  → browser fallback (but NOT integrated with main flow)
  → DONE (no DB writes, no file download, no parsing, no validation)
```

**Required full path (what is missing):**
```
task URLs
  → [DB] ingestion_runs row created
  → [DB] task_urls rows inserted
  → DiscoveryEngine: crawl URL queue
    → [DB] source_pages row per page
    → [DB] discovered_links row per link
    → DiscoveryEngine.classify_dataset() → dataset_type
    → DiscoveryEngine.get_file_type() → file_type
    → if score > threshold AND is_file → DatasetCandidate
    → [DB] dataset_candidates row per candidate
  → ArtifactCollector.download() → local file
    → [DB] raw_artifacts row per file
  → ParserRouter.parse_file(dataset_type, file_type, content)
    → parse_nav_text | parse_nav_csv | parse_amc_html | parse_portfolio_excel
    → ParserResult(records=[...], ...)
  → [DB] staging_rows row per parsed record
  → validate_and_filter_records()
    → valid + quarantined
  → [DB] validation_results row per check
  → [DB] quarantine_rows row per invalid record
  → canonical_upsert():
    → amcs → [DB] amcs table
    → schemes → [DB] schemes table
    → nav_history → [DB] nav_history table
    → portfolio → [DB] portfolio_snapshots + portfolio_holdings
  → [DB] retry_queue for failed tasks
```

### 1.5 Design vs. Code Mismatches

| Design says | Code actually does |
|---|---|
| `runner.run()` inserts to PostgreSQL | `runner.run()` only returns dict with stats, no DB writes |
| NAV parser expects `scheme_code` | NAV parser outputs `scheme_code` ✅ (matches) |
| AMC parser outputs `name`, `website_url` | AMC parser outputs `name`, `website_url` ✅ (matches) |
| Portfolio parser outputs `security_name`, `percentage_to_nav` | Portfolio parser outputs `security_name`, `percentage_to_nav` ✅ (matches) |
| `parse_file()` takes `(dataset_type, file_type, content, metadata)` | `parse_file()` takes `(dataset_type, file_type, content, metadata)` ✅ (matches) |
| `validate_and_filter_records()` splits valid from quarantined | `validate_and_filter_records()` returns dicts (not ORM rows) - needs DB wiring |
| Staging-first approach with quarantine | Staging tables exist but are empty |
| Retry queue for failed tasks | Retry queue model exists but nothing writes to it |

---

## 2. Refactor Decisions

1. **Keep Phase 1A/1B as legacy support code** — `mutual_fund_ingestion/` modules are frozen; only fix broken imports.
2. **Rename `EvidenceParser` → `LinkExtractor`** in `agent/discovery.py` to eliminate duplicate class name confusion with Phase 1.
3. **No new shared utilities** — `utils/` is complete; all needed functions exist.
4. **Wire `runner.run()` to SQLAlchemy** — add session parameter, create IngestionRun, insert all provenance + staging + canonical rows.
5. **Canonical upsert logic** — use `ON CONFLICT DO UPDATE` via SQLAlchemy's `insert().values().on_conflict_do_update()` for `amcs`, `schemes`, `nav_history`.
6. **Schema master parser** — add `parse_scheme_master_csv()` to extract scheme_code, scheme_name, amc_name, category from AMFI scheme master CSV.

---

## 3. Implementation Tasks

### Task 1: Fix `EvidenceParser` → `LinkExtractor` in `agent/discovery.py`
- Rename class to `LinkExtractor`
- Remove old HTMLParser-based implementation
- Keep regex-based feed() method

### Task 2: Wire `runner.run()` to DB — full pipeline
**File: `mutual_fund_ingestion/agent/runner.py`** (major refactor)

New `IngestionRunner`:
```python
class IngestionRunner:
    def __init__(self, config: AgentConfig):
        self.session_maker = get_session_maker(config.database_url)
        self.session = self.session_maker()
        # ... existing setup ...

    def run(self) -> dict:
        # 1. Create ingestion_runs row
        # 2. Create task_urls rows
        # 3. Discovery loop (existing) with full DB wiring:
        #    - source_pages per page
        #    - discovered_links per link
        #    - dataset_candidates per relevant file/link
        #    - raw_artifacts via ArtifactCollector.download()
        #    - staging_rows per parsed record
        #    - validation_results per check
        #    - quarantine_rows per invalid record
        #    - canonical upsert: amcs, schemes, nav_history
        #    - retry_queue for failed tasks
        # 4. Commit or rollback
        # 5. Return result dict
```

### Task 3: Add `scheme_master` parser
**New file: `mutual_fund_ingestion/agent/parser/scheme_master.py`**
- `parse_scheme_master_csv(content, metadata)` → `ParserResult(dataset_type="scheme_master", records=[{scheme_code, scheme_name, amc_name, category, sub_category}])`
- Update `agent/parser/__init__.py` PARSER_ROUTER

### Task 4: Add `inspect-run` and `retry-failed` CLI commands
**File: `mutual_fund_ingestion/cli.py`**
- `inspect-run`: query `ingestion_runs` table by run_id, print summary
- `retry-failed`: query `retry_queue` where status=pending, re-run with same config

### Task 5: DB-backed tests
**File: `tests/test_agent_db.py`** (new)
- SQLite in-memory tests: init_db, run_agent with fixture data, verify rows in all table tiers
- Scheme master parser unit test
- Portfolio parser unit tests

### Task 6: Fix type/lint issues
- Ensure all imports are correct
- Ensure no circular imports

---

## 4. Files to Modify

| File | Change |
|---|---|
| `mutual_fund_ingestion/agent/discovery.py` | Rename EvidenceParser → LinkExtractor; fix imports |
| `mutual_fund_ingestion/agent/runner.py` | **Full rewrite** — add DB session, full pipeline wiring |
| `mutual_fund_ingestion/agent/parser/scheme_master.py` | **New** — scheme_master CSV/HTML parser |
| `mutual_fund_ingestion/agent/parser/__init__.py` | Add scheme_master to PARSER_ROUTER |
| `mutual_fund_ingestion/cli.py` | Add inspect-run + retry-failed subcommands |
| `tests/test_agent_db.py` | **New** — DB-backed integration tests |
| `tests/test_agent.py` | Add scheme_master parser tests + fix imports |

## 5. Reuse

| What to reuse | Where |
|---|---|
| `get_session_maker()` | `agent/db.py` → `runner.py` |
| `normalize_amc_name()` | `utils/text_utils.py` → canonical upsert |
| `file_type_from_url()` | `utils/url_utils.py` → classification |
| `parse_file()` router | `agent/parser/__init__.py` → already imported in runner |
| `validate_and_filter_records()` | `agent/validate.py` → already imported in runner |
| `ArtifactCollector` | `agent/extract.py` → already in runner as `self.collector` |
| `DiscoveryEngine` | `agent/discovery.py` → already in runner as `self.discovery` |

## 6. Verification

1. `python -m pytest tests/ -v` — all 50+ tests pass
2. `python -m mutual_fund_ingestion init-db --database-url "sqlite:///test.db"` — creates all 17 tables
3. `python -m mutual_fund_ingestion run-agent --task-url "https://www.amfiindia.com/sp-ups/NAV.txt" --database-url "sqlite:///test.db" --max-pages 2 --max-files 5 --dry-run` — completes without error, writes provenance + staging + nav_history rows
4. `python -m mutual_fund_ingestion inspect-run --database-url "sqlite:///test.db" <run_id>` — shows run summary

---

*Plan version: 1.0 — 2026-06-15*