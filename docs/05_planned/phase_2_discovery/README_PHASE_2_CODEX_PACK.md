# Phase 2 Codex Pack — Raw Document Discovery and Download

This pack continues the existing Phase 1 / Phase 1.5 mutual fund ingestion work. It is intended to be passed to Codex as implementation context.

## Intended repository placement

Copy these files into the repository root, preserving paths:

```text
docs/design/mutual_fund_ingestion/phases/02_phase_2_raw_document_discovery_and_download.md
docs/design/mutual_fund_ingestion/phases/02_phase_2_artifact_contract.md
docs/design/mutual_fund_ingestion/phases/02_phase_2_sample_values_and_amfi_reference.md
docs/design/mutual_fund_ingestion/phases/02_phase_2_testing_and_acceptance.md
prompts/codex_phase_2_raw_document_download_prompt.md
```

## What Phase 2 should build

Phase 2 should use resolved provider profiles from Phase 1.5 to discover and download raw mutual fund investor disclosure documents from AMC/provider websites.

It should produce inspectable raw samples and metadata, not canonical parsed holdings tables yet.

Phase 2 must show actual raw values in the review notebook, such as:

- discovered document URLs,
- AMC/provider names,
- document type hints,
- reporting month/date hints,
- file names,
- MIME types,
- file sizes,
- checksums,
- first rows from downloaded Excel/CSV files when possible,
- sheet names for Excel files,
- first-page text snippets for PDFs when cheap and available.

These previews are for inspection only. They are not a replacement for Phase 3 classification or Phase 4 parsing.

## What Phase 2 should not build

Do not implement:

- full document classification,
- full Excel/PDF parsing,
- staging tables,
- PostgreSQL canonical loading,
- validation/quarantine,
- analytics,
- investment recommendations.

## Dependency on Phase 1.5

Before Phase 2, Codex must check whether Phase 1.5 exists and whether `provider_profiles.resolved.latest.json` is available.

If Phase 1.5 is missing or incomplete, Codex should either:

1. stop with a clear error explaining what is missing, or
2. implement only the minimal missing Phase 1.5 contract if explicitly instructed.

Phase 2 itself should not silently re-profile all websites from scratch.
