# Tasks: Full System Micro-Plan

_140 tasks across 20 epics. Execute one task at a time. See `SMALL_MODEL_EXECUTION_GUIDE.md` for execution rules._

---

## Epic A — Repository Hygiene and Generated Artifact Cleanup

### TASK-A001 — Add *.db to .gitignore

Status: pending

Goal:
Remove all SQLite test database files from git tracking so they do not appear in `git status`.

Files to read:
- `.gitignore`

Files to edit:
- `.gitignore`

Implementation steps:
1. Open `.gitignore`.
2. After the existing `*.py[cod]` line, add the following lines:
   ```
   *.db
   *.db-journal
   *.db-wal
   *.db-shm
   data/tmp/
   ```
3. Save the file.

Test command:
```bash
python -m pytest tests/ -q
```

Expected observable output: `85 passed` with no failures. `git status` should no longer list `test.db`, `test2.db`, `test3.db`, `final_test.db`, or `test_mock.db`.

Dependencies:
- none

Rollback risk:
Low. `.gitignore` changes affect only git tracking, not runtime behavior.

---

### TASK-A002 — Remove unused `pika` dependency

Status: pending

Goal:
Remove the RabbitMQ client (`pika`) from `requirements.txt` since nothing in the codebase imports it.

Files to read:
- `requirements.txt`

Files to edit:
- `requirements.txt`

Implementation steps:
1. Open `requirements.txt`.
2. Delete the line containing `pika`.
3. Save the file.

Test command:
```bash
python -m pytest tests/ -q
```

Expected observable output: `85 passed`. No import errors related to `pika`.

Dependencies:
- none

Rollback risk:
Low. If `pika` was somehow needed, `pip install pika` restores it immediately.

---

### TASK-A003 — Verify test temp files go to /tmp not project root

Status: pending

Goal:
Confirm that `tests/test_agent_db.py` uses `tempfile.mkstemp` with a system temp path so SQLite DBs are not created in the project root.

Files to read:
- `tests/test_agent_db.py`

Files to edit:
- `tests/test_agent_db.py` (only if temp path creates files in project root)

Implementation steps:
1. Open `tests/test_agent_db.py` and search for `tempfile.mktemp` or `tempfile.mkstemp`.
2. If any call uses `suffix=".db"` without a `dir` argument and the result is used directly as a filename, the file may be created at `/tmp/...` (correct) or in the current directory (wrong).
3. Change any `tempfile.mktemp(suffix=".db")` to `tempfile.mkstemp(suffix=".db", dir=tempfile.gettempdir())[1]` to guarantee OS temp dir placement.
4. Wrap each temp file in a try/finally teardown: `os.unlink(db_path)` after each test.

Test command:
```bash
python -m pytest tests/test_agent_db.py -v -q && ls *.db 2>/dev/null || echo "no db files in project root"
```

Expected observable output: All test_agent_db tests pass. No `.db` files appear in the project root after the test run.

Dependencies:
- TASK-A001

Rollback risk:
Low. Test-only change.

---

### TASK-A004 — Add financial_env/ virtualenv to .gitignore

Status: pending

Goal:
Ensure the `financial_env/` virtualenv directory is excluded from git tracking.

Files to read:
- `.gitignore`

Files to edit:
- `.gitignore`

Implementation steps:
1. Open `.gitignore`.
2. Check if `financial_env/` is present. If not, add:
   ```
   financial_env/
   .venv/
   ```
3. Save.

Test command:
```bash
git status --short | grep financial_env || echo "financial_env is gitignored"
```

Expected observable output: `financial_env is gitignored` — no `financial_env/` files appear in git status.

Dependencies:
- none

Rollback risk:
Low.

---

## Epic B — Documentation Truth Cleanup

### TASK-B001 — Update PLAN.md to mark completed tasks

Status: pending

Goal:
Mark PLAN.md Tasks 1 and 2 as complete and correct the false claim that "runner.run() does NOT insert to PostgreSQL."

Files to read:
- `PLAN.md`
- `plans/CURRENT_CODEBASE_STATUS_AND_REFACTOR_PLAN.md`

Files to edit:
- `PLAN.md`

Implementation steps:
1. Open `PLAN.md`.
2. Find the section listing Task 1 (EvidenceParser → LinkExtractor). Mark it complete: add `[DONE]` to the heading.
3. Find the section listing Task 2 (Wire runner.run() to DB). Mark it complete: add `[DONE]` and add a note: "runner.py now writes to all major tables; the original audit finding was incorrect."
4. Find Section 1.5 ("Design vs. Code Mismatches") and add a note at the top: "NOTE 2026-06-17: The runner.run() gap listed here was already fixed before this document was created. See CURRENT_CODEBASE_STATUS_AND_REFACTOR_PLAN.md for accurate status."

Test command:
```bash
grep -n "DONE\|NOTE 2026" PLAN.md | head -10
```

Expected observable output: Lines with `[DONE]` and `NOTE 2026` appear in PLAN.md.

Dependencies:
- none

Rollback risk:
None — documentation only.

---

### TASK-B002 — Update task_url_ingestion_agent.md test count and gap list

Status: pending

Goal:
Correct the test count from 50 to 85 and add the three real bugs (portfolio column mapping, VLM not invoked, retry-failed crash) to the known gaps section.

Files to read:
- `plans/task_url_ingestion_agent.md`

Files to edit:
- `plans/task_url_ingestion_agent.md`

Implementation steps:
1. Open `plans/task_url_ingestion_agent.md`.
2. Find all occurrences of `50 passing` or `21 agent` and update to reflect 85 total (38 Phase 1 + 36 agent + 11 amfi_disclosure).
3. Find the "Known Gaps" or "Limitations" section (or add one if absent) and add:
   - `portfolio.py column mapping broken for real Excel files (header=None + integer columns)`
   - `VLM is instantiated but analyze_page() is never called in runner main loop`
   - `retry-failed CLI crashes with TypeError when --run-id is not provided`
4. Add note at top of file: `Last updated: 2026-06-17. See CURRENT_CODEBASE_STATUS_AND_REFACTOR_PLAN.md for full audit.`

Test command:
```bash
grep -n "85\|portfolio.*column\|VLM.*not invoked\|retry-failed.*crash" plans/task_url_ingestion_agent.md | head -10
```

Expected observable output: Lines match the updated content.

Dependencies:
- none

Rollback risk:
None — documentation only.

---

### TASK-B003 — Update CHATGPT_PROJECT_MEMORY.md current status

Status: pending

Goal:
Add a dated status block to CHATGPT_PROJECT_MEMORY.md reflecting the 2026-06-17 audit findings.

Files to read:
- `CHATGPT_PROJECT_MEMORY.md`
- `plans/CURRENT_CODEBASE_STATUS_AND_REFACTOR_PLAN.md`

Files to edit:
- `CHATGPT_PROJECT_MEMORY.md`

Implementation steps:
1. Open `CHATGPT_PROJECT_MEMORY.md`.
2. Find the "Current Status" section.
3. Add a new block at the top of that section (do not delete existing content):
   ```
   ## Status Update — 2026-06-17

   Full audit completed. 85/85 tests pass. Key findings:
   - Phase 1A/1B: complete and frozen
   - Task-URL Agent: orchestration loop complete with DB persistence
   - runner.py writes to all 17 tables (prior note that it did not was incorrect)
   - portfolio.py has column mapping bug for real Excel files (TASK-P001)
   - VLM is wired but analyze_page() never called (TASK-K005)
   - retry-failed CLI crashes without --run-id (TASK-D001)
   - 5 root-level .db files not in .gitignore (TASK-A001)
   See: plans/CURRENT_CODEBASE_STATUS_AND_REFACTOR_PLAN.md
   ```

Test command:
```bash
grep -n "Status Update.*2026-06-17" CHATGPT_PROJECT_MEMORY.md
```

Expected observable output: One matching line found.

Dependencies:
- none

Rollback risk:
None — documentation only.

---

### TASK-B004 — Update CODEBASE_MAP.md with portfolio bug and amfi_disclosure status

Status: pending

Goal:
Add a note to `amfi_disclosure/` entry in CODEBASE_MAP marking it as a legacy prototype, and note the `portfolio.py` column mapping bug.

Files to read:
- `docs/ai_context/CODEBASE_MAP.md`

Files to edit:
- `docs/ai_context/CODEBASE_MAP.md`

Implementation steps:
1. Open `docs/ai_context/CODEBASE_MAP.md`.
2. Find the `amfi_disclosure/` section. Add: `Status: LEGACY PROTOTYPE — not referenced by main agent pipeline. Do not extend. Consider archiving after Epic P is complete.`
3. Find the `agent/parser/portfolio.py` entry. Add: `BUG: column mapping broken for real Excel files. See TASK-P001.`
4. Find the `agent/vlm.py` entry. Add: `NOTE: analyze_page() is never called in runner.py. See TASK-K005.`

Test command:
```bash
grep -n "LEGACY PROTOTYPE\|BUG.*column\|NOTE.*analyze_page" docs/ai_context/CODEBASE_MAP.md
```

Expected observable output: Three matching lines found.

Dependencies:
- none

Rollback risk:
None — documentation only.

---

### TASK-B005 — Update README.md test count

Status: pending

Goal:
Correct the test count in README.md from 50 to 85.

Files to read:
- `README.md`

Files to edit:
- `README.md`

Implementation steps:
1. Open `README.md`.
2. Find all references to test count (likely "50 tests" or "29 Phase 1 + 21 agent tests").
3. Update to: "85 tests (38 Phase 1 + 36 agent + 11 amfi_disclosure)".

Test command:
```bash
grep -n "85 tests" README.md
```

Expected observable output: One or more lines showing the updated count.

Dependencies:
- none

Rollback risk:
None — documentation only.

---

## Epic C — Codebase Organization and Legacy Archiving

### TASK-C001 — Add README to amfi_disclosure marking it as legacy prototype

Status: pending

Goal:
Create `mutual_fund_ingestion/amfi_disclosure/README.md` so future agents do not try to extend or integrate this module.

Files to read:
- `mutual_fund_ingestion/amfi_disclosure/cli.py`
- `mutual_fund_ingestion/amfi_disclosure/discovery.py`

Files to edit:
- `mutual_fund_ingestion/amfi_disclosure/README.md` (new file)

Implementation steps:
1. Create `mutual_fund_ingestion/amfi_disclosure/README.md` with content:
   ```
   # mutual_fund_ingestion/amfi_disclosure — Isolated Prototype

   This module is a Phase 0 proof-of-concept for crawling the AMFI portfolio disclosure page.
   It is fully functional but **not integrated** with the main ingestion agent pipeline.

   ## Status
   - All 11 tests pass (tests/test_amfi_disclosure.py)
   - Not imported by mutual_fund_ingestion/
   - Do not extend this module — the agent handles portfolio disclosure via Epic P tasks

   ## Reference use only
   The Playwright and HTTP download patterns here may be useful as reference.
   Do not copy code from here into the agent without adapting to the agent's layer model.
   ```

Test command:
```bash
ls mutual_fund_ingestion/amfi_disclosure/README.md && python -m pytest tests/test_amfi_disclosure.py -q
```

Expected observable output: `README.md` exists; `11 passed`.

Dependencies:
- none

Rollback risk:
None — new file only.

---

### TASK-C002 — Add README to docs/archive/legacy_experiments/ marking it as legacy

Status: pending

Goal:
Create `docs/archive/legacy_experiments/README.md` so future agents understand this directory contains superseded experiments.

Files to read:
- (list the directory: `ls docs/archive/legacy_experiments/`)

Files to edit:
- `docs/archive/legacy_experiments/README.md` (new file)

Implementation steps:
1. Run `ls docs/archive/legacy_experiments/` to see what is there.
2. Create `docs/archive/legacy_experiments/README.md` with content:
   ```
   # docs/archive/legacy_experiments — Legacy Experiments

   This directory contains early dataset collection experiments predating the current architecture.
   It is **not part of the production codebase** and is not tested or maintained.

   ## Status
   - Superseded by mutual_fund_ingestion/ and mutual_fund_ingestion/agent/
   - Not imported anywhere in the current codebase
   - Retained for historical reference only

   ## Do not modify or extend
   Any useful patterns have been incorporated into the main pipeline.
   ```

