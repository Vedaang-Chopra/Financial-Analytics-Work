# Phase 1.5 Strategy Resolution Memory

## Why Phase 1.5 Exists

Phase 1 provider profiling may mark many providers as manual_review, unknown, vlm_required, partial_success, or failed.

This does not necessarily mean the user must manually inspect each site. It means the deterministic profiler did not confidently determine a stable extraction strategy.

Phase 1.5 exists to resolve those ambiguous cases before Phase 2 downloads.

## Goal

Convert unresolved provider profiles into one of:

- static_html
- network_api
- playwright
- vlm_required
- failed_blocked
- manual_review_final

## Inputs

Use Phase 1 artifacts:

```text
data/raw/mutual_funds/provider_profiles/provider_profiles.jsonl
data/raw/mutual_funds/provider_profiles/provider_profiles.latest.json
data/debug/mutual_funds/provider_profiles/<safe_amc_name>/
```

Artifacts to inspect include static HTML, rendered HTML, screenshots, network logs, accessibility snapshots, profiler error JSON, and candidate links.

## Rule-Based Examples

If rendered HTML has downloadable links but static HTML does not, use `playwright`.

If network logs contain JSON/API responses with file URLs, use `network_api`.

If screenshots show Portfolio Disclosure or Download controls but links are not extractable, use `vlm_required`.

If the site is unreachable/blocked, use `failed_blocked`.

If evidence is insufficient, use `manual_review_final`.

## Optional VLM Interface

A local VLM can inspect screenshots and return structured advice. Do not hardcode a specific VLM provider.

Expected structured output:

```json
{
  "recommended_strategy": "playwright",
  "confidence": 0.78,
  "reason": "The screenshot shows a Portfolio Disclosure dropdown and a Search button.",
  "suggested_actions": [
    "click Portfolio Disclosure",
    "select latest month",
    "extract download links"
  ]
}
```

## Outputs

```text
data/raw/mutual_funds/provider_profiles/provider_strategy_resolutions.jsonl
data/raw/mutual_funds/provider_profiles/provider_profiles.resolved.latest.json
data/reports/mutual_funds/provider_strategy_resolution_report.html
```

## CLI

Suggested command:

```bash
python -m mutual_fund_ingestion resolve-strategies
```

Options:

```text
--only-unresolved
--amc
--limit
--use-vlm false
--dry-run
--log-level INFO
```

## Notebook

Create:

```text
notebooks/mutual_fund_ingestion/01_5_strategy_resolution_review.ipynb
```

It should show unresolved Phase 1 profiles, before/after strategy counts, resolution reasons, screenshots for 1–2 cases if available, and Phase 2 readiness summary.
