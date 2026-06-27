# Codex Working Instructions

## General Rule

Codex should treat this project as a phased ingestion system, not a one-off scraping task.

## Read Before Work

Before modifying ingestion code, Codex should read:

```text
AGENTS.md
CHATGPT_PROJECT_MEMORY.md
docs/project_memory/*.md
docs/design/mutual_fund_ingestion/*.md
docs/design/mutual_fund_ingestion/phases/<current_phase>.md
```

## Existing Codebase Audit

Before adding new systems, Codex must inspect the current repository.

It should identify existing AMFI code, AMC crawler code, parsing tools, Excel sheets in dataset folders, download utilities, PostgreSQL utilities, CLI patterns, tests, notebooks, and dependency files.

Reuse existing code only if compatible.

## One Phase at a Time

Codex should implement only the requested phase.

It must not jump ahead into downloads during profiling, parsing during discovery, PostgreSQL loading during parsing, or analytics before validation.

## Required Outputs Per Phase

Every phase should produce:

1. machine-readable artifacts
2. human-readable reports
3. quantifiable metrics
4. debug/failure artifacts
5. a simple Jupyter notebook

## Notebook Policy

At the end of each phase, create a notebook under `notebooks/mutual_fund_ingestion/`.

The notebook should explain the phase, import/use the implemented code, run a small sample, display key outputs as DataFrames, show summary metrics, show debug artifacts if available, and help decide whether next phase is ready.

The notebook should not duplicate production logic.

## Strategy Policy

For websites, use this order:

```text
static_html
network_api
playwright
vlm_browser_recovery
manual_review
```

VLM usage is optional and should be pluggable.

## Data Quality Policy

Never treat parsed rows as trusted immediately.

Use:

```text
raw files
→ staging
→ validation
→ canonical tables
→ quarantine for failures
```

## Financial Safety

The system must be framed as public disclosure analytics.

Avoid buy/sell recommendations or investment advice language.

## Useful Codex Prompt Pattern

```text
Read AGENTS.md, CHATGPT_PROJECT_MEMORY.md, docs/project_memory/*.md, and the current phase spec.
First inspect the existing codebase and summarize relevant reusable pieces.
Then implement only the requested phase.
Generate machine artifacts, reports, metrics, debug outputs, and a simple review notebook.
Do not implement future phases.
```