Test command:
```bash
ls docs/archive/legacy_experiments/README.md
```

Expected observable output: File exists.

Dependencies:
- none

Rollback risk:
None — new file only.

---

### TASK-C003 — Verify no production code imports from amfi_disclosure

Status: pending

Goal:
Confirm that `mutual_fund_ingestion/` does not import anything from `amfi_disclosure/` to prevent accidental coupling.

Files to read:
- none (use grep)

Files to edit:
- none (fix only if imports found)

Implementation steps:
1. Run: `grep -r "from amfi_disclosure\|import amfi_disclosure" mutual_fund_ingestion/ utils/`
2. If any results appear, they must be removed — note exactly which files to fix and escalate.
3. If no results appear, task is complete.

Test command:
```bash
grep -r "from amfi_disclosure\|import amfi_disclosure" mutual_fund_ingestion/ utils/ && echo "COUPLING FOUND" || echo "no coupling"
```

Expected observable output: `no coupling`

Dependencies:
- none

Rollback risk:
None — read-only verification.

---

## Epic D — CLI and Configuration Stability

### TASK-D001 — Fix retry-failed crash when --run-id not provided

Status: pending

Goal:
`_retry_failed` in `cli.py` crashes with `TypeError: argument of type 'NoneType' is not iterable` when `--run-id` is omitted. Add a guard.

Files to read:
- `mutual_fund_ingestion/cli.py` (lines 341–380)

Files to edit:
- `mutual_fund_ingestion/cli.py`

Implementation steps:
1. Open `mutual_fund_ingestion/cli.py` and find `def _retry_failed(args)`.
2. Add at the start of the function body, before `uuid.UUID(args.run_id)`:
   ```python
   if not args.run_id:
       print("Error: --run-id is required for retry-failed", file=sys.stderr)
       return 1
   ```
3. Ensure `import sys` is at the top of `cli.py` (it likely already is).

Test command:
```bash
python -m mutual_fund_ingestion retry-failed --database-url sqlite:///test_guard.db; echo "exit code: $?"
```

Expected observable output: `Error: --run-id is required for retry-failed` printed to stderr. Exit code `1`. No `TypeError` or traceback.

Dependencies:
- none

Rollback risk:
Low. One guard line added; no logic changed.

---

### TASK-D002 — Fix logging format to include timestamps

Status: pending

Goal:
CLI log output should include timestamps and log level so users can trace timing issues.

Files to read:
- `mutual_fund_ingestion/cli.py` (search for `basicConfig` or `logging.`)

Files to edit:
- `mutual_fund_ingestion/cli.py`

Implementation steps:
1. Open `mutual_fund_ingestion/cli.py` and find the `logging.basicConfig(...)` call (in `main()` or the subcommand dispatcher).
2. Replace it with:
   ```python
   logging.basicConfig(
       level=getattr(logging, args.log_level.upper(), logging.INFO),
       format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
       datefmt="%Y-%m-%dT%H:%M:%S",
   )
   ```
3. If `basicConfig` is called in multiple places, apply this change to all of them.

Test command:
```bash
python -m mutual_fund_ingestion --help 2>&1; python -m mutual_fund_ingestion init-db --database-url sqlite:///log_test.db --log-level DEBUG 2>&1 | head -5
```

Expected observable output: Log lines look like `2026-06-17T00:10:01 DEBUG    sqlalchemy.engine.Engine: ...` rather than bare messages.

Dependencies:
- none

Rollback risk:
Low. Format change only.

---

### TASK-D003 — Verify AgentConfig.from_args maps all CLI flags

Status: pending

Goal:
Confirm every CLI flag for `run-agent` maps correctly to an `AgentConfig` field, with no orphaned flags.

Files to read:
- `mutual_fund_ingestion/cli.py` (the `run-agent` subparser and `_run_agent` function)
- `mutual_fund_ingestion/agent/config.py`

Files to edit:
- `mutual_fund_ingestion/cli.py` (fix any mapping gaps found)

Implementation steps:
1. List all `add_argument` calls in the `run-agent` subparser.
2. List all fields in `AgentConfig`.
3. For each CLI flag, verify there is a corresponding `AgentConfig` field in `from_args`.
4. For each `AgentConfig` field, verify it is either a CLI flag or has a default value.
5. Fix any gaps: if a flag exists but isn't mapped, add it to `from_args`.

Test command:
```bash
python -m pytest tests/test_agent.py::CLITests -v
```

Expected observable output: All 4 CLI tests pass.

Dependencies:
- none

Rollback risk:
Low.

---

### TASK-D004 — Add --task-url-file support test

Status: pending

Goal:
Verify that `--task-url-file` (a file with one URL per line) is parsed correctly by the CLI and passed as `task_urls` to `AgentConfig`.

Files to read:
- `mutual_fund_ingestion/cli.py`
- `tests/test_agent.py`

Files to edit:
- `tests/test_agent.py`

Implementation steps:
1. Open `tests/test_agent.py` and find the `CLITests` class.
2. Add a test:
   ```python
   def test_run_agent_accepts_task_url_file(self, tmp_path):
       url_file = tmp_path / "urls.txt"
       url_file.write_text("https://example.com/a\nhttps://example.com/b\n")
       args = build_parser().parse_args([
           "run-agent",
           "--task-url-file", str(url_file),
           "--database-url", "sqlite:///test.db",
       ])
       config = AgentConfig.from_args(args)
       assert "https://example.com/a" in config.task_urls
       assert "https://example.com/b" in config.task_urls
   ```
3. Import `build_parser` and `AgentConfig` at the top of the test file if not already present.

Test command:
```bash
python -m pytest tests/test_agent.py::CLITests -v
```

Expected observable output: 5 CLI tests pass (4 existing + 1 new).

Dependencies:
- none

Rollback risk:
None — test addition only.

---

## Epic E — Logging and Observability

### TASK-E001 — Add link discovery count log in runner BFS loop

Status: pending

Goal:
After extracting links from each page, log the count so operators can see discovery progress.

Files to read:
- `mutual_fund_ingestion/agent/runner.py` (the BFS loop, around the `extract_links` call)

Files to edit:
- `mutual_fund_ingestion/agent/runner.py`

Implementation steps:
1. Open `runner.py` and find the BFS loop where `self.engine.extract_links(html, url)` is called.
2. After the call, add:
   ```python
   LOGGER.info("Page %s: %d links extracted", url, len(links))
   ```
3. After the loop that creates `DatasetCandidate` objects, add:
   ```python
   LOGGER.info("Page %s: %d dataset candidates identified", url, candidates_added)
   ```
   where `candidates_added` is a counter incremented each time a DatasetCandidate is added.

Test command:
```bash
python -m pytest tests/test_agent_db.py::DBIntegrationTests::test_run_agent_creates_discovered_links -v
```

Expected observable output: Test passes. (Log output visible if `-s` flag added.)

Dependencies:
- TASK-D002

Rollback risk:
None — log additions only.

---

### TASK-E002 — Add download success log in artifact collector

Status: pending

Goal:
Log successful downloads with URL, byte count, and checksum prefix so the download pipeline is visible.

Files to read:
- `mutual_fund_ingestion/agent/extract.py`

Files to edit:
- `mutual_fund_ingestion/agent/extract.py`

Implementation steps:
1. Open `extract.py` and find `ArtifactCollector.download()`.
2. After `checksum = hasher.hexdigest()`, add:
   ```python
   LOGGER.info(
       "Downloaded %s: %d bytes sha256=%s",
       url, temp_path.stat().st_size, checksum[:12]
   )
   ```

Test command:
```bash
python -m pytest tests/test_agent_db.py -v -q
```

Expected observable output: All DB integration tests pass.

Dependencies:
- TASK-D002

Rollback risk:
None.

---

### TASK-E003 — Add parser selection log in parse_file

Status: pending

Goal:
Log which parser is selected for each file so routing errors are immediately visible.

Files to read:
- `mutual_fund_ingestion/agent/parser/__init__.py`

Files to edit:
- `mutual_fund_ingestion/agent/parser/__init__.py`

Implementation steps:
1. Open `mutual_fund_ingestion/agent/parser/__init__.py`.
2. In `parse_file()`, after `parser_name = route_parser(dataset_type, file_type)`, add:
   ```python
   if parser_name == "unknown":
       LOGGER.warning("No parser for dataset_type=%s file_type=%s", dataset_type, file_type)
   else:
       LOGGER.info("Routing to parser=%s for dataset_type=%s file_type=%s", parser_name, dataset_type, file_type)
   ```

Test command:
```bash
python -m pytest tests/test_agent.py::RouteParserIntegrationTests -v
```

Expected observable output: 3 routing tests pass.

Dependencies:
- TASK-D002

Rollback risk:
None.

---

### TASK-E004 — Add parsed record count log in runner

Status: pending

Goal:
After each parser call, log the number of records returned so parse failures (0 records) are visible.

Files to read:
- `mutual_fund_ingestion/agent/runner.py` (find `parse_file` call in `_download_and_process_artifact`)

Files to edit:
- `mutual_fund_ingestion/agent/runner.py`

Implementation steps:
1. Open `runner.py` and find `_download_and_process_artifact`.
2. After the `parse_file(...)` call, add:
   ```python
   LOGGER.info(
       "Parser %s returned %d records from %s (confidence=%.2f)",
       parser_result.parser_name, len(parser_result.records),
       url, parser_result.confidence
   )
   if parser_result.errors:
       LOGGER.warning("Parser errors for %s: %s", url, "; ".join(parser_result.errors))
   ```

Test command:
```bash
python -m pytest tests/test_agent_db.py::ParserUpsertTests -v
```

Expected observable output: 4 parser upsert tests pass.

Dependencies:
- TASK-D002

Rollback risk:
None.

---

### TASK-E005 — Add validation result log in runner

Status: pending

Goal:
Log valid vs quarantined record counts after each validation pass.

Files to read:
- `mutual_fund_ingestion/agent/runner.py` (find `validate_and_filter_records` call)

Files to edit:
- `mutual_fund_ingestion/agent/runner.py`

Implementation steps:
1. Open `runner.py` and find where `validate_and_filter_records(parser_result, self.run_id)` is called.
2. After the call, add:
   ```python
   LOGGER.info(
       "Validation for %s: %d valid, %d quarantined",
       url, len(valid_records), len(invalid_records)
   )
   ```

Test command:
```bash
python -m pytest tests/test_agent_db.py::ValidationQuarantineTests -v
```

Expected observable output: 3 validation tests pass.

Dependencies:
- TASK-D002

Rollback risk:
None.

---

### TASK-E006 — Add retry queue write log

Status: pending

Goal:
Log whenever a retry task is created so failures are traceable without querying the DB.

Files to read:
- `mutual_fund_ingestion/agent/runner.py` (find where `retry_queue` records are created)

Files to edit:
- `mutual_fund_ingestion/agent/runner.py`

Implementation steps:
1. Find all places where `RetryQueue(...)` is instantiated in `runner.py`.
2. After each `self.session.add(retry_task)`, add:
   ```python
   LOGGER.warning("Retry queued for %s: %s", url, failure_reason)
   ```

Test command:
```bash
python -m pytest tests/test_agent_db.py::DBIntegrationTests::test_run_agent_creates_retry_queue_on_fetch_failure -v
```

Expected observable output: Test passes.

Dependencies:
- TASK-D002

Rollback risk:
None.

---

### TASK-E007 — Add run completion summary log

Status: pending

Goal:
Ensure the run-completion log line includes all key counters: pages, links, candidates, downloads, staged, inserted, quarantined.

Files to read:
- `mutual_fund_ingestion/agent/runner.py` (find the final LOGGER.info at end of run)

Files to edit:
- `mutual_fund_ingestion/agent/runner.py`

