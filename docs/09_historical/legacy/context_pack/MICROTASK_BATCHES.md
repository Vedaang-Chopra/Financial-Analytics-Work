# Microtask Batches

_Created: 2026-06-23. Groups tasks from `TASKS_FULL_SYSTEM_MICRO_PLAN.md` into demonstrable batches._

This file sits above `TASKS_FULL_SYSTEM_MICRO_PLAN.md`. It does not replace it — it organizes it.

**Execution rule: one task per smaller-model session. Batches are for human-level tracking only.**

---

## Status Overview

| Batch | Name | Epic(s) | Status | Tests added |
|---|---|---|---|---|
| A | Repository hygiene | A | Mostly done | — |
| B | Documentation cleanup | B | Pending | — |
| C | Legacy archiving | C | Pending | — |
| D | CLI stability | D | Mostly done | — |
| E | Validation coverage | G | Pending | +6 |
| F | Discovery tests | H | Pending | +5 |
| G | Browser/network tests | I, J | Pending | +4 |
| H | VLM tests | K | Pending | +5 |
| I | Raw retention tests | L | Mostly done | +2 |
| J | NAV ingestion tests | N | Pending | +3 |
| K | AMC/Scheme master tests | O | Pending | +3 |
| L | Portfolio parser tests | P | Mostly done | +2 |
| M | Metadata parser stubs | Q | Pending | +3 |
| N | Final docs verification | T | In progress | — |
| Phase 2 | Document discovery | New | Not started | TBD |

---

## Completed Batches (Done)

### Batch: Phase 1A/1B Implementation
**Epics**: Phase 1 core
**Completed**: Jun 17, 2026
**Result**: 38 Phase 1 tests, source registry, provider profiling, reports, notebooks

### Batch: Agent Core Implementation
**Epics**: Agent core
**Completed**: Jun 17–21, 2026
**Result**: 36 agent unit tests + 22 DB integration tests; all 17 tables; BFS crawl; parsers (NAV, AMC, scheme master, portfolio); validation; upsert

### Batch A (Done)
**Epics**: A001, A002, A004
**Completed**: Jun 21, 2026
**Result**: .db files gitignored, pika removed, financial_env gitignored

### Batch: Bugs + Observability
**Epics**: D001/D002, E001–E007, K004, L001, N003, P001, P004, F002/F003
**Completed**: Jun 21–22, 2026
**Result**: Logging fixed, VLM wired, raw retention implemented, NAV HTML parser, portfolio fix, portfolio CSV, schema tests

### Batch: Fixture + Smoke Tests
**Epics**: R001–R004, S001–S002
**Completed**: Jun 22, 2026
**Result**: 3 smoke tests + 2 fixture e2e tests; 125 total tests passing

---

## Pending Batches

### Batch B — Documentation Cleanup

**Purpose**: Eliminate stale claims that confuse future agents.
**Tasks**: B001, B002, B003, B004, B005
**Execution rule**: one task per session, in order

| Task | File | Stale claim to fix |
|---|---|---|
| B001 | `PLAN.md` | Tasks 1/2 not marked done; "runner not writing to DB" |
| B002 | `plans/task_url_ingestion_agent.md` | Test count "50", stale gap list |
| B003 | `CHATGPT_PROJECT_MEMORY.md` | Test count 121 → 125 |
| B004 | `docs/ai_context/CODEBASE_MAP.md` | VLM note stale, portfolio bug note stale, parsers missing |
| B005 | `README.md` | Test count 118 → 125 |

**Completion gate**:
```bash
grep -rn "50 passing\|21 agent\|85 pass\|118 test\|does NOT insert\|never called\|column mapping broken" \
  PLAN.md plans/task_url_ingestion_agent.md CHATGPT_PROJECT_MEMORY.md \
  docs/ai_context/CODEBASE_MAP.md README.md
# Should return no matches
```

**Demo artifact**: grep returns empty.

---

### Batch C — Legacy Archiving

**Purpose**: Clearly mark legacy areas so agents don't import from them.
**Tasks**: C001, C002, C003

| Task | Description |
|---|---|
| C001 | Add README to amfi_disclosure/ marking it as legacy prototype |
| C002 | Verify README in docs/archive/legacy_experiments/ is accurate |
| C003 | Verify no production code imports from amfi_disclosure |

**Completion gate**:
```bash
grep -rn "from mutual_fund_ingestion.amfi_disclosure\|import amfi_disclosure" mutual_fund_ingestion/agent/ tests/
# Should return nothing (amfi_disclosure is isolated by design)
```

---

### Batch E — Validation Coverage

**Purpose**: Add validators for scheme_master and AMC records.
**Tasks**: G001 → G002 → G003 → G004 → G005 → G006
**Estimated test additions**: +6

