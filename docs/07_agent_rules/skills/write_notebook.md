---
name: design-feature-notebook
description: >
  Use when creating or updating Jupyter notebooks so they serve as structured
  feature understanding and integration testing surfaces — not thin wrappers
  around one interface call. Triggers: creating any new notebook, updating a
  notebook after feature changes, or reviewing notebooks that only call one
  function. Use with SKILL: write-notebook is removed — this is the single
  authoritative notebook skill.
---

# SKILL: design-feature-notebook

## Trigger

Use this skill when:
* Creating a new Jupyter notebook for a feature, module, or workflow.
* Updating an existing notebook after a feature change.
* Reviewing notebooks that only call one function from `interfaces.py` or `runners.py`.
* Building an inspection notebook for ML code, pipelines, data processing, evaluation,
  or agentic workflows.

Use together with:
* `SKILL: add-observability` — for stage print blocks in each section
* `SKILL: design-layered-module` — for understanding which functions to call

---

## What a Notebook Is (and Is Not)

A notebook is a **structured understanding surface and integration test**
for a feature. It shows what a module does, how it flows, and what breaks.

| Artifact | Purpose | Audience | Pass/Fail |
|---|---|---|---|
| `notebooks/<X>_inspection.ipynb` | Behavior demonstration, intermediate state | Human + agent | Human review |
| `tests/test_<X>.py` | Function-level contract verification | CI pipeline | Binary |
| `scripts/smoke_<X>.py` | Module runs end-to-end without crashing | Pre-deploy | Binary |

A notebook does NOT replace unit tests. A unit test does NOT replace a notebook.
They serve different purposes and must not be conflated.

A notebook that only does this is wrong:
```python
from module.interfaces import run_feature
result = run_feature(...)
result
```

A notebook should let a human answer:
* What does this feature take as input?
* What intermediate states does it produce?
* What does success look like?
* What does failure look like?
* How do I debug it if it breaks?

---

## Required Structure

### Section 1 — Purpose
```markdown
## 1. Purpose
What feature is this notebook inspecting?
What should a human understand after running it top-to-bottom?
```

### Section 2 — Setup
```python
## 2. Setup

import logging
from pathlib import Path

# Configure logging so production module logs are visible inline
logging.basicConfig(
    level=logging.DEBUG,
    format="%(name)s | %(levelname)s | %(message)s"
)

# Imports
from module.interfaces import run_feature, load_inputs
from module.schemas.config import PipelineConfig

# Config
config = PipelineConfig(input_path="path/to/test_input")

print("[SETUP] complete")
print(f"  → config: {config}")
```

No feature logic in this section. Only imports, config, logging, path setup.

### Section 3 — Test Inputs
```python
## 3. Test Inputs

print("\n[STAGE] test inputs")
# Load or construct small, representative inputs
# Show their summary — shape, fields, sample record

inputs = load_inputs(config)

print(f"  ✓ count  : {len(inputs)}")
print(f"  ✓ fields : {list(inputs[0].__dict__.keys())}")
print(f"  ✓ sample : {inputs[0]}")
```

### Section 4 — Public Entry Point Check
```python
## 4. Public Entry Point

print("\n[STAGE] run_feature (top-level)")
print(f"  → input count: {len(inputs)}")

result = run_feature(inputs, config)

print(f"  ✓ result type  : {type(result)}")
print(f"  ✓ result count : {len(result) if hasattr(result, '__len__') else 'N/A'}")
print(f"  ✓ sample       : {result[0] if result else 'empty'}")
```

Call the public entry point from `interfaces.py` or `runners.py`.
Show the top-level output. Do not import from `core/` directly here.

### Section 5 — Stage-by-Stage Inspection
For each major stage of the feature's pipeline:

```python
## 5a. Stage: load_inputs

from module.runners import load_inputs_stage  # or equivalent exposed stage fn

print("\n[STAGE] load_inputs")
print(f"  → path: {config.input_path}")

stage_result = load_inputs_stage(config)

print(f"  ✓ loaded  : {len(stage_result)} records")
print(f"  ✓ valid   : {sum(1 for r in stage_result if r.status == 'ok')}")
```

Expose stage functions through `interfaces.py` or `runners.py` if not already.
Do not import from internal `core/` files to make inspection work.

### Section 6 — Assertions
```python
## 6. Assertions

print("\n[STAGE] assertions")

assert result is not None, "result must not be None"
assert isinstance(result, list), f"expected list, got {type(result)}"
assert len(result) > 0, "result must not be empty"
assert all(hasattr(r, "id") for r in result), "all records must have 'id'"

print("  ✓ all assertions passed")
```