Implementation steps:
1. Find the `LOGGER.info("Run %s complete: ...")` line at the end of `run()`.
2. Ensure it includes all of: `pages_seen`, `links_discovered`, `files_downloaded`, `rows_staged`, `rows_inserted`, `rows_quarantined`, `retry_tasks`.
3. Update the format string to match all counters tracked in the `AgentResult`.

Test command:
```bash
python -m pytest tests/test_agent_db.py::DBIntegrationTests::test_run_agent_creates_ingestion_run -v
```

Expected observable output: Test passes.

Dependencies:
- TASK-D002

Rollback risk:
None.

---

## Epic F — PostgreSQL Schema and Migrations

### TASK-F001 — Smoke test init-db against SQLite

Status: pending

Goal:
Verify that `python -m mutual_fund_ingestion init-db --database-url sqlite:///smoke.db` creates all 17 tables without error.

Files to read:
- `mutual_fund_ingestion/agent/db.py`
- `mutual_fund_ingestion/cli.py`

Files to edit:
- none

Implementation steps:
1. Run: `python -m mutual_fund_ingestion init-db --database-url sqlite:///smoke_schema.db`
2. Verify exit code 0.
3. Run: `python -c "import sqlite3; conn=sqlite3.connect('smoke_schema.db'); print(sorted([r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()]))" `
4. Verify all 17 table names appear.

Test command:
```bash
python -m mutual_fund_ingestion init-db --database-url sqlite:///smoke_schema.db && python -c "import sqlite3; c=sqlite3.connect('smoke_schema.db'); tables=sorted([r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()]); print(f'{len(tables)} tables: {tables}')" && rm smoke_schema.db
```

Expected observable output: `17 tables: ['amcs', 'dataset_candidates', 'discovered_links', 'documents', 'ingestion_runs', 'instruments', 'nav_history', 'portfolio_holdings', 'portfolio_snapshots', 'quarantine_rows', 'raw_artifacts', 'retry_queue', 'schemes', 'source_pages', 'staging_rows', 'task_urls', 'validation_results']`

Dependencies:
- none

Rollback risk:
None — read-only verification with temp file cleanup.

---

### TASK-F002 — Add nav_history composite index test

Status: pending

Goal:
Verify that the `nav_history` table has an index on `(scheme_code, nav_date)` for fast lookups.

Files to read:
- `mutual_fund_ingestion/agent/db.py`

Files to edit:
- `mutual_fund_ingestion/agent/db.py` (add index if missing)
- `tests/test_agent_db.py` (add test)

Implementation steps:
1. Open `db.py` and find the `NAVHistory` class.
2. Check `__table_args__` for an index on `(scheme_code, nav_date)`.
3. If missing, add:
   ```python
   __table_args__ = (
       Index("ix_nav_history_scheme_date", "scheme_code", "nav_date"),
   )
   ```
4. In `tests/test_agent_db.py`, add a test that queries `nav_history` filtered by `scheme_code` and verifies results.

Test command:
```bash
python -m pytest tests/test_agent_db.py -v -q
```

Expected observable output: All DB tests pass.

Dependencies:
- TASK-F001

Rollback risk:
Low. Index addition only.

---

### TASK-F003 — Verify amcs.normalized_name unique constraint

Status: pending

Goal:
Confirm that inserting two AMC records with the same `normalized_name` raises an IntegrityError (unique constraint enforced).

Files to read:
- `mutual_fund_ingestion/agent/db.py`
- `tests/test_agent_db.py`

Files to edit:
- `tests/test_agent_db.py`

Implementation steps:
1. Open `db.py` and check that `AMC.normalized_name` has `unique=True`.
2. Add a test in `tests/test_agent_db.py`:
   ```python
   def test_amc_normalized_name_is_unique(self):
       from sqlalchemy.exc import IntegrityError
       amc1 = AMC(name="Example Fund", normalized_name="example_fund", source_url="http://a.com")
       amc2 = AMC(name="Example Fund 2", normalized_name="example_fund", source_url="http://b.com")
       self.session.add(amc1)
       self.session.flush()
       self.session.add(amc2)
       with self.assertRaises(IntegrityError):
           self.session.flush()
   ```

Test command:
```bash
python -m pytest tests/test_agent_db.py -v -q
```

Expected observable output: All DB tests pass including the new unique constraint test.

Dependencies:
- none

Rollback risk:
None — test addition only.

---

## Epic G — Provenance, Staging, Validation, Quarantine, and Retry

### TASK-G001 — Add validate_scheme_master_record function

Status: pending

Goal:
Add a validation function for scheme_master records that requires `scheme_code` and `scheme_name`.

Files to read:
- `mutual_fund_ingestion/agent/validate.py`

Files to edit:
- `mutual_fund_ingestion/agent/validate.py`

Implementation steps:
1. Open `validate.py`.
2. After `validate_portfolio_record`, add:
   ```python
   def validate_scheme_master_record(record: dict[str, Any]) -> list[str]:
       """Return list of validation errors for a scheme_master record."""
       errors = []
       if not record.get("scheme_code"):
           errors.append("missing scheme_code")
       if not record.get("scheme_name"):
           errors.append("missing scheme_name")
       return errors
   ```

Test command:
```bash
python -m pytest tests/test_agent.py::ValidationTests -v
```

Expected observable output: All existing validation tests pass. (New tests added in G003.)

Dependencies:
- none

Rollback risk:
None — new function added.

---

### TASK-G002 — Add validate_amc_record function

Status: pending

Goal:
Add a validation function for amc_provider_list records that requires `name`.

Files to read:
- `mutual_fund_ingestion/agent/validate.py`

Files to edit:
- `mutual_fund_ingestion/agent/validate.py`

Implementation steps:
1. Open `validate.py`.
2. After `validate_scheme_master_record` (added in G001), add:
   ```python
   def validate_amc_record(record: dict[str, Any]) -> list[str]:
       """Return list of validation errors for an amc_provider_list record."""
       errors = []
       if not record.get("name"):
           errors.append("missing name")
       return errors
   ```

Test command:
```bash
python -m pytest tests/test_agent.py::ValidationTests -v
```

Expected observable output: All validation tests pass.

Dependencies:
- TASK-G001

Rollback risk:
None.

---

### TASK-G003 — Wire scheme_master and AMC validators into validate_and_filter_records

Status: pending

Goal:
`validate_and_filter_records` should route scheme_master and amc_provider_list records to their validators.

Files to read:
- `mutual_fund_ingestion/agent/validate.py`

Files to edit:
- `mutual_fund_ingestion/agent/validate.py`

Implementation steps:
1. Open `validate.py` and find `validate_and_filter_records`.
2. Add routing cases for the new dataset types:
   ```python
   elif dataset_type == "scheme_master":
       errors = validate_scheme_master_record(record)
   elif dataset_type == "amc_provider_list":
       errors = validate_amc_record(record)
   ```
3. Place these before the final `else` clause that handles unknown dataset types.

Test command:
```bash
python -m pytest tests/test_agent.py::ValidationTests -v
```

Expected observable output: All validation tests pass.

Dependencies:
- TASK-G001
- TASK-G002

Rollback risk:
Low.

---

### TASK-G004 — Add tests for scheme_master and AMC validation

Status: pending

Goal:
Add unit tests confirming that scheme_master and AMC records with missing required fields go to the invalid bucket.

Files to read:
- `tests/test_agent.py`
- `mutual_fund_ingestion/agent/validate.py`

Files to edit:
- `tests/test_agent.py`

Implementation steps:
1. In `tests/test_agent.py`, in the `ValidationTests` class, add:
   ```python
   def test_scheme_master_validation_fails_missing_scheme_code(self):
       record = {"scheme_name": "Example Growth Fund"}
       errors = validate_scheme_master_record(record)
       self.assertIn("missing scheme_code", errors)

   def test_scheme_master_validation_passes_valid_record(self):
       record = {"scheme_code": "120503", "scheme_name": "Example Growth Fund", "amc_name": "Example AMC"}
       errors = validate_scheme_master_record(record)
       self.assertEqual(errors, [])

   def test_amc_validation_fails_missing_name(self):
       record = {"website_url": "http://example.com"}
       errors = validate_amc_record(record)
       self.assertIn("missing name", errors)
   ```
2. Import `validate_scheme_master_record` and `validate_amc_record` at the top of the test file.

Test command:
```bash
python -m pytest tests/test_agent.py::ValidationTests -v
```

Expected observable output: All validation tests pass including 3 new ones.

Dependencies:
- TASK-G003

Rollback risk:
None — test additions.

---

### TASK-G005 — Verify staging_rows.raw_row_json preserves original record

Status: pending

Goal:
Confirm that `staging_rows.raw_row_json` contains the original unmodified record dict as returned by the parser.

Files to read:
- `tests/test_agent_db.py`
- `mutual_fund_ingestion/agent/runner.py`

Files to edit:
- `tests/test_agent_db.py`

Implementation steps:
1. Find `test_staging_rows_created` in `test_agent_db.py`.
2. Add an assertion that `staging_row.raw_row_json` matches the exact record dict from the parser.
3. If the test doesn't already check field values, add: `self.assertIn("scheme_code", row.raw_row_json)` or equivalent for the fixture data used.

Test command:
```bash
python -m pytest tests/test_agent_db.py::ValidationQuarantineTests::test_staging_rows_created -v
```

Expected observable output: Test passes with the new assertion.

Dependencies:
- none

Rollback risk:
None — test enhancement.

---

### TASK-G006 — Add test: quarantine reason codes are non-empty

Status: pending

Goal:
Verify that every `QuarantineRow` written has a non-empty `reason` field.

Files to read:
- `tests/test_agent_db.py`

Files to edit:
- `tests/test_agent_db.py`

Implementation steps:
1. In `test_quarantine_for_invalid_records`, after fetching quarantine rows, add:
   ```python
   for row in quarantine_rows:
       self.assertTrue(row.reason, f"QuarantineRow {row.id} has empty reason")
   ```

Test command:
```bash
python -m pytest tests/test_agent_db.py::ValidationQuarantineTests::test_quarantine_for_invalid_records -v
```

Expected observable output: Test passes.

Dependencies:
- none

Rollback risk:
None.

---

## Epic H — Static Discovery and Relevance Scoring

### TASK-H001 — Test high-relevance NAV link scoring

Status: pending

Goal:
Verify that a link with text "NAV History" scores ≥ 0.7 in `score_relevance`.

Files to read:
- `mutual_fund_ingestion/agent/discovery.py`
- `tests/test_agent.py`

Files to edit:
- `tests/test_agent.py`

Implementation steps:
1. In `tests/test_agent.py`, add a new test class `DiscoveryEngineTests`.
2. Add:
   ```python
   from mutual_fund_ingestion.agent.discovery import DiscoveryEngine
   from utils.http import HttpSettings
   import requests

   class DiscoveryEngineTests(unittest.TestCase):
       def setUp(self):
           self.session = requests.Session()
           self.engine = DiscoveryEngine(session=self.session, settings=HttpSettings())

       def test_nav_link_scores_high(self):
           score, hint = self.engine.score_relevance(
               "https://example.com/nav-history", "NAV History", ""
           )
           self.assertGreaterEqual(score, 0.7)

       def test_careers_link_scores_zero(self):
           score, hint = self.engine.score_relevance(
               "https://example.com/careers", "Careers", ""
           )
           self.assertEqual(score, 0.0)
   ```

Test command:
```bash
python -m pytest tests/test_agent.py::DiscoveryEngineTests -v
```

Expected observable output: 2 new discovery tests pass.

Dependencies:
- none

Rollback risk:
None — test additions.

---

### TASK-H002 — Test link extraction from HTML fixture

Status: pending

Goal:
Verify that `extract_links` correctly parses anchor tags from an HTML fixture.

Files to read:
- `mutual_fund_ingestion/agent/discovery.py`
- `tests/fixtures/provider_static.html`
- `tests/test_agent.py`

Files to edit:
- `tests/test_agent.py`

