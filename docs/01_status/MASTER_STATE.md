# Master System State

_Verified: 2026-06-26. Source of truth: live codebase + test suite._

---

## Loop Engineering Setup

**Status:** Complete (2026-06-27)

**Checkpoint Plan:** `docs/06_plans/CHECKPOINT_PLAN.md`

**Active Checkpoint:** 0 — System Foundation

**Pi Loop Rules:** `docs/07_agent_rules/PI_LOOP_RULES.md`

**Verification Spec:** `docs/07_agent_rules/VERIFICATION_SPEC.md`

**Pi Prompts:** `docs/06_plans/PI_PROMPTS.md`

**To begin:** Paste the Checkpoint 0 START prompt from `docs/06_plans/PI_PROMPTS.md` into a Pi session.

---

## Test Suite

```
122 passed, 3 skipped
Run: ./financial_env/bin/python -m pytest tests/ -q
```

> Note: Previous docs referenced "125 tests passing" — that counted 3 tests now marked as skipped (live network smoke tests). The 122 count is the accurate non-skipped baseline.

Coverage split:
- ~38 Phase 1A/1B tests (`test_mutual_fund_ingestion.py`)
- ~47 agent unit tests (`test_agent.py`)
- 11 amfi_disclosure prototype tests (`test_amfi_disclosure.py`)
- ~22 DB integration tests (`test_agent_db.py`)
- 3 smoke tests — skipped unless live network available (`test_smoke.py`)

---

## Completed

### Phase 1A — Source Registry Bootstrap
- `profiling/source_registry.py`, `profiling/source_discovery.py`, `profiling/registry.py`
- Reads `configs/amc_sources.yaml` (53 AMCs + AMFI + SEBI)
- CLI: `python -m mutual_fund_ingestion bootstrap-sources`

### Phase 1B — Provider Website Profiling
- `profiling/profiler.py`, `profiling/extract.py`, `profiling/browser.py`, `profiling/artifacts.py`, `profiling/reports.py`
- Static HTML profiling + optional Playwright rendering
- CLI: `python -m mutual_fund_ingestion profile-providers`

### Task-URL Agent — Core Pipeline
- `agent/runner.py` — orchestrates full pipeline (821 lines — LAYER VIOLATION, see below)
- `agent/discovery.py` — BFS crawl, relevance scoring, dataset classification
- `agent/browser.py` — Playwright fallback
- `agent/extract.py` — streaming download, SHA256 checksum
- `agent/db.py` — 17 SQLAlchemy table models
- `agent/config.py` — AgentConfig
- VLM wired (NullVLMClient + OllamaVLMClient)
- Raw file retention implemented
- CLI: `python -m mutual_fund_ingestion run-agent`

### Parsers
- NAV: text, CSV, HTML
- Portfolio: Excel (header detection fixed), CSV
- Scheme master: CSV, HTML
- AMC/provider HTML
- Parser router (`route_parser`, `parse_file`) wired in runner

### Validation / Pipeline
- `validate_nav_record`, `validate_portfolio_record`, `validate_and_filter_records`
- Staging rows written; canonical upserts for amcs, schemes, nav_history, portfolio
- Quarantine writer with reason codes

### Repository Hygiene
- `*.db*` in `.gitignore`; `financial_env/` in `.gitignore`
- `pika` removed from `requirements.txt`
- Timestamps in logging format

---

## Partially Implemented

| Feature | Status | Task |
|---|---|---|
| `validate_scheme_master_record()` | Unclear — verify TASK-G001/G002 | G001/G002 |
| `validate_amc_record()` | Unclear | G001/G002 |
| Metadata parsers (factsheet, SID, KIM, TER, AUM) | Stubs only in `parser/metadata.py` | Q001-Q003 |
| Network/API as explicit discovery step | Partially (browser captures it) | Not planned |

---

## Missing / Not Started

| Feature | Notes |
|---|---|
| Phase 2: document discovery from Phase 1 profiles | Spec in `docs/05_planned/phase_2_discovery/` |
| Phase 3: document classification | Not started |
| Epic G validation tests (6 tasks) | Pending |
| Epic H discovery tests (5 tasks) | Pending |
| Epic I/J browser + network tests | Pending |
| Epic K VLM tests | Pending |
| Epic L/M/N/O/P/Q parser + retention tests | Partially pending |
| Analytics layer | Not started |
| `docs/02_architecture/system_overview.md` | Not yet written |
| `docs/02_architecture/database_schema.md` | Not yet written |