**Completion gate**:
```bash
./financial_env/bin/python -m pytest tests/test_agent.py -k "validation or quarantine" -v -q
```

**Demo artifact**: Test output shows scheme_master and AMC records are validated and quarantined when invalid.

---

### Batch F — Discovery and Relevance Tests

**Purpose**: Verify discovery engine behavior with fixture HTML.
**Tasks**: H001 → H002 → H003 → H004 → H005
**Estimated test additions**: +5

**Completion gate**:
```bash
./financial_env/bin/python -m pytest tests/test_agent.py -k "relevance or discovery or classification or dataset_type" -v -q
```

---

### Batch G — Browser and Network Tests

**Purpose**: Verify Playwright and network-capture paths.
**Tasks**: I001, I002, J001, J002
**Estimated test additions**: +4

**Completion gate**:
```bash
./financial_env/bin/python -m pytest tests/test_agent.py -k "browser or network or playwright" -v -q
```

---

### Batch H — VLM Tests

**Purpose**: Verify VLM client contracts.
**Tasks**: K001, K002, K003, K005
**Estimated test additions**: +4–5

**Completion gate**:
```bash
./financial_env/bin/python -m pytest tests/ -k "vlm" -v -q
```

---

### Batch I — Raw Retention Tests

**Purpose**: Verify remaining retention behavior tests.
**Tasks**: L002, L003
_L001 (implementation) is done; `test_smoke_keep_raw_files_creates_file_in_raw_dir` passes._

**Completion gate**:
```bash
./financial_env/bin/python -m pytest tests/ -k "retention or raw_dir or keep_raw" -v -q
```

---

### Batch J — NAV Ingestion Tests

**Purpose**: Verify NAV text, CSV, HTML parsing.
**Tasks**: N001 (fixture), N002 (parse_nav_text test), N004 (parse_nav_html test)
_N003 (parse_nav_html implementation) is done._

**Completion gate**:
```bash
./financial_env/bin/python -m pytest tests/test_agent.py -k "nav" -v -q
```

**Demo artifact**: Test output showing NAV records with scheme_code and nav_value.

---

### Batch K — AMC and Scheme Master Tests

**Purpose**: Verify scheme master CSV parsing and AMC-to-scheme linkage.
**Tasks**: O001 (fixture), O002 (parse_scheme_master_csv test), O003 (upsert_schemes links test)

**Completion gate**:
```bash
./financial_env/bin/python -m pytest tests/ -k "scheme_master or amc" -v -q
```

---

### Batch L — Portfolio Parser Tests

**Purpose**: Verify portfolio Excel parsing with real AMFI column names.
**Tasks**: P002 (fixture), P003 (parse test)
_P001 (fix) and P004 (CSV parser) are done._

**Completion gate**:
```bash
./financial_env/bin/python -m pytest tests/ -k "portfolio" -v -q
```

**Demo artifact**: Test shows portfolio records with `security_name` and `percentage_to_nav` populated (not empty).

---

### Batch M — Metadata Parser Stubs

**Purpose**: Add router entries for factsheet, SID, KIM, TER, AUM so these files don't silently fail.
**Tasks**: Q001 (PARSER_ROUTER entries), Q002 (parser/metadata.py stubs), Q003 (test metadata_html returns doc record)

**Completion gate**:
```bash
./financial_env/bin/python -m pytest tests/test_agent.py -k "metadata or factsheet or ter or sid" -v -q
```

---

### Batch N — Final Docs Verification

**Purpose**: Confirm all documentation is accurate and the system is ready for Phase 2.
**Tasks**: T001, T002, T003, T004

| Task | Description |
|---|---|
| T001 | Update CODEBASE_MAP.md to reflect completed epics |
| T002 | Update README.md with verified commands |
| T003 | Run full test suite and verify all pass |
| T004 | Create final handoff note in session_state.md |

**Completion gate**:
```bash
./financial_env/bin/python -m pytest tests/ -q
# Expected: ≥ 145 passed
./financial_env/bin/python -m mutual_fund_ingestion --help
# Help text matches README commands
```

---

## Phase 2 — Document Discovery (Next Major Phase)

**Purpose**: Use Phase 1B provider profiles to discover and download actual disclosure documents.

**Gate to enter**: All Batches B–N complete, OR at minimum Batches E–L complete.

**Pre-work**: Read `docs/design/phase_2/` fully before writing a single line.

**Microtask spec**: Write Phase 2 microtasks before implementing. Follow `SKILL: write-spec` then decompose into tasks in `TASKS_FULL_SYSTEM_MICRO_PLAN.md`.

**Demonstrable artifact**: Phase 2 review notebook in `notebooks/mutual_fund_ingestion/02_phase_2_document_discovery.ipynb` showing:
- Provider profiles loaded
- Links discovered
- At least 1 file downloaded with metadata sidecar
- HTML report summary
