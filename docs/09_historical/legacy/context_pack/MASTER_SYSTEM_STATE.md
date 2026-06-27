# Master System State
# Indian Mutual Fund Ingestion System
# Last verified: 2026-06-23 | Tests: 125 passing
# This is the single authoritative status file. All other status claims defer to this.

---

## 1. What Is Built and Frozen (Do Not Modify)

### Phase 1A — Source Registry Bootstrap ✅ COMPLETE
**Module:** `mutual_fund_ingestion/profiling/source_registry.py`, `source_discovery.py`, `registry.py`
**CLI:** `python -m mutual_fund_ingestion bootstrap-sources`
**Outputs:**
- `data/raw/mutual_funds/source_registry/source_registry_candidates.jsonl`
- `data/raw/mutual_funds/source_registry/source_registry.latest.json`
- `data/reports/mutual_funds/source_registry_report.html`
**Config:** `configs/amc_sources.yaml` — 53 AMC entries + AMFI + SEBI
**Tests:** ~38 in `tests/test_mutual_fund_ingestion.py`
**Status:** Frozen. Do not extend without creating a new module.

---

### Phase 1B — Provider Website Profiling ✅ COMPLETE
**Module:** `mutual_fund_ingestion/profiling/profiler.py`, `extract.py`, `browser.py`, `artifacts.py`, `reports.py`
**CLI:** `python -m mutual_fund_ingestion profile-providers`
**Outputs:**
- `data/raw/mutual_funds/provider_profiles/provider_profiles.jsonl`
- `data/raw/mutual_funds/provider_profiles/provider_profiles.latest.json`
- `data/reports/mutual_funds/provider_profile_report.html`
- `data/debug/mutual_funds/provider_profiles/<amc_name>/`
**Tests:** Included in `tests/test_mutual_fund_ingestion.py`
**Status:** Frozen. Input to Phase 2.

---

### Task-URL Agent — Core Ingestion Pipeline ✅ SUBSTANTIALLY COMPLETE
**Modules:** `mutual_fund_ingestion/agent/` (all submodules)
**CLI:** `python -m mutual_fund_ingestion run-agent`, `init-db`, `inspect-run`, `retry-failed`

**What is confirmed working:**
| Component | Status | Notes |
|---|---|---|
| `agent/runner.py` — IngestionRunner | ✅ | Full BFS orchestration |
| `agent/discovery.py` — DiscoveryEngine | ✅ | BFS crawl, relevance scoring, dataset classification |
| `agent/browser.py` — Playwright extraction | ✅ | Network capture, screenshots |
| `agent/extract.py` — ArtifactCollector | ✅ | SHA256, streaming download, raw retention |
| `agent/db.py` — 17 SQLAlchemy tables | ✅ | All tables created by `init-db` |
| `agent/config.py` — AgentConfig | ✅ | All CLI flags mapped |
| `agent/vlm.py` — VLM client | ✅ | NullVLMClient default; OllamaVLMClient; wired in runner.py L179–195 |
| Raw file retention (`--keep-raw-files`) | ✅ | Implemented in runner.py L409–417 |
| Logging with timestamps | ✅ | Fixed in cli.py |

**Parsers confirmed working:**
| Parser | Function | Status |
|---|---|---|
| NAV text | `parse_nav_text()` | ✅ |
| NAV CSV | `parse_nav_csv()` | ✅ |
| NAV HTML | `parse_nav_html()` | ✅ |
| AMC HTML | `parse_amc_html()` | ✅ |
| Portfolio Excel | `parse_portfolio_excel()` | ✅ Header detection fixed |
| Portfolio CSV | `parse_portfolio_csv()` | ✅ |
| Scheme master CSV | `parse_scheme_master_csv()` | ✅ |
| Scheme master HTML | `parse_scheme_master_html()` | ✅ |

**Canonical upserts confirmed working:**
- `_upsert_nav_history`, `_upsert_amcs`, `_upsert_schemes`, `_upsert_portfolio`
- Every canonical row carries `raw_artifact_id` + `source_url` provenance

**Database tables (all 17):**
`ingestion_runs`, `task_urls`, `source_pages`, `discovered_links`, `dataset_candidates`, `raw_artifacts`,
`amcs`, `schemes`, `nav_history`, `documents`, `instruments`, `portfolio_snapshots`, `portfolio_holdings`,
`staging_rows`, `validation_results`, `quarantine_rows`, `retry_queue`

