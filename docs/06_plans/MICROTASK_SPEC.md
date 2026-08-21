# MICROTASK_SPEC - STORY-NB-004

## Task ID

STORY-NB-004

## Title

Rewrite the source registry story notebook

## Milestone served

Sub-Goal 1 - make the system inspectable through notebooks

## Skill to apply

- `design-feature-notebook`
- `add-observability`
- `update-docs`
- `verify-checkpoint`

## Files to read before starting

1. `AGENTS.md`
2. `docs/README.md`
3. `docs/06_plans/active/STORY_NOTEBOOK_SERIES_PLAN.md`
4. `docs/06_plans/active/STORY_NOTEBOOK_SERIES_TASKS.md`
5. `docs/02_architecture/codebase_map.md`
6. `mutual_fund_ingestion/profiling/registry.py`
7. `mutual_fund_ingestion/profiling/source_registry.py`
8. `configs/amc_sources.yaml`
9. `notebooks/mutual_fund_ingestion/01a_phase_1_source_registry_review.ipynb`

## Files to edit

- `notebooks/mutual_fund_ingestion/01a_phase_1_source_registry_review.ipynb`
- `docs/06_plans/EXECUTION_RESULT.md`
- `docs/01_status/session_state.md`

## Exact work

1. Rewrite `01a_phase_1_source_registry_review.ipynb` as the source registry story notebook.
2. Use public or documented entry points where available: `load_registry`, `SourceRegistryEntry`, `merge_source_candidates`, and source registry artifacts.
3. Include setup, stage blocks, at least three assertions, artifact inspection, failure/debug section, and final "what this proves / what it does not prove".
4. Keep live network optional and off by default.
5. Do not change ingestion behavior.
6. Do not edit other notebooks.

## Validation commands

```bash
./financial_env/bin/python - <<'PY'
import json
from pathlib import Path
path = Path("notebooks/mutual_fund_ingestion/01a_phase_1_source_registry_review.ipynb")
nb = json.loads(path.read_text())
src = "\\n".join("".join(cell.get("source", [])) for cell in nb["cells"])
assert src.count("assert ") >= 3
assert src.count("[STAGE]") >= 5
assert "what this proves" in src.lower()
print("source registry notebook structural checks passed")
PY
./financial_env/bin/python -m pytest tests/ -q --tb=no
```

## Expected output

- Structural check passes.
- Full pytest remains at the current baseline.
- Notebook explains registry inputs, provenance, AMFI/SEBI reference entries, artifacts, and Phase 1B readiness.

## Stop condition

Stop after `01a_phase_1_source_registry_review.ipynb` and status docs are updated and validated.

## Next task after completion

STORY-NB-005 - rewrite `notebooks/mutual_fund_ingestion/01b_phase_1_provider_profiling_review.ipynb`.