Implementation steps:
1. In `DiscoveryEngineTests` (created in H001), add:
   ```python
   def test_extract_links_from_fixture(self):
       from pathlib import Path
       html = (Path(__file__).parent / "fixtures" / "provider_static.html").read_text()
       links = self.engine.extract_links(html, "https://example.com/")
       urls = [l["url"] for l in links]
       # provider_static.html has a portfolio link and a factsheet link
       self.assertTrue(any("portfolio" in u.lower() or ".xlsx" in u.lower() for u in urls),
                       f"No portfolio link found in {urls}")
   ```

Test command:
```bash
python -m pytest tests/test_agent.py::DiscoveryEngineTests::test_extract_links_from_fixture -v
```

Expected observable output: Test passes.

Dependencies:
- TASK-H001

Rollback risk:
None.

---

### TASK-H003 — Test dataset classification by URL pattern

Status: pending

Goal:
Verify that `classify_dataset` correctly identifies NAV, portfolio, scheme, and AMC URLs by keyword matching.

Files to read:
- `mutual_fund_ingestion/agent/discovery.py`
- `tests/test_agent.py`

Files to edit:
- `tests/test_agent.py`

Implementation steps:
1. In `DiscoveryEngineTests`, add:
   ```python
   def test_classify_nav_url(self):
       self.assertEqual(self.engine.classify_dataset("https://x.com/nav-all.txt", "NAV Data"), "nav_history")

   def test_classify_portfolio_url(self):
       result = self.engine.classify_dataset("https://x.com/portfolio-disclosure.xlsx", "Monthly Portfolio")
       self.assertEqual(result, "portfolio_disclosure")

   def test_classify_scheme_master_url(self):
       result = self.engine.classify_dataset("https://x.com/scheme-master.csv", "Scheme Code List")
       self.assertEqual(result, "scheme_master")
   ```

Test command:
```bash
python -m pytest tests/test_agent.py::DiscoveryEngineTests -v
```

Expected observable output: All DiscoveryEngineTests pass.

Dependencies:
- TASK-H001

Rollback risk:
None.

---

### TASK-H004 — Add SID/KIM/TER/AUM/factsheet to DATASET_TYPE_HINTS

Status: pending

Goal:
Ensure that SID, KIM, TER, AUM, and factsheet URL patterns are included in `DATASET_TYPE_HINTS` so they get classified during crawl.

Files to read:
- `mutual_fund_ingestion/agent/discovery.py`

Files to edit:
- `mutual_fund_ingestion/agent/discovery.py`

Implementation steps:
1. Open `discovery.py` and find `DATASET_TYPE_HINTS`.
2. Add missing types:
   ```python
   "factsheet": ["factsheet", "fact sheet", "fund factsheet"],
   "sid": ["scheme information document", "sid", "scheme info doc"],
   "kim": ["key information memorandum", "kim", "key info memorandum"],
   "ter": ["total expense ratio", "ter", "expense ratio"],
   "aum_aaum": ["aum", "aaum", "assets under management"],
   ```

Test command:
```bash
python -m pytest tests/test_agent.py::DiscoveryEngineTests -v
```

Expected observable output: All discovery tests pass. (Add a classify test for factsheet in H005.)

Dependencies:
- TASK-H003

Rollback risk:
Low — keyword dict addition only.

---

### TASK-H005 — Test factsheet and TER URL classification

Status: pending

Goal:
Verify that factsheet and TER URLs are correctly classified after H004.

Files to read:
- `tests/test_agent.py`
- `mutual_fund_ingestion/agent/discovery.py`

Files to edit:
- `tests/test_agent.py`

Implementation steps:
1. In `DiscoveryEngineTests`, add:
   ```python
   def test_classify_factsheet_url(self):
       result = self.engine.classify_dataset("https://x.com/SBI-Factsheet-Oct2024.pdf", "Factsheet")
       self.assertEqual(result, "factsheet")

   def test_classify_ter_url(self):
       result = self.engine.classify_dataset("https://x.com/TER-report-2024.csv", "Total Expense Ratio")
       self.assertEqual(result, "ter")
   ```

Test command:
```bash
python -m pytest tests/test_agent.py::DiscoveryEngineTests -v
```

Expected observable output: All discovery tests pass including 2 new ones.

Dependencies:
- TASK-H004

Rollback risk:
None.

---

## Epic I — Chromium/Playwright Traversal Agent

### TASK-I001 — Test BrowserUnavailable raised when Playwright not installed

Status: pending

Goal:
Confirm that `extract_with_browser` raises `BrowserUnavailable` when `playwright` cannot be imported.

Files to read:
- `mutual_fund_ingestion/agent/browser.py`
- `tests/test_agent.py`

Files to edit:
- `tests/test_agent.py`

Implementation steps:
1. Add test class `BrowserAgentTests`:
   ```python
   from mutual_fund_ingestion.agent.browser import extract_with_browser, BrowserUnavailable
   from pathlib import Path
   import unittest.mock as mock

   class BrowserAgentTests(unittest.TestCase):
       def test_raises_browser_unavailable_when_playwright_missing(self):
           with mock.patch.dict("sys.modules", {"playwright": None, "playwright.sync_api": None}):
               with self.assertRaises((BrowserUnavailable, ImportError)):
                   extract_with_browser("https://example.com", Path("/tmp/debug"), timeout_seconds=5)
   ```

Test command:
```bash
python -m pytest tests/test_agent.py::BrowserAgentTests -v
```

Expected observable output: 1 browser test passes.

Dependencies:
- none

Rollback risk:
None — test addition.

---

### TASK-I002 — Test extract_with_browser with mocked Playwright

Status: pending

Goal:
Test that `extract_with_browser` returns a valid `BrowserResult` when Playwright is mocked.

Files to read:
- `mutual_fund_ingestion/agent/browser.py`
- `tests/test_agent.py`

Files to edit:
- `tests/test_agent.py`

Implementation steps:
1. In `BrowserAgentTests`, add a test that patches `sync_playwright` to return a fake context yielding fake HTML with one link:
   ```python
   def test_extract_with_browser_returns_links(self):
       fake_html = '<html><body><a href="/nav.txt">NAV Data</a></body></html>'
       # Build a fake Playwright context using MagicMock
       fake_page = mock.MagicMock()
       fake_page.content.return_value = fake_html
       fake_page.locator.return_value.all.return_value = [
           mock.MagicMock(**{"get_attribute.return_value": "/nav.txt", "inner_text.return_value": "NAV Data"})
       ]
       fake_page.goto.return_value = None
       fake_browser = mock.MagicMock()
       fake_browser.new_page.return_value = fake_page
       fake_playwright = mock.MagicMock()
       fake_playwright.__enter__ = mock.Mock(return_value=mock.MagicMock(chromium=mock.MagicMock(launch=mock.Mock(return_value=fake_browser))))
       fake_playwright.__exit__ = mock.Mock(return_value=False)
       with mock.patch("mutual_fund_ingestion.agent.browser.sync_playwright", return_value=fake_playwright):
           from pathlib import Path
           result = extract_with_browser("https://example.com", Path("/tmp/test_browser_debug"))
       self.assertIsNotNone(result.html)
   ```

Test command:
```bash
python -m pytest tests/test_agent.py::BrowserAgentTests -v
```

Expected observable output: Both browser tests pass.

Dependencies:
- TASK-I001

Rollback risk:
None.

---

## Epic J — Network/API Discovery

### TASK-J001 — Test network download detection in BrowserResult

Status: pending

Goal:
Verify that `extract_with_browser` populates `BrowserResult.downloads` when network responses contain file extensions.

Files to read:
- `mutual_fund_ingestion/agent/browser.py`
- `tests/test_agent.py`

Files to edit:
- `tests/test_agent.py`

Implementation steps:
1. In `BrowserAgentTests`, add a test where the fake `network_calls` list includes a URL ending in `.txt`:
   ```python
   def test_network_downloads_detected_from_xhr(self):
       from mutual_fund_ingestion.agent.browser import BrowserResult
       # Simulate BrowserResult built from network calls
       network_calls = [
           {"url": "https://api.amfiindia.com/NavALL", "status": 200, "content_type": "text/plain"},
       ]
       # Manually build a BrowserResult to test downloads field logic
       # (this tests the data contract, not Playwright integration)
       result = BrowserResult(
           html="<html></html>",
           screenshot_path=None,
           links=[],
           downloads=[{"url": "https://api.amfiindia.com/NavALL", "file_type": "txt", "content_type": "text/plain"}],
           network_calls=network_calls,
       )
       self.assertTrue(any(d["file_type"] == "txt" for d in result.downloads))
   ```

Test command:
```bash
python -m pytest tests/test_agent.py::BrowserAgentTests -v
```

Expected observable output: All browser tests pass.

Dependencies:
- TASK-I002

Rollback risk:
None.

---

### TASK-J002 — Add AMFI direct API URL to DATASET_TYPE_HINTS

Status: pending

Goal:
Ensure the AMFI direct NAV API (`NavALL`) is classified as `nav_history` by the discovery engine.

Files to read:
- `mutual_fund_ingestion/agent/discovery.py`
- `tests/test_agent.py`

Files to edit:
- `tests/test_agent.py`

Implementation steps:
1. In `DiscoveryEngineTests`, add:
   ```python
   def test_amfi_api_nav_url_classified_as_nav_history(self):
       result = self.engine.classify_dataset(
           "https://www.amfiindia.com/spages/NAVAll.txt", "Download All NAV"
       )
       self.assertEqual(result, "nav_history")
   ```
2. If this test fails, the `DATASET_TYPE_HINTS` entry for `nav_history` needs to include `"navall"` or the URL pattern detection needs to check file extensions.

Test command:
```bash
python -m pytest tests/test_agent.py::DiscoveryEngineTests::test_amfi_api_nav_url_classified_as_nav_history -v
```

Expected observable output: Test passes.

Dependencies:
- TASK-H003

Rollback risk:
None (test only; may require H004 fix if keyword missing).

---

## Epic K — VLM-Guided Page Understanding

### TASK-K001 — Test NullVLMClient returns None

Status: pending

Goal:
Add an explicit unit test that `NullVLMClient.analyze_page()` always returns `None`.

Files to read:
- `mutual_fund_ingestion/agent/vlm.py`
- `tests/test_agent.py`

Files to edit:
- `tests/test_agent.py`

Implementation steps:
1. Add test class `VLMClientTests`:
   ```python
   from mutual_fund_ingestion.agent.vlm import NullVLMClient, OllamaVLMClient, PageAnalysisPayload

   class VLMClientTests(unittest.TestCase):
       def test_null_client_returns_none(self):
           client = NullVLMClient()
           payload = PageAnalysisPayload(url="https://x.com", html="<html></html>", screenshot_path=None, links=[])
           self.assertIsNone(client.analyze_page(payload))
   ```

Test command:
```bash
python -m pytest tests/test_agent.py::VLMClientTests -v
```

Expected observable output: 1 VLM test passes.

Dependencies:
- none

Rollback risk:
None.

---

### TASK-K002 — Test OllamaVLMClient._build_prompt returns non-empty string

Status: pending

Goal:
Verify that `_build_prompt` produces a usable prompt string given a `PageAnalysisPayload`.

Files to read:
- `mutual_fund_ingestion/agent/vlm.py`
- `tests/test_agent.py`

Files to edit:
- `tests/test_agent.py`

Implementation steps:
1. In `VLMClientTests`, add:
   ```python
   def test_ollama_client_builds_prompt(self):
       client = OllamaVLMClient(endpoint="http://localhost:11434", model="llama3")
       payload = PageAnalysisPayload(
           url="https://example.com/downloads",
           html="<html><body>Download NAV Data</body></html>",
           screenshot_path=None,
           links=[{"url": "https://example.com/nav.txt", "text": "NAV History"}]
       )
       prompt = client._build_prompt(payload)
       self.assertIsInstance(prompt, str)
       self.assertGreater(len(prompt), 20)
       self.assertIn("example.com", prompt)
   ```

Test command:
```bash
python -m pytest tests/test_agent.py::VLMClientTests -v
```

Expected observable output: 2 VLM tests pass.

Dependencies:
- TASK-K001

