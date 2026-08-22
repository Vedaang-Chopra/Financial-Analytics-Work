# Story Notebook Series Tasks

**Plan:** `docs/06_plans/active/STORY_NOTEBOOK_SERIES_PLAN.md`  
**Status:** `STORY-NB-003` complete; next microtask is `STORY-NB-004`  
**Validation baseline:** `145 passed, 3 skipped`

## Rules

- Execute one microtask at a time.
- Touch at most one notebook or one small helper per implementation task.
- Do not delete notebooks or data.
- Do not change ingestion behavior.
- Keep live network calls optional and bounded.
- Update `docs/01_status/session_state.md` and `docs/06_plans/EXECUTION_RESULT.md` after each task.

## Microtasks

### STORY-NB-001 - Notebook Audit and Batch Setup

**Model hint:** planning  
**Rate limit flag:** no  
**Fallback:** complex-reasoning  
**Files to edit:** `docs/06_plans/active/STORY_NOTEBOOK_SERIES_TASKS.md`, `docs/06_plans/MICROTASK_SPEC.md`, `docs/06_plans/EXECUTION_RESULT.md`, `docs/01_status/session_state.md`  
**Verify command:** `./financial_env/bin/python -m pytest tests/ -q --tb=no`  
**Stop condition:** first notebook implementation task is ready; no notebooks edited.

### STORY-NB-002 - Public Inspection Helper Decision

**Model hint:** complex-reasoning  
**Rate limit flag:** no  
**Fallback:** local  
**Files to edit:** at most one helper module plus tests, only if approved by the current microtask  
**Verify command:** targeted helper tests, then full pytest  
**Stop condition:** helpers either implemented with tests or explicitly deferred.

### STORY-NB-003 - System Checkpoint Notebook

**Model hint:** fast-code  
**Rate limit flag:** yes  
**Fallback:** local  
**Files to edit:** `notebooks/mutual_fund_ingestion/00_system_checkpoint.ipynb`  
**Verify command:** structural assertion/stage check plus offline notebook execution if available  
**Status:** Complete (2026-06-29)  
**Stop condition:** notebook shows system health, artifact inventory, DB table inventory, and limits.

### STORY-NB-004 - Source Registry Story Notebook

**Model hint:** fast-code  
**Rate limit flag:** yes  
**Fallback:** local  
**Files to edit:** `notebooks/mutual_fund_ingestion/01a_phase_1_source_registry_review.ipynb`  
**Verify command:** structural assertion/stage check and artifact load check  
**Stop condition:** notebook explains source registry inputs, provenance, reference entries, and readiness.

### STORY-NB-005 - Provider Profile Story Notebook

**Model hint:** fast-code  
**Rate limit flag:** yes  
**Fallback:** local  
**Files to edit:** `notebooks/mutual_fund_ingestion/01b_phase_1_provider_profiling_review.ipynb`  
**Verify command:** profile artifact load and structural notebook check  
**Stop condition:** notebook explains provider strategy, candidate links, reports, and debug artifacts.

### STORY-NB-006 - Discovery and Candidate Story Notebook

**Model hint:** complex-reasoning  
**Rate limit flag:** no  
**Fallback:** local  
**Files to edit:** `notebooks/mutual_fund_ingestion/03_phase2_discovery_review.ipynb`  
**Verify command:** DB/run inspection check or documented offline blocker  
**Stop condition:** notebook shows source pages, discovered links, dataset candidates, and retry/debug state.

### STORY-NB-007 - Raw Artifact Download Story Notebook

**Model hint:** complex-reasoning  
**Rate limit flag:** no  
**Fallback:** local  
**Files to edit:** `notebooks/mutual_fund_ingestion/04_raw_artifact_download_story.ipynb`  
**Verify command:** raw artifact checksum/path assertions  
**Stop condition:** notebook proves one raw download or clearly shows why no artifact is available.

### STORY-NB-008 - Parse, Validate, and Load Story Notebook

**Model hint:** complex-reasoning  
**Rate limit flag:** no  
**Fallback:** local  
**Files to edit:** `notebooks/mutual_fund_ingestion/05_parse_validate_load_story.ipynb`  
**Verify command:** parser/validation/DB inspection checks from fixture or artifact  
**Stop condition:** notebook shows parsed rows, staging, validation, quarantine, and canonical table effects.

### STORY-NB-009 - Compatibility Cleanup

**Model hint:** local  
**Rate limit flag:** no  
**Fallback:** fast-code  
**Files to edit:** `01_phase_1_provider_profiling_review.ipynb`, `02_task_url_ingestion_agent_inspection.ipynb`, docs inventory  
**Verify command:** notebook inventory and stale-doc search  
**Stop condition:** duplicate notebooks are pointers or explicitly listed for archival. Do not delete without approval.

### STORY-NB-010 - Final Validation and Handoff

**Model hint:** planning  
**Rate limit flag:** no  
**Fallback:** complex-reasoning  
**Files to edit:** status/planning docs only  
**Verify command:** `./financial_env/bin/python -m pytest tests/ -q --tb=no` and notebook structural inventory  
**Stop condition:** series status is current and next implementation phase is clear.