Assertions are required. They make the notebook an executable contract, not just a demo.

### Section 7 — Edge Cases / Failure Cases
```python
## 7. Edge Cases

print("\n[STAGE] edge case: empty input")
try:
    empty_result = run_feature([], config)
    print(f"  ✓ empty input handled: returned {empty_result}")
except Exception as e:
    print(f"  ✗ error type : {type(e).__name__}")
    print(f"  ✗ message    : {e}")
```

At least one edge or failure case is required. Show the error explicitly — do not hide it.

### Section 8 — Artifact / Output Inspection
```python
## 8. Artifacts

from pathlib import Path

output_path = Path("execution_results/feature_output.json")
print(f"\n[STAGE] artifact check")
print(f"  → expected path: {output_path}")
print(f"  ✓ exists: {output_path.exists()}")
if output_path.exists():
    print(f"  ✓ size  : {output_path.stat().st_size / 1024:.1f} KB")
```

If the feature writes outputs/files, inspect them here.

### Section 9 — Debugging Notes
```markdown
## 9. Debugging Notes

If this feature fails, check:
- `module/core/loader.py` — FileNotFoundError means input path is wrong
- `module/schemas/record.py` — validation failure means input record is malformed
- Logger output above — `load_inputs | failed` shows exact failure location

Relevant logs: look for lines starting with `module.core.`
Run with: `LOG_LEVEL=DEBUG python -m module.runners`
```

### Section 10 — Summary
```markdown
## 10. Summary

| Section | Result |
|---|---|
| Public entry point | ✓ returns list of 47 records |
| Stage inspection | ✓ all stages visible |
| Assertions | ✓ 5/5 passed |
| Edge case: empty input | ✓ returns [] gracefully |
| Artifact | ✓ output.json exists (12 KB) |

Not tested: concurrent execution, very large inputs (>10k records).
```

---

## Rules

### 1. Notebooks call production code — never reimplement it
Allowed in notebooks: setup, test input construction, calling production functions,
printing results, simple assertions, visualizations.

NOT allowed: core algorithms, parsing logic, schema definitions, retry logic,
model setup, reusable transformations. If a cell grows into a reusable function,
move it to a Python module immediately.

### 2. Every section must have stage print blocks
Follow `SKILL: add-observability` — every major section starts with a `[STAGE]`
header print and ends with a `✓` or `✗` summary. No section should be silent.

### 3. Assertions are required
Every notebook must include at least 3 assertions. They are not optional.

### 4. At least one failure case is required
Do not present only the happy path. Show what happens with empty, malformed,
or missing input. Show the error — do not catch and hide it.

### 5. Import only from public entry points
Never import from `core/`, `orchestration/`, or internal files in notebooks.
If stage-level inspection is needed, expose stable stage functions through
`interfaces.py` or `runners.py`.

### 6. Notebook runs top-to-bottom with no hidden state
All cells must run sequentially. No reliance on cells that were run manually
in a previous session.

### 7. Clear outputs before committing
Unless the notebook is explicitly a saved report, clear all outputs before commit.

---

## Before Creating the Notebook

Write this plan first and confirm it:

```markdown
## Notebook Plan

**Path:** notebooks/<feature>_inspection.ipynb
**Feature:** <description>
**Public entry points:** module.interfaces.<X>, module.runners.<Y>
**Sections:** [list all 10]
**Expected assertions:** [list 3+]
**Expected artifacts to inspect:** [list files/outputs]
**Not tested in this notebook:** [explicit exclusions]
```

---

## Validation Checklist

- [ ] Notebook has a clear purpose statement.
- [ ] Setup cell configures `logging.basicConfig` at DEBUG level.
- [ ] Each major section has a `[STAGE]` print block (entry + exit).
- [ ] Public entry point is called and output shown.
- [ ] At least one stage-by-stage inspection section.
- [ ] At least 3 assertions present.
- [ ] At least one edge/failure case shown with explicit error output.
- [ ] Artifacts inspected if the feature produces them.
- [ ] Debugging notes section present.
- [ ] Summary section present with a table.
- [ ] All cells run top-to-bottom without error.
- [ ] No production logic reimplemented in notebook cells.
- [ ] Imports are from public entry points only.

---

## Related Skills

* `SKILL: add-observability` — stage print block conventions used in every section
* `SKILL: write-tests` — the separate unit test artifact (not this notebook)
* `SKILL: design-layered-module` — understand which functions are safe to call from notebooks
* `SKILL: implement-feature` — this notebook is created in Step 6 of that skill
