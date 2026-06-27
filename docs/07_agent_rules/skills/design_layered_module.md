---
name: design-layered-module
description: >
  Use this skill whenever creating, editing, or refactoring code where module
  structure or workflow design is involved. Triggers include: adding or changing
  runners.py / interfaces.py / api.py, adding a notebook that exercises
  production code, moving logic between notebooks and Python modules, reviewing
  whether generated code is at the correct abstraction level, and any task that
  touches a module's directory layout. This skill must run before implementation
  when the task affects module structure. It enforces a five-layer architecture:
  notebooks inspection, interfaces/api/runners public entry points, orchestration
  workflow composition, core implementation logic, and schemas/utils data
  contracts and reusable primitives. Use it proactively: if a task touches more
  than one file in a module, default to applying this skill first.
---

# SKILL: design-layered-module

## Trigger

Use this skill whenever:

* Creating a new module or feature.
* Editing an existing module with multiple files.
* Adding or changing a `runners.py`, `interfaces.py`, or `api.py`.
* Adding or updating a notebook that exercises production code.
* Refactoring a flat or hard-to-understand directory.
* Moving logic between notebooks, runners, core modules, schemas, or utilities.
* Reviewing whether newly generated code is placed at the correct abstraction level.

This skill must be used before implementation when the task affects module structure or workflow design.

---

## Purpose

Ensure code is generated and edited using a clear layered architecture.

The goal is to prevent:

* Production logic inside notebooks.
* Giant `runners.py` files.
* One large `run_full_pipeline()` function containing all logic.
* Random imports from deep internal files.
* Core logic mixed with orchestration.
* Shared utilities buried inside feature modules.
* Flat directories with many unrelated files.
* Duplicated parsing, schemas, configs, or helper functions.

---

## Required Layer Model

Design the code using these layers.

### Layer 1 — Notebook Inspection Layer

Location:

```text
notebooks/
```

Purpose:

* Human inspection.
* Debugging.
* Visualization.
* Intermediate output display.
* Step-by-step understanding.
* Demonstrating how the module behaves.

Rules:

* Notebooks call production code.
* Notebooks must not own reusable logic.
* Notebooks should import from `interfaces.py`, `api.py`, or `runners.py`.
* If notebook logic becomes reusable, move it into a Python module.
* Notebook sections should match the workflow stages.

---

### Layer 2 — Public Interface / Runner Layer

Location:

```text
module_name/interfaces.py
module_name/api.py
module_name/runners.py
```

Purpose:

* Public callable entry points.
* Stable functions external modules and notebooks may import.
* Thin workflow orchestration.
* Clear input/output contracts.

Rules:

* This layer exposes what the module wants other code to call.
* Do not expose random internal files directly.
* Keep functions typed and documented.
* `run_full_pipeline()` may exist, but it must only compose smaller stage functions.
* Do not place business logic or core algorithms directly in `runners.py`.

Good pattern:

```python
def load_inputs(...) -> Inputs:
    ...

def run_stage_a(inputs: Inputs) -> StageAOutput:
    ...

def run_stage_b(stage_a: StageAOutput) -> FinalOutput:
    ...

def run_full_pipeline(...) -> FinalOutput:
    inputs = load_inputs(...)
    stage_a = run_stage_a(inputs)
    return run_stage_b(stage_a)
```

---

### Layer 3 — Orchestration Layer

Location:

```text
module_name/orchestration/
```

Purpose:

* Compose multiple core operations.
* Manage workflow order.
* Coordinate state movement between stages.
* Keep pipeline logic readable.

Rules:

* Orchestration calls core logic.
* Orchestration should not implement low-level algorithms.
* Orchestration should not define schemas unless they are workflow-local and not shared.
* Orchestration should be independently testable when possible.

Use this layer when `runners.py` would otherwise become too large.

---

### Layer 4 — Core Implementation Layer

Location:

```text
module_name/core/
module_name/evaluation/
module_name/data_loading/
module_name/visualization/
module_name/parsing/
```

Purpose:

* Main feature logic.
* Algorithms.
* Evaluation logic.
* Data loading logic.
* Rendering/visualization logic.
* Parsing logic specific to the module.

Rules:

* Core modules contain the actual implementation.
* Keep files responsibility-specific.
* Do not mix unrelated logic in one file.
* Do not import from notebooks.
* Do not depend on high-level runners unless absolutely necessary.
* If logic is reused by more than one module, move it to project-level `utils/`.

---

