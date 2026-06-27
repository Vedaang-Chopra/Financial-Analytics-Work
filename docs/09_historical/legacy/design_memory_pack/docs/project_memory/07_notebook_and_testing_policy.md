# Notebook and Testing Policy

## Purpose

Every implemented phase should end with a simple Jupyter notebook.

The notebook is for understanding, debugging, and deciding whether the next phase is ready.

It is not a replacement for production code and should not duplicate crawler/parser logic.

## Notebook Location

Use:

```text
notebooks/mutual_fund_ingestion/
```

Naming pattern:

```text
01_phase_1_provider_profiling_review.ipynb
01_5_strategy_resolution_review.ipynb
02_phase_2_raw_download_review.ipynb
03_phase_3_classification_review.ipynb
04_phase_4_excel_parser_review.ipynb
```

## Notebook Requirements

Each notebook should briefly explain the phase, link to relevant design docs, import the implemented code, load inputs, run a small sample, display outputs as pandas DataFrames, compute summary metrics, show debug/report artifact paths, display screenshots if useful, and end with readiness guidance for the next phase.

## Notebook Simplicity

Do not overload notebooks. Avoid large abstractions, complete reimplementation of crawler logic, full production runs by default, unnecessary visualizations, and future-phase work.

## Phase 1 Notebook

`notebooks/mutual_fund_ingestion/01_phase_1_provider_profiling_review.ipynb`

Purpose: understand Phase 1 code, load source registry, profile 3–5 AMCs, inspect provider profiles, summarize strategies, inspect candidate links, inspect debug artifacts, and decide whether Phase 1 is good enough for Phase 1.5 or Phase 2.

## Phase 1.5 Notebook

`notebooks/mutual_fund_ingestion/01_5_strategy_resolution_review.ipynb`

Purpose: load unresolved profiles, show why they were unresolved, run/load strategy resolution, compare before/after strategy counts, inspect screenshots/artifacts, and decide whether Phase 2 is safe.

## Testing Policy

Each phase should include lightweight tests where practical.

Examples: source registry loading, schema validation, link extraction from saved fixtures, safe filename generation, report generation, and JSONL output validity.

Live tests should be limited by default.

## Phase Readiness Criteria

Proceed only when outputs are inspectable, metrics make sense, failures are categorized, debug artifacts exist, notebook results are understandable, and the current phase produces enough reliable input for the next phase.
