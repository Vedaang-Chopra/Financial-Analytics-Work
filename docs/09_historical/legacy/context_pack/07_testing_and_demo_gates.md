# Testing and Demo Gates

_What counts as "done" in this project. Created: 2026-06-23._

**A phase or batch is not complete merely because code compiles or tests are added.**
Each category below defines the minimum bar.

---

## General Rule

Every implemented feature must produce:
1. At least one passing test
2. A demonstrable inspection artifact (see category definitions below)
3. No regressions: full test suite (`./financial_env/bin/python -m pytest tests/ -q`) still passes

---

## Gate by Task Category

### Documentation-Only Tasks

**Done when**:
- Stale claim removed from the target document
- Verified against live codebase (grep or test output confirms)
- No stale claim survives in key agent-facing documents

**Demo artifact**: Run the grep command in the task's "Test command" section and show it returns no stale matches.

---

### Parser Tasks

**Done when**:
- Parser function exists and is importable
- Router entry exists in `parser/__init__.py`
- Unit test passes with a realistic fixture
- Parsed records have correct field names (security_name, percentage_to_nav, scheme_code, nav_value, etc.)
- Records are non-empty for valid input

**Demo artifact**: Test output showing parsed record count ≥ 1 with expected field values.

Example command:
```bash
./financial_env/bin/python -m pytest tests/test_agent.py -k "portfolio or nav or scheme_master" -v -q
```

**Not sufficient**: "Parser function exists." Must have a passing test with a fixture.

---

### Discovery Tasks

**Done when**:
- Relevance score is correct for known-good and known-bad URLs
- Dataset classification produces correct `dataset_type` for fixture HTML
- Link extraction returns expected count from fixture page

**Demo artifact**: Test output showing relevance scores and dataset types for named URLs.

---

### Database/Upsert Tasks

**Done when**:
- `init-db` creates the expected tables
- Upsert function produces a row in the canonical table
- ON CONFLICT behavior is correct (update, not insert duplicate)
- Row carries `raw_artifact_id` and `source_url` provenance

**Demo artifact**: DB integration test passing, showing row count ≥ 1 in the target table.

```bash
./financial_env/bin/python -m pytest tests/test_agent_db.py -v -q
```

---

### Validation/Quarantine Tasks

**Done when**:
- Valid records are accepted with no quarantine
- Invalid records (missing required field, bad value range) produce a quarantine row
- Quarantine row has a non-empty reason code
- Retry queue entry is created for recoverable failures

**Demo artifact**: Test showing accepted count + quarantined count + reason code for a known-bad record.

---

### Browser/VLM Tasks

**Done when**:
- `BrowserUnavailable` is raised when Playwright is not installed (test with mock)
- `extract_with_browser()` returns HTML, links, and screenshots in a fixture-based test
- `NullVLMClient.analyze_page()` returns None (no-op)
- `OllamaVLMClient.analyze_page()` makes an HTTP call to the VLM endpoint (test with mock)

**Demo artifact**: Test output confirming each of the above behaviors.

---

### End-to-End Fixture Tests

**Done when**:
- A fake seed HTML page is fetched (mocked HTTP)
- Source pages and discovered links are written to DB
- At least one dataset candidate is identified
- A fake file is downloaded (mocked download)
- The file is parsed and at least one canonical row is upserted
- The test verifies the canonical row count ≥ 1

**Demo artifact**: `test_agent_db.py` DB integration tests pass with ≥ 1 row in target table.

---

### Smoke Tests (Live Network)

**Done when**:
- AMFI seed page is reachable (HTTP 200 within timeout)
- At least one NAV link is discovered from the AMFI page
- No crash occurs during bounded crawl

**Demo artifact**: `test_smoke.py` passes (3 tests).

```bash
./financial_env/bin/python -m pytest tests/test_smoke.py -v -q
```

**Note**: Smoke tests are expected to run in CI or developer machines with network access. They are allowed to skip if network is unavailable.

---

### Phase Completion Gates

#### Phase 1A Complete
- [ ] `bootstrap-sources` CLI runs without error
- [ ] `data/raw/mutual_funds/source_registry/source_registry.latest.json` exists
- [ ] `data/reports/mutual_funds/source_registry_report.html` exists
- [ ] ≥ 10 providers in registry
- [ ] Review notebook 01a renders without error
- **Status: COMPLETE** ✅

#### Phase 1B Complete
- [ ] `profile-providers --limit 3` runs without error
- [ ] `data/raw/mutual_funds/provider_profiles/provider_profiles.latest.json` exists
- [ ] At least 1 provider has `detected_strategy` ≠ `unknown`
- [ ] Review notebook 01b renders without error
- **Status: COMPLETE** ✅

#### Task-URL Agent Core Complete
- [ ] `init-db` creates all 17 tables
- [ ] `run-agent` runs on AMFI URL without crash
- [ ] Source pages, discovered links, dataset candidates written to DB
- [ ] At least 1 artifact downloaded and parsed
- [ ] Canonical upsert succeeds for at least 1 record
- [ ] `inspect-run` shows all 9 table sections
- [ ] 125 tests pass
- **Status: SUBSTANTIALLY COMPLETE** ✅ (test coverage gaps remain)

#### Test Coverage Complete (Pre-Phase-2 Gate)
- [ ] Epics G, H, I, J, K, L, M, N, O, P, Q all complete
- [ ] Total test count ≥ 145
- [ ] No silent failures in any parser path
- [ ] All validators tested with valid and invalid input
- **Status: IN PROGRESS**

#### Phase 2 Complete
- [ ] At least 3 Phase 1B provider profiles traversed
- [ ] At least 1 portfolio Excel file discovered and downloaded
- [ ] File stored with metadata sidecar in `data/raw/mutual_funds/files/`
- [ ] HTML discovery report generated
- [ ] Review notebook 02 renders without error
- **Status: NOT STARTED**

---

## What Is NOT Sufficient

- "Code compiles" is not done
- "Function exists" is not done
- "Test added but skipped" is not done
- "I think it works" is not done
- A task is only complete when the exact `Test command` in the task spec returns the expected output