### Layer 5 — Schemas, Config, and Low-Level Utilities

Location:

```text
module_name/schemas/
module_name/utils/
utils/
```

Purpose:

* Typed data contracts.
* Dataclasses / Pydantic models.
* Config structures.
* Stateless helper functions.
* Low-level reusable utilities.

Rules:

* Define each schema once.
* Do not redefine the same schema in multiple files.
* Keep utilities stateless when possible.
* Project-level `utils/` must not import from high-level feature modules.
* Avoid circular imports.
* If a utility is shared across modules, place it in project-level `utils/`.
* If a utility is local to one module, keep it inside `module_name/utils/`.

---

## Before Writing Code

Before implementing or editing code, produce a layer plan.

The layer plan must include:

```markdown
## Layer Plan

### Layer 1: Notebook
- Notebook path:
- What it will inspect:
- What production entry points it will call:

### Layer 2: Public Interface / Runner
- Public file:
- Public functions:
- Input/output contracts:

### Layer 3: Orchestration
- Orchestration files:
- Workflow stages:
- What each stage calls:

### Layer 4: Core Logic
- Core files:
- Responsibilities:
- Classes/functions to add or edit:

### Layer 5: Schemas / Utilities
- Schemas:
- Configs:
- Local utilities:
- Shared utilities:
```

Do not begin implementation until this layer plan is written.

---

## During Implementation

While writing or editing code:

1. Keep notebooks thin.
2. Keep runners thin.
3. Keep public interfaces stable.
4. Put workflow composition in runners or orchestration.
5. Put actual implementation in core modules.
6. Put schemas in schemas.
7. Put shared reusable utilities in project-level `utils/`.
8. Do not import upward from lower layers.
9. Do not create circular imports.
10. Do not duplicate schemas, parsing logic, config loading, or utility functions.
11. Do not create flat directories with many unrelated files.
12. Update `README.md` and `docs/ai_context/CODEBASE_MAP.md` if structure changes.

---

## During Edits to Existing Code

When editing an existing module, check whether the current code violates the layer model.

Ask:

* Is production logic inside a notebook?
* Is `runners.py` doing too much?
* Is `run_full_pipeline()` hiding all the logic?
* Are notebooks importing deep internal files?
* Are public APIs unclear?
* Is orchestration mixed with core implementation?
* Are schemas duplicated?
* Are shared utilities buried in a feature module?
* Are low-level utilities importing high-level modules?
* Is the directory flat when it should be grouped by responsibility?

If the answer is yes, do not perform a broad rewrite automatically. State the issue and either:

* fix only the part required by the current task, or
* propose a separate refactor using `SKILL: refactor-module`.

---

## Layer Ownership Rules

| Layer                | Owns                                               | Must Not Own                                            |
| -------------------- | -------------------------------------------------- | ------------------------------------------------------- |
| Notebook             | inspection, examples, visualization, debugging     | production logic, reusable functions                    |
| Interface/API/Runner | public entry points, thin orchestration            | algorithms, parsing internals, large workflow logic     |
| Orchestration        | workflow composition, stage ordering               | low-level algorithms, schemas duplicated from elsewhere |
| Core                 | implementation logic, algorithms, feature behavior | public API sprawl, notebook-specific display            |
| Schemas/Utils        | data contracts, helpers, reusable primitives       | high-level feature workflows                            |

---

## Validation Checklist

Before finalizing, verify:

* [ ] A layer plan was written before implementation.
* [ ] Notebooks call production code and do not own reusable logic.
* [ ] Public entry points live in `interfaces.py`, `api.py`, or `runners.py`.
* [ ] Runners are thin and composed of smaller stage functions.
* [ ] Core logic lives outside runners.
* [ ] Orchestration and implementation are separated when complexity requires it.
* [ ] Schemas are defined once.
* [ ] Shared utilities are in project-level `utils/`.
* [ ] Local-only utilities remain inside the module.
* [ ] No lower layer imports from a higher layer.
* [ ] No circular imports were introduced.
* [ ] Module `README.md` reflects the structure.
* [ ] `docs/ai_context/CODEBASE_MAP.md` reflects public entry points and ownership.
* [ ] Existing tests, notebooks, or smoke commands still work.

---

## Related Skills

Use with:

* `SKILL: discover-codebase`
* `SKILL: create-module`
* `SKILL: design-runner`
* `SKILL: write-notebook`
* `SKILL: update-codebase-map`
* `SKILL: refactor-module`
* `SKILL: update-docs`