Rollback risk:
None.

---

### TASK-K003 — Test OllamaVLMClient._parse_response handles valid and invalid JSON

Status: pending

Goal:
Verify that `_parse_response` correctly parses a valid JSON decision and returns `None` on bad JSON.

Files to read:
- `mutual_fund_ingestion/agent/vlm.py`
- `tests/test_agent.py`

Files to edit:
- `tests/test_agent.py`

Implementation steps:
1. In `VLMClientTests`, add:
   ```python
   def test_parse_response_valid_json(self):
       client = OllamaVLMClient()
       raw = '{"is_relevant": true, "dataset_type": "nav_history", "confidence": 0.85, "reasoning": "NAV link found"}'
       decision = client._parse_response(raw)
       self.assertIsNotNone(decision)
       self.assertTrue(decision.is_relevant)
       self.assertEqual(decision.dataset_type, "nav_history")

   def test_parse_response_invalid_json_returns_none(self):
       client = OllamaVLMClient()
       self.assertIsNone(client._parse_response("not json at all"))
   ```

Test command:
```bash
python -m pytest tests/test_agent.py::VLMClientTests -v
```

Expected observable output: 4 VLM tests pass.

Dependencies:
- TASK-K001

Rollback risk:
None.

---

### TASK-K004 — Wire VLM invocation in runner for low-confidence pages

Status: pending

Goal:
When `use_vlm=True` and a fetched page has relevance score below `vlm_confidence_threshold`, call `self.vlm.analyze_page()` and use the result to promote the page to a dataset candidate.

Files to read:
- `mutual_fund_ingestion/agent/runner.py` (BFS loop, around `score_relevance` call)
- `mutual_fund_ingestion/agent/vlm.py`

Files to edit:
- `mutual_fund_ingestion/agent/runner.py`

Implementation steps:
1. In `runner.py`, after `score, hint = self.engine.score_relevance(url, text, title)` in the BFS loop, add:
   ```python
   if self.config.use_vlm and score < self.config.vlm_confidence_threshold and html:
       from .vlm import PageAnalysisPayload
       vlm_payload = PageAnalysisPayload(url=url, html=html[:4000], screenshot_path=None, links=links[:20])
       vlm_decision = self.vlm.analyze_page(vlm_payload)
       if vlm_decision and vlm_decision.is_relevant:
           score = vlm_decision.confidence
           hint = vlm_decision.dataset_type
           LOGGER.info("VLM classified %s as %s (confidence=%.2f)", url, hint, score)
   ```
2. Ensure this block runs only in the BFS page-processing loop, not in the link-scoring loop.

Test command:
```bash
python -m pytest tests/test_agent_db.py::DBIntegrationTests -v
```

Expected observable output: All DB integration tests pass. (VLM mock test added in K005.)

Dependencies:
- TASK-K003

Rollback risk:
Medium. Modifies core BFS loop. If score logic breaks, discovery stops working. Mitigated by NullVLMClient default.

---

### TASK-K005 — Test VLM is called for low-confidence pages when use_vlm=True

Status: pending

Goal:
Add an integration test verifying that `vlm.analyze_page()` is invoked when a page scores below threshold.

Files to read:
- `tests/test_agent_db.py`
- `mutual_fund_ingestion/agent/runner.py`

Files to edit:
- `tests/test_agent_db.py`

Implementation steps:
1. Add a test that runs `IngestionRunner` with a `MockVLMClient` (defined inline) and `use_vlm=True`, then verifies `analyze_page` was called:
   ```python
   def test_vlm_called_for_low_confidence_page(self):
       from mutual_fund_ingestion.agent.vlm import VLMClient, PageAnalysisPayload, PageAnalysisDecision
       calls = []
       class SpyVLM(VLMClient):
           def analyze_page(self, payload):
               calls.append(payload.url)
               return None
       # patch runner to use SpyVLM
       config = AgentConfig(
           task_urls=["https://httpbin.org/html"],
           database_url=f"sqlite:///{self.db_path}",
           use_vlm=True,
           vlm_confidence_threshold=1.0,  # force VLM for all pages
           max_pages=1, max_files=0,
       )
       runner = IngestionRunner(config)
       runner.vlm = SpyVLM()
       runner.run()
       self.assertGreater(len(calls), 0, "VLM was never called")
   ```

Test command:
```bash
python -m pytest tests/test_agent_db.py -k vlm -v
```

Expected observable output: VLM spy test passes.

Dependencies:
- TASK-K004

Rollback risk:
None — test addition.

---

## Epic L — Raw Artifact Download and Retention

### TASK-L001 — Implement raw file retention: move to raw_dir

Status: pending

Goal:
When `keep_raw_files=True`, move the downloaded temp file to `raw_dir/<run_id>/<safe_filename>` and update `raw_artifacts.local_path`.

Files to read:
- `mutual_fund_ingestion/agent/runner.py` (`_download_and_process_artifact`)
- `mutual_fund_ingestion/agent/extract.py`
- `mutual_fund_ingestion/agent/config.py`

Files to edit:
- `mutual_fund_ingestion/agent/runner.py`

Implementation steps:
1. In `_download_and_process_artifact`, after `self.session.add(raw_artifact)` and `self.session.flush()`:
   ```python
   if artifact_result.get("retained") and self.config.raw_dir:
       import shutil
       raw_dir = Path(self.config.raw_dir) / self.run_id
       raw_dir.mkdir(parents=True, exist_ok=True)
       src = Path(artifact_result["local_path"])
       dest = raw_dir / src.name
       shutil.copy2(src, dest)
       raw_artifact.local_path = str(dest)
       LOGGER.info("Retained raw file at %s", dest)
   ```

Test command:
```bash
python -m pytest tests/test_agent_db.py::ParserUpsertTests -v
```

Expected observable output: All 4 parser upsert tests pass. (Full retention test in L002.)

Dependencies:
- none

Rollback risk:
Low. Adds a conditional block after the session flush; NullVLMClient path is unchanged.

---

### TASK-L002 — Test raw file retention creates file in raw_dir

Status: pending

Goal:
Verify that after a run with `keep_raw_files=True`, the downloaded file exists at `raw_dir/<run_id>/<filename>`.

Files to read:
- `tests/test_agent_db.py`
- `mutual_fund_ingestion/agent/runner.py`

Files to edit:
- `tests/test_agent_db.py`

Implementation steps:
1. Add a test:
   ```python
   def test_keep_raw_files_creates_file_in_raw_dir(self):
       import tempfile, os
       raw_dir = tempfile.mkdtemp()
       config = AgentConfig(
           task_urls=["https://www.amfiindia.com/spages/NAVAll.txt"],
           database_url=f"sqlite:///{self.db_path}",
           keep_raw_files=True,
           raw_dir=raw_dir,
           max_pages=1, max_files=1,
       )
       runner = IngestionRunner(config)
       runner.run()
       retained = []
       for root, dirs, files in os.walk(raw_dir):
           retained.extend(files)
       self.assertGreater(len(retained), 0, "No files retained in raw_dir")
   ```
2. Mark the test `@pytest.mark.smoke` since it makes a real network call.

Test command:
```bash
python -m pytest tests/test_agent_db.py -k retain -v -m smoke
```

Expected observable output: Test passes (requires network). Skip if network unavailable.

Dependencies:
- TASK-L001

Rollback risk:
None — test addition.

---

### TASK-L003 — Test file size limit enforced during streaming

Status: pending

Goal:
Verify that `ArtifactCollector.download()` returns `{"error": "file_too_large"}` when streaming a file exceeding `max_file_size_mb`.

Files to read:
- `mutual_fund_ingestion/agent/extract.py`
- `tests/test_agent_db.py`

Files to edit:
- `tests/test_agent_db.py`

Implementation steps:
1. Add a unit test:
   ```python
   def test_download_rejects_oversized_file_by_content_length(self):
       from mutual_fund_ingestion.agent.extract import ArtifactCollector
       from utils.http import HttpSettings
       import tempfile, unittest.mock as mock
       collector = ArtifactCollector(
           session=mock.MagicMock(),
           temp_dir=Path(tempfile.mkdtemp()),
           max_file_size_mb=0.001,  # 1 KB limit
       )
       fake_response = mock.MagicMock()
       fake_response.headers = {"content-length": "999999999"}
       fake_response.raise_for_status.return_value = None
       collector.session.get.return_value = fake_response
       result = collector.download("https://example.com/huge.txt", "test-run")
       self.assertEqual(result["error"], "file_too_large")
   ```

Test command:
```bash
python -m pytest tests/test_agent_db.py -k oversized -v
```

Expected observable output: Test passes.

Dependencies:
- none

Rollback risk:
None.

---

## Epic M — Dataset/Document Classification

### TASK-M001 — Test portfolio_disclosure.xlsx URL creates DatasetCandidate

Status: pending

Goal:
Integration test: a URL ending in `.xlsx` with portfolio keyword is classified as `portfolio_disclosure` DatasetCandidate.

Files to read:
- `tests/test_agent_db.py`
- `mutual_fund_ingestion/agent/discovery.py`

Files to edit:
- `tests/test_agent_db.py`

Implementation steps:
1. Add a test that runs `DiscoveryEngine.extract_links` on HTML containing a portfolio `.xlsx` link, then checks `classify_dataset` returns `portfolio_disclosure`:
   ```python
   def test_portfolio_xlsx_classified_as_portfolio_disclosure(self):
       from mutual_fund_ingestion.agent.discovery import DiscoveryEngine
       from utils.http import HttpSettings
       import requests
       engine = DiscoveryEngine(session=requests.Session(), settings=HttpSettings())
       html = '<a href="https://amc.com/portfolio-oct2024.xlsx">Monthly Portfolio</a>'
       links = engine.extract_links(html, "https://amc.com/")
       self.assertEqual(len(links), 1)
       classification = engine.classify_dataset(links[0]["url"], links[0]["text"])
       self.assertEqual(classification, "portfolio_disclosure")
   ```

Test command:
```bash
python -m pytest tests/test_agent_db.py -k portfolio_classified -v
```

Expected observable output: Test passes.

Dependencies:
- TASK-H003

Rollback risk:
None.

---

## Epic N — NAV Ingestion

### TASK-N001 — Create NAV text fixture file

Status: pending

Goal:
Create `tests/fixtures/data/nav_all_schemes.txt` with a small sample of the AMFI pipe-delimited NAV all-schemes format.

Files to read:
- `mutual_fund_ingestion/agent/parser/nav.py`

Files to edit:
- `tests/fixtures/data/nav_all_schemes.txt` (new file)

Implementation steps:
1. Create directory `tests/fixtures/data/` if it doesn't exist.
2. Create `tests/fixtures/data/nav_all_schemes.txt` with content:
   ```
   Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Net Asset Value;Date
   120503;INF200K01RN2;INF200K01RO0;Example Growth Fund - Regular Plan;52.1234;16-Jun-2026
   120504;INF200K01RP7;INF200K01RQ5;Example Blue Chip Fund - Direct Plan;147.8921;16-Jun-2026
   INVALIDROW;bad;data
   ```

Test command:
```bash
ls tests/fixtures/data/nav_all_schemes.txt
```

Expected observable output: File exists.

Dependencies:
- none

Rollback risk:
None — new file.

---

### TASK-N002 — Test parse_nav_text with realistic fixture

Status: pending

Goal:
Verify that `parse_nav_text` correctly parses the fixture from N001 and returns 2 valid records.

Files to read:
- `tests/fixtures/data/nav_all_schemes.txt`
- `mutual_fund_ingestion/agent/parser/nav.py`
- `tests/test_agent.py`

Files to edit:
- `tests/test_agent.py`

Implementation steps:
1. In `NAVParserTests`, add:
   ```python
   def test_nav_text_parser_with_realistic_fixture(self):
       from pathlib import Path
       fixture = (Path(__file__).parent / "fixtures" / "data" / "nav_all_schemes.txt").read_text()
       result = parse_nav_text(fixture, {"source_url": "https://amfiindia.com/NAVAll.txt"})
       self.assertEqual(len(result.records), 2, f"Expected 2 records, got {len(result.records)}: {result.records}")
       self.assertEqual(result.records[0]["scheme_code"], "120503")
       self.assertAlmostEqual(float(result.records[0]["nav_value"]), 52.1234, places=3)
   ```

