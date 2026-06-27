# Batch I — Raw Retention Tests
# Milestone served: 2 (pipeline fully tested)
# Status: backlog
# Gate: Retention tests pass; L001 already done

## Purpose

Verify files are retained to raw_dir when --keep-raw-files is set.

## Completion Gate

```bash
./financial_env/bin/python -m pytest tests/ -k "retention or raw_dir or keep_raw" -v -q
```

## Tasks

### TASK-L002: Test raw file retention creates file in raw_dir
**Goal:** Verify `ArtifactCollector.download()` moves file to `raw_dir/<run_id>/` when `--keep-raw-files` set.
**Files to read:** `tests/test_agent_db.py`, `mutual_fund_ingestion/agent/extract.py`
**Files to modify:** `tests/test_agent_db.py`
**Exact work:**
1. Run pipeline with `keep_raw_files=True` and a `raw_dir` set to a temp dir
2. After run, assert file exists in `raw_dir/<run_id>/`
3. Assert `raw_artifacts.retained = True` in DB
**Acceptance criteria:** 1 test passing
**Test command:** `./financial_env/bin/python -m pytest tests/test_agent_db.py -k "raw_dir" -v`
**Do not do:** Test live downloads; use fixture HTML pages only
**Status:** pending

---

### TASK-L003: Test file size limit enforced during streaming
**Goal:** Verify that streaming download stops and raises or skips when file exceeds `max_file_size_mb`.
**Files to read:** `mutual_fund_ingestion/agent/extract.py`, `mutual_fund_ingestion/agent/config.py`
**Files to modify:** `tests/test_agent.py`
**Exact work:**
1. Mock an HTTP response that streams more bytes than `max_file_size_mb` allows
2. Assert download is aborted (exception or early return)
3. Assert no partial file is left in raw_dir
**Acceptance criteria:** 1 test passing — oversized file rejected cleanly
**Test command:** `./financial_env/bin/python -m pytest tests/test_agent.py -k "file_size_limit" -v`
**Do not do:** Real network downloads
**Status:** pending
