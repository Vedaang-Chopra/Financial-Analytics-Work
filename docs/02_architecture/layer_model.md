# 5-Layer Architecture Model

_Enforced on ALL new code. Every file must be classifiable into exactly one layer._

---

## Layer Definitions

```
Layer 1 — Notebooks
  Inspection, understanding, integration surface.
  No production logic. Read-only consumers of Layer 2 public APIs.
  Files: notebooks/mutual_fund_ingestion/*.ipynb

Layer 2 — Public Interface
  interfaces.py / api.py / runners.py / cli.py — thin, typed, documented.
  Input validation only. Delegates immediately to Layer 3.
  Files: mutual_fund_ingestion/cli.py, mutual_fund_ingestion/__init__.py

Layer 3 — Orchestration
  Workflow composition. Calls Layer 4. Does not implement algorithms.
  Files: agent/runner.py, profiling/artifacts.py, profiling/reports.py, profiling/source_registry.py

Layer 4 — Core Logic
  Implementation logic, algorithms, feature-specific behavior.
  Files: agent/discovery.py, agent/browser.py, agent/extract.py, agent/validate.py,
         agent/vlm.py, agent/parser/*.py, profiling/profiler.py, profiling/extract.py,
         profiling/browser.py, profiling/source_discovery.py

Layer 5 — Schemas / Utils
  Data contracts, config, stateless helpers.
  Files: agent/db.py, agent/models.py, agent/config.py, profiling/models.py,
         profiling/registry.py, profiling/http.py, utils/http.py,
         utils/url_utils.py, utils/text_utils.py
```

---

## Violations — Flag, Do Not Fix Silently

| Violation | Action |
|---|---|
| Production logic in a notebook cell | Flag. Move to Layer 4. |
| Importing from deep internal files (not public interface) | Flag. Reroute to Layer 2. |
| `runner.py` growing beyond 300 lines | Flag as refactor candidate. |
| Duplicate schema definitions | Flag. Merge to one canonical location. |
| Low-level utils importing high-level modules | Flag. Invert the dependency. |

---

## Current Violations

| File | Issue | Priority | Task |
|---|---|---|---|
| `agent/runner.py` | 821 lines — mixes orchestration + core logic | High | REFACTOR_runner (not this session) |

---

## Before Writing Any New Code

Produce a layer plan:

```markdown
### Layer Plan
#### Layer 2: Public Interface
- File: [path]
- Public functions: [list]
#### Layer 3: Orchestration
- File: [path]
- Stage order: [list]
#### Layer 4: Core Logic
- File: [path]
- Responsibility: [description]
#### Layer 5: Schemas
- File: [path]
- Data types: [list]
```