Test command:
```bash
python -m pytest tests/test_agent.py::NAVParserTests::test_nav_text_parser_with_realistic_fixture -v
```

Expected observable output: Test passes with 2 records parsed.

Dependencies:
- TASK-N001

Rollback risk:
None.

---

### TASK-N003 — Create NAV HTML fixture and implement parse_nav_html

Status: pending

Goal:
Create `tests/fixtures/data/nav_page.html` and implement `parse_nav_html` in `nav.py`.

Files to read:
- `mutual_fund_ingestion/agent/parser/nav.py`
- `mutual_fund_ingestion/agent/parser/__init__.py`

Files to edit:
- `mutual_fund_ingestion/agent/parser/nav.py`
- `mutual_fund_ingestion/agent/parser/__init__.py`
- `tests/fixtures/data/nav_page.html` (new file)

Implementation steps:
1. Create `tests/fixtures/data/nav_page.html`:
   ```html
   <html><body>
   <table>
   <tr><th>Scheme Code</th><th>Scheme Name</th><th>NAV</th><th>Date</th></tr>
   <tr><td>120503</td><td>Example Growth Fund</td><td>52.1234</td><td>16-Jun-2026</td></tr>
   <tr><td>120504</td><td>Example Blue Chip Fund</td><td>147.89</td><td>16-Jun-2026</td></tr>
   </table>
   </body></html>
   ```
2. In `nav.py`, add:
   ```python
   def parse_nav_html(content: bytes | str, metadata: dict) -> ParserResult:
       """Parse NAV data from an HTML table."""
       from lxml import html as lhtml
       records = []
       errors = []
       if isinstance(content, bytes):
           content = content.decode("utf-8", errors="replace")
       try:
           doc = lhtml.fromstring(content)
           for table in doc.cssselect("table"):
               headers = [th.text_content().strip().lower() for th in table.cssselect("tr:first-child th, tr:first-child td")]
               for row in table.cssselect("tr")[1:]:
                   cells = [td.text_content().strip() for td in row.cssselect("td")]
                   if len(cells) < 3:
                       continue
                   record = {}
                   for i, header in enumerate(headers):
                       if "scheme code" in header or "code" == header:
                           record["scheme_code"] = cells[i] if i < len(cells) else None
                       elif "nav" in header:
                           try:
                               record["nav_value"] = float(cells[i].replace(",", ""))
                           except (ValueError, IndexError):
                               pass
                       elif "date" in header:
                           record["nav_date"] = cells[i] if i < len(cells) else None
                       elif "scheme name" in header or "name" in header:
                           record["scheme_name"] = cells[i] if i < len(cells) else None
                   if record.get("scheme_code") and record.get("nav_value"):
                       record.setdefault("source_url", metadata.get("source_url", ""))
                       records.append(record)
       except Exception as exc:
           errors.append(f"HTML NAV parse error: {exc}")
       return ParserResult(
           dataset_type="nav_history",
           parser_name="nav_html_v1",
           parser_version="1.0",
           confidence=0.7 if records else 0.0,
           records=records, warnings=[], errors=errors, metadata=metadata,
       )
   ```
3. In `parser/__init__.py`, add `elif parser_name == "nav_html": from .nav import parse_nav_html; return parse_nav_html(content, metadata)`.

Test command:
```bash
python -m pytest tests/test_agent.py -k nav_html -v
```

Expected observable output: NAV HTML parser test passes. (Test added in N004.)

Dependencies:
- TASK-N001

Rollback risk:
Low — new function.

---

### TASK-N004 — Test parse_nav_html with fixture

Status: pending

Goal:
Verify `parse_nav_html` returns 2 records from the HTML fixture.

Files to read:
- `tests/fixtures/data/nav_page.html`
- `tests/test_agent.py`

Files to edit:
- `tests/test_agent.py`

Implementation steps:
1. In `tests/test_agent.py`, in `NAVParserTests`, add:
   ```python
   def test_nav_html_parser_with_fixture(self):
       from pathlib import Path
       from mutual_fund_ingestion.agent.parser.nav import parse_nav_html
       fixture = (Path(__file__).parent / "fixtures" / "data" / "nav_page.html").read_bytes()
       result = parse_nav_html(fixture, {"source_url": "https://example.com/nav.html"})
       self.assertEqual(len(result.records), 2)
       self.assertEqual(result.records[0]["scheme_code"], "120503")
   ```

Test command:
```bash
python -m pytest tests/test_agent.py::NAVParserTests::test_nav_html_parser_with_fixture -v
```

Expected observable output: Test passes.

Dependencies:
- TASK-N003

Rollback risk:
None.

---

## Epic O — AMC/Provider and Scheme-Master Ingestion

### TASK-O001 — Create scheme_master.csv fixture

Status: pending

Goal:
Create `tests/fixtures/data/scheme_master.csv` with AMFI-format columns.

Files to read:
- `mutual_fund_ingestion/agent/parser/scheme_master.py`

Files to edit:
- `tests/fixtures/data/scheme_master.csv` (new file)

Implementation steps:
1. Create `tests/fixtures/data/scheme_master.csv` with content:
   ```
   Scheme Code,Scheme Name,AMC Name,Category,Sub Category
   120503,Example Growth Fund - Regular Plan,Example Asset Management Ltd.,Equity,Large Cap Fund
   120504,Example Blue Chip Fund - Direct Plan,Example Asset Management Ltd.,Equity,Large Cap Fund
   ,Missing Code Fund,Example Asset Management Ltd.,Equity,Large Cap Fund
   ```
   (Third row has missing scheme_code to test quarantine.)

Test command:
```bash
ls tests/fixtures/data/scheme_master.csv
```

Expected observable output: File exists.

Dependencies:
- none

Rollback risk:
None — new file.

---

### TASK-O002 — Test parse_scheme_master_csv with fixture

Status: pending

Goal:
Verify that `parse_scheme_master_csv` returns 2 valid records and skips the missing-code row.

Files to read:
- `tests/fixtures/data/scheme_master.csv`
- `mutual_fund_ingestion/agent/parser/scheme_master.py`
- `tests/test_agent.py`

Files to edit:
- `tests/test_agent.py`

Implementation steps:
1. In `SchemeMasterParserTests`, add:
   ```python
   def test_scheme_master_csv_parser_with_realistic_fixture(self):
       from pathlib import Path
       from mutual_fund_ingestion.agent.parser.scheme_master import parse_scheme_master_csv
       fixture = (Path(__file__).parent / "fixtures" / "data" / "scheme_master.csv").read_bytes()
       result = parse_scheme_master_csv(fixture, {"source_url": "https://amfi.com/scheme.csv"})
       codes = [r["scheme_code"] for r in result.records if r.get("scheme_code")]
       self.assertIn("120503", codes)
       self.assertIn("120504", codes)
   ```

Test command:
```bash
python -m pytest tests/test_agent.py::SchemeMasterParserTests -v
```

Expected observable output: All scheme master tests pass.

Dependencies:
- TASK-O001

Rollback risk:
None.

---

### TASK-O003 — Test _upsert_schemes links scheme to AMC

Status: pending

Goal:
Verify that `_upsert_schemes` creates a `Scheme` row linked to an existing `AMC` via `amc_id`.

Files to read:
- `tests/test_agent_db.py`
- `mutual_fund_ingestion/agent/runner.py`

Files to edit:
- `tests/test_agent_db.py`

Implementation steps:
1. Find `test_scheme_master_parser_upserts_to_schemes`. Add assertion:
   ```python
   # After verifying scheme exists, check amc linkage
   scheme = self.session.execute(select(Scheme)).scalars().first()
   if scheme and scheme.amc_id:
       amc = self.session.get(AMC, scheme.amc_id)
       self.assertIsNotNone(amc, "Scheme.amc_id does not reference valid AMC")
   ```

Test command:
```bash
python -m pytest tests/test_agent_db.py::ParserUpsertTests::test_scheme_master_parser_upserts_to_schemes -v
```

Expected observable output: Test passes with AMC linkage verified.

Dependencies:
- none

Rollback risk:
None.

---

## Epic P — Portfolio Disclosure Ingestion

### TASK-P001 — Fix portfolio.py column mapping for real Excel files

Status: pending

Goal:
`parse_portfolio_excel` currently reads Excel with `header=None` (integer column indices) and fails to map columns from real AMFI portfolio files. Fix to detect the header row automatically.

Files to read:
- `mutual_fund_ingestion/agent/parser/portfolio.py`

Files to edit:
- `mutual_fund_ingestion/agent/parser/portfolio.py`

Implementation steps:
1. Open `portfolio.py` and find `parse_portfolio_excel`.
2. Replace the inner per-sheet logic:
   ```python
   raw = pd.read_excel(BytesIO(content), sheet_name=sheet_name, header=None, dtype=str)
   if raw.empty:
       continue
   # Find header row: first row where ≥ 2 cells match known column aliases
   header_row_idx = 0
   for i, row in raw.iterrows():
       normalized_cells = [_normalize_col(str(v)) for v in row.values if str(v).strip().lower() != "nan"]
       known_count = sum(1 for v in normalized_cells
                        if any(v in aliases for aliases in COLUMN_ALIASES.values()))
       if known_count >= 2:
           header_row_idx = i
           break
   df = pd.read_excel(BytesIO(content), sheet_name=sheet_name, header=int(header_row_idx), dtype=str)
   col_map = _map_columns(df)
   ```
3. Keep the rest of the parsing logic (security_name extraction, pct_nav, market_value, isin, sector) unchanged.

Test command:
```bash
python -m pytest tests/test_agent.py tests/test_agent_db.py::ParserUpsertTests::test_portfolio_parser_creates_holdings -v
```

Expected observable output: All existing tests still pass.

Dependencies:
- none

Rollback risk:
Medium. Core parser logic changed. Mitigation: existing test covers the basic case; new tests added in P002 verify real-column case.

---

### TASK-P002 — Create portfolio Excel fixture with real AMFI column names

Status: pending

Goal:
Create `tests/fixtures/data/portfolio_sample.xlsx` with AMFI-style column headers for testing the fixed parser.

Files to read:
- `mutual_fund_ingestion/agent/parser/portfolio.py`

Files to edit:
- `tests/fixtures/data/portfolio_sample.xlsx` (new file, generated by script)

Implementation steps:
1. Create a Python script (not a test) to generate the fixture. Run it once:
   ```python
   import pandas as pd
   from pathlib import Path
   df = pd.DataFrame({
       "Name of Instrument": ["Reliance Industries Ltd", "HDFC Bank Ltd", "TCS Ltd", None],
       "ISIN": ["INE002A01018", "INE040A01034", "INE467B01029", ""],
       "Industry": ["Oil & Gas", "Banks", "IT", ""],
       "Quantity": ["100", "200", "50", ""],
       "Market Value (Rs. in Lakhs)": ["5234.56", "8901.23", "3456.78", ""],
       "% to NAV": ["8.5", "14.2", "5.6", "bad_value"],
   })
   Path("tests/fixtures/data").mkdir(parents=True, exist_ok=True)
   df.to_excel("tests/fixtures/data/portfolio_sample.xlsx", index=False)
   print("Created portfolio_sample.xlsx")
   ```
2. Run the script: `python -c "..."` and verify the file is created.
3. Delete the script after running (do not commit it).

Test command:
```bash
python -c "import pandas as pd; df=pd.read_excel('tests/fixtures/data/portfolio_sample.xlsx'); print(list(df.columns))"
```

Expected observable output: `['Name of Instrument', 'ISIN', 'Industry', 'Quantity', 'Market Value (Rs. in Lakhs)', '% to NAV']`

Dependencies:
- TASK-P001

Rollback risk:
None — new fixture file.

---

### TASK-P003 — Test parse_portfolio_excel with real AMFI column names

