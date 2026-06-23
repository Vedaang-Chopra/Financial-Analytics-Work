# Plan: Demo Notebook for Mutual Fund Ingestion System

**Spec:** N/A (Layer 1 Notebook — documentation/inspection only)
**Status:** Draft

## Summary

Create a single comprehensive Jupyter notebook (`notebooks/mutual_fund_ingestion/00_demo_system_overview.ipynb`) that demonstrates the entire working pipeline: Phase 1A (Source Registry), Phase 1B (Provider Profiling), and the Task-URL Agent. The notebook loads existing artifacts, displays them interactively, and includes bounded live execution cells for each phase. This is a Layer 1 artifact — no production logic, only inspection and integration surface.

## Layer Assignment

| Component | Layer | File Path | Reason |
|---|---|---|---|
| Demo notebook | Notebook (Layer 1) | `notebooks/mutual_fund_ingestion/00_demo_system_overview.ipynb` | Human-facing inspection, calls public CLI and loads artifacts |

## Files to Create

| File | Layer | Purpose |
|---|---|---|
| `notebooks/mutual_fund_ingestion/00_demo_system_overview.ipynb` | Notebook (1) | Single comprehensive demo showing all phases with live cells |

## Files to Modify

None — this is a new Layer 1 artifact only.

## Dependency Order

1. Notebook file created with proper structure
2. Notebook executed to verify all sections work

## Integration Points

The notebook imports/calls:

- `mutual_fund_ingestion` CLI via subprocess (Phase 1A, 1B commands)
- `amfi_disclosure` CLI via subprocess
- Existing artifacts in `data/raw/mutual_funds/` and `data/reports/`
- Public schemas: `mutual_fund_ingestion.profiling.models`

## Risks and Open Questions

- Network calls to AMFI/SEBI/provider sites may timeout (handled with `--dry-run` and small `--limit` bounds)
- Playwright/Chromium may not be installed in all environments (notebook handles gracefully)
- The notebook must not duplicate production logic — only call CLI and display artifacts

## Validation Criteria

- [ ] Notebook exists at `notebooks/mutual_fund_ingestion/00_demo_system_overview.ipynb`
- [ ] Notebook executes top-to-bottom without unhandled exceptions (network timeouts caught and displayed)
- [ ] Phase 1A section loads and displays 55 sources from `source_registry.latest.json`
- [ ] Phase 1B section loads and displays provider profiles with strategy distribution
- [ ] Live demo cells have sensible bounds (`--limit`, `--dry-run`, `--max-pages`) to avoid long waits
- [ ] HTML reports linked/embedded for visual inspection
