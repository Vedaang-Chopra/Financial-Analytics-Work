# Current Status and Next Steps

## What Has Been Designed

The project now has:

1. Provider-first ingestion architecture
2. AMFI as secondary/reference source only
3. Strategy hierarchy: static → network/API → Playwright → VLM → manual
4. Persistent provider profiles
5. Phase-based implementation
6. Existing codebase audit before implementation
7. Phase 1 provider profiling
8. Phase 1 review notebook requirement
9. Phase 1.5 strategy resolution
10. Requirement for notebooks after each phase
11. Future PostgreSQL-backed analytics

## Phase 1 Status

The user indicated Phase 1 is completed or near completion.

A review notebook was requested:

`notebooks/mutual_fund_ingestion/01_phase_1_provider_profiling_review.ipynb`

It should load source registry, run profiling on 3–5 providers, display provider profiles, summarize strategies, inspect candidate links, inspect debug artifact paths/screenshots, and decide readiness for Phase 2.

## Manual Review Issue

The user observed many manual-review providers in Phase 1.

Interpretation: `manual_review` means deterministic profiling did not confidently decide the right extraction strategy. It should not mean the user personally inspects every site.

Recommended next step: implement Phase 1.5 before Phase 2 if many providers remain unresolved.

## Phase 1.5 Outputs

Expected outputs:

```text
data/raw/mutual_funds/provider_profiles/provider_strategy_resolutions.jsonl
data/raw/mutual_funds/provider_profiles/provider_profiles.resolved.latest.json
data/reports/mutual_funds/provider_strategy_resolution_report.html
notebooks/mutual_fund_ingestion/01_5_strategy_resolution_review.ipynb
```

## When to Move to Phase 2

Proceed to Phase 2 only when most providers have concrete strategies: static_html, network_api, or playwright.

Suggested rule: if 60–70% of providers have concrete strategies, begin Phase 2.

If many remain manual_review_final or vlm_required, improve strategy resolution or add VLM/browser recovery first.

## Next Recommended Codex Task

Ask Codex to read the docs, inspect existing Phase 1 implementation, create/update the Phase 1 review notebook if not done, implement Phase 1.5 strategy resolution, and create the Phase 1.5 notebook.

Do not implement Phase 2 until Phase 1.5 readiness is acceptable.