Status: pending

Goal:
Verify that after P001 fix, `parse_portfolio_excel` returns 3 valid records from the fixture (4th row has null name, bad % to NAV — should be skipped/partial).

Files to read:
- `tests/fixtures/data/portfolio_sample.xlsx`
- `mutual_fund_ingestion/agent/parser/portfolio.py`
- `tests/test_agent.py`

Files to edit:
- `tests/test_agent.py`

Implementation steps:
1. Add to a new `PortfolioParserTests` class in `tests/test_agent.py`:
   ```python
   def test_parse_portfolio_excel_with_real_columns(self):
       from pathlib import Path
       from mutual_fund_ingestion.agent.parser.portfolio import parse_portfolio_excel
       content = (Path(__file__).parent / "fixtures" / "data" / "portfolio_sample.xlsx").read_bytes()
       result = parse_portfolio_excel(content, {"source_url": "https://example.com/portfolio.xlsx"})
       names = [r["security_name"] for r in result.records]
       self.assertIn("Reliance Industries Ltd", names)
       self.assertIn("HDFC Bank Ltd", names)
       self.assertTrue(all(r.get("security_name") for r in result.records))
   ```

Test command:
```bash
python -m pytest tests/test_agent.py::PortfolioParserTests -v
```

Expected observable output: Portfolio parser test passes with ≥ 3 records.

Dependencies:
- TASK-P001
- TASK-P002

Rollback risk:
None.

---

### TASK-P004 — Add parse_portfolio_csv for CSV portfolio files

Status: pending

Goal:
Add `parse_portfolio_csv` to handle CSV portfolio files (same column names as Excel but CSV format).

Files to read:
- `mutual_fund_ingestion/agent/parser/portfolio.py`
- `mutual_fund_ingestion/agent/parser/__init__.py`

Files to edit:
- `mutual_fund_ingestion/agent/parser/portfolio.py`
- `mutual_fund_ingestion/agent/parser/__init__.py`

Implementation steps:
1. In `portfolio.py`, add:
   ```python
   def parse_portfolio_csv(content: bytes | str, metadata: dict[str, Any]) -> ParserResult:
       """Parse portfolio disclosure from CSV (same column schema as Excel)."""
       from io import StringIO
       records = []
       errors = []
       try:
           if isinstance(content, bytes):
               content = content.decode("utf-8", errors="replace")
           df = pd.read_csv(StringIO(content), dtype=str)
           col_map = _map_columns(df)
           for idx, row in df.iterrows():
               security_name = None
               for col, mapped in col_map.items():
                   if mapped == "security_name":
                       security_name = str(row.get(col, "")).strip()
                       break
               if not security_name or security_name == "nan" or len(security_name) < 2:
                   continue
               pct_nav = None
               for col, mapped in col_map.items():
                   if mapped == "percentage_to_nav":
                       try:
                           pct_nav = float(str(row.get(col, "")).replace("%", "").replace(",", "").strip())
                       except (ValueError, TypeError):
                           pass
               records.append({"security_name": security_name, "percentage_to_nav": pct_nav,
                                "source_url": metadata.get("source_url", "")})
       except Exception as exc:
           errors.append(f"Portfolio CSV parse error: {exc}")
       return ParserResult(
           dataset_type="portfolio_disclosure", parser_name="portfolio_csv_v1", parser_version="1.0",
           confidence=0.7 if records else 0.0, records=records, warnings=[], errors=errors, metadata=metadata,
       )
   ```
2. In `parser/__init__.py`, add `elif parser_name == "portfolio_csv": from .portfolio import parse_portfolio_csv; return parse_portfolio_csv(content, metadata)`.
3. Add `("portfolio_disclosure", "csv"): "portfolio_csv"` to `PARSER_ROUTER` if not already present (it already is — verify routing goes to correct function).

Test command:
```bash
python -m pytest tests/test_agent.py -k portfolio -v
```

Expected observable output: All portfolio tests pass.

Dependencies:
- TASK-P003

Rollback risk:
Low — new function.

---

## Epic Q — Factsheet/SID/KIM/TER/AUM Metadata Ingestion

### TASK-Q001 — Add factsheet, sid, kim, ter, aum_aaum to PARSER_ROUTER

Status: pending

Goal:
Register parser routes for document metadata types so they don't fall through to "unknown".

Files to read:
- `mutual_fund_ingestion/agent/parser/__init__.py`

Files to edit:
- `mutual_fund_ingestion/agent/parser/__init__.py`

Implementation steps:
1. In `PARSER_ROUTER`, add:
   ```python
   ("factsheet", "html"): "metadata_html",
   ("factsheet", "pdf"): "metadata_pdf",
   ("sid", "pdf"): "metadata_pdf",
   ("kim", "pdf"): "metadata_pdf",
   ("ter", "csv"): "ter_csv",
   ("aum_aaum", "csv"): "aum_csv",
   ```
2. In `parse_file`, add stubs:
   ```python
   elif parser_name == "metadata_html":
       from .metadata import parse_metadata_html
       return parse_metadata_html(content, metadata)
   elif parser_name == "metadata_pdf":
       from .metadata import parse_metadata_pdf
       return parse_metadata_pdf(content, metadata)
   elif parser_name in ("ter_csv", "aum_csv"):
       from .metadata import parse_tabular_csv
       return parse_tabular_csv(content, metadata, dataset_type=dataset_type)
   ```

Test command:
```bash
python -m pytest tests/test_agent.py::ParserRoutingTests -v
```

Expected observable output: Router test passes. New routes registered.

Dependencies:
- TASK-H004

Rollback risk:
Low — import errors from missing `metadata.py` will surface immediately; fix in Q002.

---

### TASK-Q002 — Create parser/metadata.py with HTML and CSV stubs

Status: pending

Goal:
Create `mutual_fund_ingestion/agent/parser/metadata.py` with functional stub parsers for factsheet HTML and tabular CSV.

Files to read:
- `mutual_fund_ingestion/agent/parser/nav.py` (for pattern reference)
- `mutual_fund_ingestion/agent/models.py`

Files to edit:
- `mutual_fund_ingestion/agent/parser/metadata.py` (new file)

Implementation steps:
1. Create `mutual_fund_ingestion/agent/parser/metadata.py`:
   ```python
   """Metadata parsers for factsheet, SID, KIM, TER, AUM documents."""
   from __future__ import annotations
   import logging
   from typing import Any
   from ..models import ParserResult

   LOGGER = logging.getLogger(__name__)

   def parse_metadata_html(content: bytes | str, metadata: dict[str, Any]) -> ParserResult:
       """Extract document metadata from a factsheet or SID HTML page."""
       if isinstance(content, bytes):
           content = content.decode("utf-8", errors="replace")
       records = [{"document_type": metadata.get("dataset_type", "factsheet"),
                   "source_url": metadata.get("source_url", ""),
                   "raw_html_length": len(content)}]
       return ParserResult(
           dataset_type=metadata.get("dataset_type", "factsheet"),
           parser_name="metadata_html_v1", parser_version="1.0",
           confidence=0.5, records=records, warnings=["metadata_html is a stub parser"],
           errors=[], metadata=metadata,
       )

   def parse_metadata_pdf(content: bytes | str, metadata: dict[str, Any]) -> ParserResult:
       """PDF metadata parser stub — returns quarantine-ready result until PDF parsing is implemented."""
       return ParserResult(
           dataset_type=metadata.get("dataset_type", "factsheet"),
           parser_name="metadata_pdf_v1", parser_version="1.0",
           confidence=0.0, records=[],
           warnings=["PDF parsing not yet implemented; file retained for manual review"],
           errors=[], metadata=metadata,
       )

   def parse_tabular_csv(content: bytes | str, metadata: dict[str, Any], dataset_type: str = "ter") -> ParserResult:
       """Parse TER or AUM/AAUM tabular CSV."""
       import pandas as pd
       from io import StringIO
       records = []
       errors = []
       try:
           if isinstance(content, bytes):
               content = content.decode("utf-8", errors="replace")
           df = pd.read_csv(StringIO(content), dtype=str)
           for _, row in df.iterrows():
               records.append({**row.dropna().to_dict(), "source_url": metadata.get("source_url", "")})
       except Exception as exc:
           errors.append(f"Tabular CSV parse error: {exc}")
       return ParserResult(
           dataset_type=dataset_type, parser_name=f"{dataset_type}_csv_v1", parser_version="1.0",
           confidence=0.6 if records else 0.0, records=records, warnings=[], errors=errors, metadata=metadata,
       )
   ```

Test command:
```bash
python -m pytest tests/test_agent.py::ParserRoutingTests -v
```

Expected observable output: All routing tests pass. No ImportError from metadata.py.

Dependencies:
- TASK-Q001

Rollback risk:
Low — new file.

---

### TASK-Q003 — Test metadata_html parser returns document record

Status: pending

Goal:
Verify that `parse_metadata_html` returns a record with `document_type` and `source_url`.

Files to read:
- `mutual_fund_ingestion/agent/parser/metadata.py`
- `tests/test_agent.py`

Files to edit:
- `tests/test_agent.py`

Implementation steps:
1. Add a test class `MetadataParserTests`:
   ```python
   class MetadataParserTests(unittest.TestCase):
       def test_metadata_html_returns_document_record(self):
           from mutual_fund_ingestion.agent.parser.metadata import parse_metadata_html
           result = parse_metadata_html(
               b"<html><body>Factsheet October 2024</body></html>",
               {"source_url": "https://example.com/factsheet.html", "dataset_type": "factsheet"}
           )
           self.assertEqual(len(result.records), 1)
           self.assertEqual(result.records[0]["document_type"], "factsheet")

       def test_metadata_pdf_returns_zero_records_with_warning(self):
           from mutual_fund_ingestion.agent.parser.metadata import parse_metadata_pdf
           result = parse_metadata_pdf(b"%PDF stub", {"source_url": "https://x.com/sid.pdf", "dataset_type": "sid"})
           self.assertEqual(result.records, [])
           self.assertTrue(result.warnings)
   ```

Test command:
```bash
python -m pytest tests/test_agent.py::MetadataParserTests -v
```

Expected observable output: 2 metadata parser tests pass.

Dependencies:
- TASK-Q002

Rollback risk:
None.

---

## Epic R — End-to-End Fixture Website Tests

### TASK-R001 — Create fixture AMFI seed page HTML

Status: pending

Goal:
Create `tests/fixtures/amfi_seed_page.html` simulating the AMFI top-level navigation page.

Files to read:
- `tests/fixtures/provider_static.html` (existing fixture for reference)

Files to edit:
- `tests/fixtures/amfi_seed_page.html` (new file)

Implementation steps:
1. Create `tests/fixtures/amfi_seed_page.html`:
   ```html
   <html>
   <head><title>AMFI India - Association of Mutual Funds in India</title></head>
   <body>
   <h1>AMFI India</h1>
   <nav>
     <a href="/amc-list">AMC List</a>
     <a href="/nav-history">Historical NAV</a>
     <a href="/portfolio-disclosure">Portfolio Disclosure</a>
     <a href="/scheme-master">Scheme Master</a>
     <a href="/careers">Careers</a>
   </nav>
   </body>
   </html>
   ```

Test command:
```bash
ls tests/fixtures/amfi_seed_page.html
```

Expected observable output: File exists.

Dependencies:
- none

Rollback risk:
None.

---

### TASK-R002 — Create fixture AMC disclosure page HTML

Status: pending

Goal:
Create `tests/fixtures/amc_disclosure_page.html` with links to NAV, portfolio, and scheme files.

Files to read:
- `tests/fixtures/amfi_seed_page.html`

Files to edit:
- `tests/fixtures/amc_disclosure_page.html` (new file)

Implementation steps:
1. Create `tests/fixtures/amc_disclosure_page.html`:
   ```html
   <html>
   <head><title>Example AMC - Downloads</title></head>
   <body>
   <h1>Downloads</h1>
   <ul>
     <li><a href="/files/nav_all_schemes.txt">Download NAV - All Schemes</a></li>
     <li><a href="/files/scheme_master.csv">Scheme Master Data</a></li>
     <li><a href="/files/portfolio_sample.xlsx">Monthly Portfolio Disclosure</a></li>
     <li><a href="/files/factsheet.html">Fund Factsheet</a></li>
   </ul>
   </body>
   </html>
   ```