---

## 2. What Is Partially Built (Needs Completion Before Phase 2)

### Test Coverage Gaps ⚠️ IN PROGRESS
**Current:** 125 tests passing
**Target before Phase 2:** ≥145 tests

| Epic | Gap | Priority |
|---|---|---|
| G — Validation | `validate_scheme_master_record()`, `validate_amc_record()` status unclear — need to verify if added | HIGH |
| H — Discovery | Relevance scoring, dataset classification tests incomplete | HIGH |
| P — Portfolio parser | Excel fixture with real AMFI column names needed | HIGH |
| N — NAV ingestion | NAV HTML end-to-end test (N004) | HIGH |
| O — AMC/Scheme | Scheme master CSV + DB linkage tests | MEDIUM |
| K — VLM | OllamaVLMClient mock test, runner invocation test | MEDIUM |
| I — Browser | Playwright unavailable / fixture-based tests | MEDIUM |
| J — Network/API | Network capture path tests | MEDIUM |
| L — Retention | L002/L003 retention edge-case tests (L001 done) | LOW |
| Q — Metadata stubs | Router entries for factsheet/SID/KIM/TER (stubs) | LOW |

### Metadata Parsers ⚠️ STUB ONLY
**File:** `mutual_fund_ingestion/agent/parser/metadata.py`
**Status:** May exist as stubs — not verified. Factsheet, SID, KIM, TER, AUM parsers not implemented.
**Blocked by:** Need real Phase 2 documents to build against.

---

## 3. What Is Not Started

| Phase | Status | Spec Location | Dependency |
|---|---|---|---|
| Phase 2 — Document discovery from Phase 1 profiles | ❌ NOT STARTED | `docs/design/phase_2/` | Test coverage complete |
| Phase 3 — Document classification | ❌ NOT STARTED | Planned | Phase 2 complete |
| Phase 4 — Additional parsers (factsheet, SID, KIM, TER) | ❌ NOT STARTED | Stub only | Real documents from Phase 2 |
| Phase 5 — Validation coverage expansion | ❌ NOT STARTED | Planned | Phase 2 complete |
| Phase 6 — Analytics layer | ❌ NOT STARTED | Not spec'd | Canonical tables populated |
| Phase 7 — Agentic query layer | ❌ NOT STARTED | Not spec'd | Analytics layer |

**Phase 1.5 note:** Phase 1.5 (strategy resolution) is NOT required unless Phase 1B profiles show many providers stuck at `manual_review`. Check `data/raw/mutual_funds/provider_profiles/provider_profiles.latest.json` before deciding.

---

## 4. Legacy / Do Not Touch

| Module | Reason |
|---|---|
| `mutual_fund_ingestion/amfi_disclosure/` | Standalone AMFI prototype — do not import into agent pipeline |
| `docs/archive/legacy_experiments/` | Historical experiments — read only |

---

## 5. Verified CLI Commands

```bash
# Phase 1
python -m mutual_fund_ingestion bootstrap-sources --dry-run
python -m mutual_fund_ingestion profile-providers --limit 3
python -m mutual_fund_ingestion phase-1 --limit 3

# Agent pipeline
python -m mutual_fund_ingestion init-db --database-url "$DATABASE_URL"
python -m mutual_fund_ingestion run-agent --task-url URL --database-url "$DATABASE_URL"
python -m mutual_fund_ingestion inspect-run --database-url "$DATABASE_URL" --run-id RUN_ID
python -m mutual_fund_ingestion retry-failed --database-url "$DATABASE_URL" --run-id RUN_ID

# AMFI prototype (isolated)
python -m amfi_disclosure run
```

---

## 6. Gate Before Starting Phase 2

Phase 2 is BLOCKED until all of the following are true:

- [ ] Epic G (validation coverage) — all tasks complete
- [ ] Epic H (discovery/relevance tests) — all tasks complete
- [ ] Epic P (portfolio parser with real column names) — complete
- [ ] Epic N (NAV HTML end-to-end) — complete
- [ ] Total test count ≥ 145
- [ ] `docs/design/phase_2/README_PHASE_2_CODEX_PACK.md` read in full before any Phase 2 code is written