---

## Code Structure Assessment

_Produced 2026-06-26 per CLAUDE_CODE_MASTER_BRIEF.md Part 2._

### Layer Compliance: agent/ Module

| File | Expected layer | Actual | Violation? |
|---|---|---|---|
| `agent/runner.py` | Layer 3 (orchestration) | Layer 3+4 mixed | **YES — 821 lines; _upsert_* methods are Layer 4 logic embedded in orchestrator** |
| `agent/discovery.py` | Layer 4 (core) | Layer 4 | No |
| `agent/browser.py` | Layer 4 (core) | Layer 4 | No |
| `agent/extract.py` | Layer 4 (core) | Layer 4 | No |
| `agent/parser/__init__.py` | Layer 2 (router) | Layer 4 (routing logic inline) | Minor |
| `agent/parser/nav.py` | Layer 4 | Layer 4 | No |
| `agent/parser/portfolio.py` | Layer 4 | Layer 4 | No |
| `agent/validate.py` | Layer 4 | Layer 4 | No |
| `agent/vlm.py` | Layer 4 | Layer 4 | No |
| `agent/db.py` | Layer 5 | Layer 5 | No (331 lines — justified by 17 tables) |
| `agent/models.py` | Layer 5 | Layer 5 | No |
| `agent/config.py` | Layer 5 | Layer 5 | No |

### Layer Compliance: profiling/ Module

| File | Layer | Compliant? |
|---|---|---|
| `profiling/models.py` | 5 — Schemas | Yes |
| `profiling/registry.py` | 5 — Config loading | Yes |
| `profiling/extract.py` | 4 — HTML parsing | Yes |
| `profiling/http.py` | 5 — HTTP session | Yes |
| `profiling/browser.py` | 4 — Playwright | Yes |
| `profiling/profiler.py` | 4 — Core profiling | Yes |
| `profiling/artifacts.py` | 3 — Artifact persistence | Yes |
| `profiling/reports.py` | 3 — Report generation | Yes |
| `profiling/source_registry.py` | 3 — Candidate merging | Yes |
| `profiling/source_discovery.py` | 4 — AMFI/SEBI discovery | Yes |

**profiling/ verdict: COMPLIANT — all frozen, all layers correct.**

### Refactor Candidates

| File | Reason | Estimated scope | Priority |
|---|---|---|---|
| `agent/runner.py` | 821 lines; `_upsert_nav_history`, `_upsert_amcs`, `_upsert_schemes`, `_upsert_portfolio`, `_download_and_process_artifact` are Layer 4 core logic embedded in Layer 3 orchestrator. Proposed split: extract to `agent/upserts.py` | Medium — ~4 hours, ~300 lines | High (before Phase 2) |

See `docs/04_in_progress/REFACTOR_runner.md` for full proposal.

### Utils Check

`utils/http.py`, `utils/url_utils.py`, `utils/text_utils.py` — all Layer 5, no high-level imports. Compliant.

### Conclusion

**Acceptable to continue building test coverage.** The `runner.py` violation is significant but self-contained — no other modules import its private methods. It does not block Epics G–Q. The refactor must happen **before Phase 2** is implemented.

---

## Known Blockers

| Issue | Impact | Action |
|---|---|---|
| `runner.py` layer violation | Will worsen with Phase 2 additions | Create `docs/04_in_progress/REFACTOR_runner.md` |
| `docs/02_architecture/system_overview.md` missing | Agents lack pipeline diagram | Add as TASK-B004 sub-task |
| `docs/02_architecture/database_schema.md` missing | 17 tables undocumented | Add as TASK-B004 sub-task |

---

## CLI Entry Points (verified working)

```bash
python -m mutual_fund_ingestion bootstrap-sources --dry-run
python -m mutual_fund_ingestion profile-providers --limit 3
python -m mutual_fund_ingestion init-db --database-url "$DATABASE_URL"
python -m mutual_fund_ingestion run-agent --task-url URL --database-url "$DATABASE_URL"
python -m mutual_fund_ingestion inspect-run --database-url "$DATABASE_URL" --run-id RUN_ID
python -m mutual_fund_ingestion retry-failed --database-url "$DATABASE_URL" --run-id RUN_ID
python -m amfi_disclosure run
```