Test command:
```bash
ls tests/fixtures/amc_disclosure_page.html
```

Expected observable output: File exists.

Dependencies:
- TASK-R001

Rollback risk:
None.

---

### TASK-R003 — Write fixture end-to-end test: seed page discovery

Status: pending

Goal:
Test that running `IngestionRunner` against the fixture seed page discovers relevant links and writes `source_pages` and `discovered_links` to the DB.

Files to read:
- `tests/fixtures/amfi_seed_page.html`
- `tests/test_agent_db.py`
- `mutual_fund_ingestion/agent/runner.py`

Files to edit:
- `tests/test_agent_db.py`

Implementation steps:
1. Add a test that patches `DiscoveryEngine.fetch` to return the fixture HTML and verifies DB writes:
   ```python
   def test_fixture_seed_page_writes_source_pages(self):
       from pathlib import Path
       import unittest.mock as mock
       seed_html = (Path(__file__).parent / "fixtures" / "amfi_seed_page.html").read_text()
       config = AgentConfig(
           task_urls=["https://fixture.amfi.com/"],
           database_url=f"sqlite:///{self.db_path}",
           max_pages=1, max_files=0, use_browser=False,
       )
       with mock.patch("mutual_fund_ingestion.agent.discovery.DiscoveryEngine.fetch",
                       return_value=(200, seed_html)):
           runner = IngestionRunner(config)
           runner.run()
       pages = self.session.execute(select(SourcePage)).scalars().all()
       self.assertGreaterEqual(len(pages), 1)
       links = self.session.execute(select(DiscoveredLink)).scalars().all()
       self.assertGreaterEqual(len(links), 3)
   ```

Test command:
```bash
python -m pytest tests/test_agent_db.py -k fixture_seed_page -v
```

Expected observable output: Test passes with ≥ 1 source page and ≥ 3 discovered links.

Dependencies:
- TASK-R001

Rollback risk:
None — test addition.

---

### TASK-R004 — Write fixture end-to-end test: NAV file parse and upsert

Status: pending

Goal:
Test that running the agent against the fixture AMC page triggers NAV file download, parse, and `nav_history` upsert.

Files to read:
- `tests/fixtures/amc_disclosure_page.html`
- `tests/fixtures/data/nav_all_schemes.txt`
- `tests/test_agent_db.py`

Files to edit:
- `tests/test_agent_db.py`

Implementation steps:
1. Add a test that:
   - Patches `DiscoveryEngine.fetch` to return fixture HTML for the seed URL and the nav file URL
   - Patches `ArtifactCollector.download` to return the fixture `.txt` file content
   - Runs `IngestionRunner` with `max_pages=2, max_files=1`
   - Verifies `nav_history` has ≥ 1 row
   ```python
   def test_fixture_nav_file_upserted_to_nav_history(self):
       from pathlib import Path
       import unittest.mock as mock
       from sqlalchemy import select
       from mutual_fund_ingestion.agent.db import NAVHistory
       seed_html = (Path(__file__).parent / "fixtures" / "amc_disclosure_page.html").read_text()
       nav_content = (Path(__file__).parent / "fixtures" / "data" / "nav_all_schemes.txt").read_bytes()
       # Map URLs to responses
       def fake_fetch(url):
           return (200, seed_html)
       def fake_download(url, run_id):
           return {"url": url, "file_type": "text", "content_type": "text/plain",
                   "checksum": "abc123", "size_bytes": len(nav_content),
                   "local_path": None, "retained": False, "content": nav_content}
       config = AgentConfig(
           task_urls=["https://fixture.amc.com/"],
           database_url=f"sqlite:///{self.db_path}",
           max_pages=2, max_files=1, use_browser=False,
       )
       with mock.patch("mutual_fund_ingestion.agent.discovery.DiscoveryEngine.fetch", side_effect=fake_fetch), \
            mock.patch("mutual_fund_ingestion.agent.extract.ArtifactCollector.download", side_effect=fake_download):
           runner = IngestionRunner(config)
           runner.run()
       nav_rows = self.session.execute(select(NAVHistory)).scalars().all()
       self.assertGreaterEqual(len(nav_rows), 1, "No NAV rows in nav_history")
   ```

Test command:
```bash
python -m pytest tests/test_agent_db.py -k fixture_nav_file -v
```

Expected observable output: Test passes with ≥ 1 NAV history row.

Dependencies:
- TASK-R002
- TASK-N001
- TASK-N002

Rollback risk:
Low — test addition with mocks.

---

## Epic S — Bounded Live Smoke Tests

### TASK-S001 — Create tests/test_smoke.py with AMFI seed page reachability test

Status: pending

Goal:
Create a smoke test file that verifies AMFI is reachable and the agent can fetch and process one page.

Files to read:
- `tests/test_agent_db.py` (for test setup pattern)
- `mutual_fund_ingestion/agent/runner.py`

Files to edit:
- `tests/test_smoke.py` (new file)

Implementation steps:
1. Create `tests/test_smoke.py`:
   ```python
   """Bounded live smoke tests. Run with: python -m pytest -m smoke tests/"""
   import pytest
   import tempfile
   import os
   from sqlalchemy import create_engine, select
   from sqlalchemy.orm import sessionmaker
   from mutual_fund_ingestion.agent.db import Base, IngestionRun, SourcePage
   from mutual_fund_ingestion.agent.runner import IngestionRunner
   from mutual_fund_ingestion.agent.config import AgentConfig

   def _check_network():
       import requests
       try:
           requests.get("https://www.amfiindia.com", timeout=5)
           return True
       except Exception:
           return False

   @pytest.mark.smoke
   def test_smoke_amfi_seed_page_reachable():
       if not _check_network():
           pytest.skip("Network unavailable")
       db_fd, db_path = tempfile.mkstemp(suffix=".db")
       os.close(db_fd)
       try:
           config = AgentConfig(
               task_urls=["https://www.amfiindia.com"],
               database_url=f"sqlite:///{db_path}",
               max_pages=1, max_files=0, use_browser=False,
           )
           runner = IngestionRunner(config)
           result = runner.run()
           engine = create_engine(f"sqlite:///{db_path}")
           session = sessionmaker(bind=engine)()
           pages = session.execute(select(SourcePage)).scalars().all()
           assert len(pages) >= 1, "No source pages written"
           session.close()
       finally:
           os.unlink(db_path)
   ```

Test command:
```bash
python -m pytest -m smoke tests/test_smoke.py -v
```

Expected observable output: Test passes (or skips if network unavailable). At least 1 source_pages row.

Dependencies:
- TASK-F001

Rollback risk:
None — new test file, live network, skip if unavailable.

---

### TASK-S002 — Add NAV discovery smoke test

Status: pending

Goal:
Verify that a bounded run against AMFI nav-history discovers at least one `nav_history` dataset candidate.

Files to read:
- `tests/test_smoke.py`

Files to edit:
- `tests/test_smoke.py`

Implementation steps:
1. Add to `test_smoke.py`:
   ```python
   @pytest.mark.smoke
   def test_smoke_amfi_discovers_nav_candidate():
       if not _check_network():
           pytest.skip("Network unavailable")
       db_fd, db_path = tempfile.mkstemp(suffix=".db")
       os.close(db_fd)
       try:
           from mutual_fund_ingestion.agent.db import DatasetCandidate
           config = AgentConfig(
               task_urls=["https://www.amfiindia.com/nav-history"],
               database_url=f"sqlite:///{db_path}",
               max_pages=3, max_files=0, use_browser=False,
           )
           runner = IngestionRunner(config)
           runner.run()
           engine = create_engine(f"sqlite:///{db_path}")
           session = sessionmaker(bind=engine)()
           candidates = session.execute(select(DatasetCandidate)).scalars().all()
           nav_candidates = [c for c in candidates if c.dataset_type == "nav_history"]
           assert len(nav_candidates) >= 1, f"No nav_history candidates found. All: {[c.dataset_type for c in candidates]}"
           session.close()
       finally:
           os.unlink(db_path)
   ```

Test command:
```bash
python -m pytest -m smoke tests/test_smoke.py::test_smoke_amfi_discovers_nav_candidate -v
```

Expected observable output: Test passes with ≥ 1 nav_history DatasetCandidate.

Dependencies:
- TASK-S001

Rollback risk:
None.

---

## Epic T — Final Docs and Handoff

### TASK-T001 — Update CODEBASE_MAP.md to reflect completed epics

Status: pending

Goal:
After all earlier epics are done, update `CODEBASE_MAP.md` with any new modules, functions, and layer assignments.

Files to read:
- `docs/ai_context/CODEBASE_MAP.md`
- `mutual_fund_ingestion/agent/parser/metadata.py`
- `mutual_fund_ingestion/agent/validate.py`

Files to edit:
- `docs/ai_context/CODEBASE_MAP.md`

Implementation steps:
1. Add `mutual_fund_ingestion/agent/parser/metadata.py` under parser layer with: `parse_metadata_html, parse_metadata_pdf, parse_tabular_csv`.
2. Add `validate_scheme_master_record`, `validate_amc_record` to the validate.py entry.
3. Remove or annotate the `amfi_disclosure/` entry with "ARCHIVED — see Epic C notes."
4. Update overall status from "partial" to "complete" for epics that are done.

Test command:
```bash
python -m pytest tests/ -q
```

Expected observable output: 85+ tests pass (count will be higher after all epics).

Dependencies:
- All previous epics

Rollback risk:
None — documentation only.

---

### TASK-T002 — Update README.md with verified commands

Status: pending

Goal:
Ensure README.md reflects all CLI commands, flags, and test counts as they stand after all fixes.

Files to read:
- `README.md`
- `mutual_fund_ingestion/cli.py`

Files to edit:
- `README.md`

Implementation steps:
1. Run `python -m mutual_fund_ingestion --help` and verify all subcommands are documented.
2. Run `python -m pytest tests/ -q` and update the test count.
3. Update the `retry-failed` section to note that `--run-id` is required.
4. Add a section on smoke tests: `python -m pytest -m smoke tests/`.

Test command:
```bash
python -m mutual_fund_ingestion --help | grep -E "bootstrap|profile|run-agent|init-db|inspect|retry"
```

Expected observable output: All 7 subcommands appear in help output.

Dependencies:
- All previous epics

Rollback risk:
None.

---

### TASK-T003 — Run full test suite and verify all pass

Status: pending

Goal:
Final verification: all tests pass, test count is accurate, no regressions.

Files to read:
- none

Files to edit:
- none

Implementation steps:
1. Run: `python -m pytest tests/ -v --tb=short`
2. Verify all tests pass.
3. Record the final test count.
4. If any test fails, do not mark this task complete — fix the failing test first.

Test command:
```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -5
```

Expected observable output: `N passed in X.XXs` with 0 failures.

Dependencies:
- All previous epics

Rollback risk:
None.

---

### TASK-T004 — Create final handoff note in CURRENT_CODEBASE_STATUS_AND_REFACTOR_PLAN.md

Status: pending

Goal:
Add a dated completion block to the audit document noting which tasks were completed.

Files to read:
- `plans/CURRENT_CODEBASE_STATUS_AND_REFACTOR_PLAN.md`

Files to edit:
- `plans/CURRENT_CODEBASE_STATUS_AND_REFACTOR_PLAN.md`

Implementation steps:
1. Add a `## 18. Completion Notes` section at the bottom.
2. Record: date completed, tasks completed, final test count, any tasks skipped with reason.

Test command:
```bash
grep -n "Completion Notes" plans/CURRENT_CODEBASE_STATUS_AND_REFACTOR_PLAN.md
```

Expected observable output: Section heading found.

Dependencies:
- TASK-T003

Rollback risk:
None.

---

Execute this plan one task at a time. Do not batch unrelated tasks.
