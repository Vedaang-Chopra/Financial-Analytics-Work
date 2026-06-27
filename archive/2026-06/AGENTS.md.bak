# AGENTS.md

Mandatory rules for all AI coding agents working in this codebase.
**Read this file before making any change. All rules are non-negotiable.**

---

## 0. Role and Scope

- You are an **execution agent**. Architecture and design decisions come from the spec or the human.
- Do not invent structure, modules, or patterns not specified in the task or spec.
- **When requirements are ambiguous or the existing codebase is unclear — ask, do not assume.**
- One task = one focused change. Do not silently fix, refactor, or reorganize unrelated code.
- Each implementation step must be separately verifiable before moving to the next. Do not bundle unrelated changes into one step.
- If you notice something broken outside your scope, flag it. Do not fix it silently.

---

## 1. Read These First

Before writing any code, read:

| Document | What it tells you |
|---|---|
| `docs/ai_context/CODEBASE_MAP.md` | Module ownership, public entry points, what exists, what not to duplicate |
| `docs/design/mutual_fund_ingestion/` | System architecture, phase plans, provider profile schema, artifact layout |
| `README.md` | Current CLI commands, setup, and artifact locations |
| `CONVENTIONS.md` | Code style standards — type hints, imports, class vs function |
| `AGENTS.md` | This file |
| `README.md` of every module you will touch | Module-local scope, entry points, restrictions |

If these files have not been read, stop and read them. Do not proceed to implementation.

---

## 2. Pre-Implementation Checklist

**Complete all steps before writing any code.**

- [ ] Read `docs/ai_context/CODEBASE_MAP.md` — identify all related files and functions.
- [ ] Confirm the spec exists under `docs/design/mutual_fund_ingestion/`. If not, follow `SKILL: write-spec` first.
- [ ] Confirm which module owns the behavior you are implementing.
- [ ] Confirm whether similar functionality already exists — do not duplicate.
- [ ] List every file your change will affect before touching any of them.
- [ ] Produce a layer plan (see §3) before writing any code.
- [ ] Confirm this is the correct phase. Do not implement later-phase behavior.

---

## 3. Layered Architecture — Non-Negotiable

Every module follows this layer model. State which layer each part of your change belongs to before writing code.

```text
Layer 1 — Notebooks           Inspection, debugging, visualization only. No production logic.
Layer 2 — Public Interface    cli.py / registry.py / interfaces.py — thin, typed, documented.
Layer 3 — Orchestration       Workflow composition. Calls core; does not implement algorithms.
Layer 4 — Core                Implementation logic, algorithms, provider-specific logic.
Layer 5 — Schemas / Utilities Data contracts, config objects, stateless helpers.
```

**Before writing code, produce a layer plan:**

```markdown
### Layer 1: Notebook
- Path:
- What it inspects:
- Which runner / interface it calls:

### Layer 2: Public Interface
- Public file and functions:
- Input / output types:

### Layer 3: Orchestration
- File and stage order:

### Layer 4: Core Logic
- Files and responsibilities:

### Layer 5: Schemas / Utilities
- Schemas:
- Shared utilities (project-level utils/):
- Local utilities (stays in module):
```

**Enforcement rules:**

- No production logic in notebooks.
- No core implementation logic inside `cli.py` or `registry.py`.
- No `run_full_pipeline()` function that contains all logic.
- No notebooks importing deep internal files unless explicitly debugging.
- No low-level utilities importing high-level feature modules.

---

## 4. Data Flow and Storage

Understand the ingestion pipeline storage topology before changing anything:

```text
configs/amc_sources.yaml          <- curated source registry (primary input)
  -> Phase 1A
    data/raw/mutual_funds/source_registry/
      source_registry_candidates.jsonl
      source_registry.latest.json
    data/reports/mutual_funds/source_registry_report.html
  -> Phase 1B
    data/raw/mutual_funds/provider_profiles/
      provider_profiles.jsonl
      provider_profiles.latest.json
    data/reports/mutual_funds/
      provider_profile_report.html
      provider_profile_summary.csv
    data/debug/mutual_funds/provider_profiles/<safe_amc_name>/

  -> Phase 2+ (planned)
    data/raw/mutual_funds/links/
    data/raw/mutual_funds/files/

  -> Parsing -> staging -> validation -> canonical PostgreSQL -> quarantine
```

**Raw files are never modified.** All transformed output goes to `processed/` or a staging layer.

---

## 5. Provider-First and Strategy Order

### Provider-First Principle

- AMC/provider websites are the **primary source** of disclosure documents.
- AMFI and SEBI are **secondary reference indexes** for discovery and corroboration only.
- Phase 1A uses AMFI/SEBI to discover candidate provider URLs; they are not the primary holdings source.
- Every future phase must load existing provider profiles and try the known strategy first before re-profiling.

### Deterministic Strategy Order

Every extraction or profiling attempt must follow this order. Do not skip ahead.

```text
1. static_html     — direct HTTP + HTML link extraction
2. network_api     — embedded API hints, JSON endpoints
3. playwright      — deterministic JavaScript rendering + network capture
4. vlm_required    — local VLM/LLM-assisted fallback (explicit, not default)
5. manual_review   — human inspection required
```

A provider profile's `detected_strategy` field records which step succeeded. Future runs load this and try the known strategy first.

---

## 6. Phase-Based Implementation

Implement one phase at a time. Do not jump ahead into later phases.

| Phase | Scope | Status |
|---|---|---|
| Phase 1A | Source registry bootstrap | Implemented |
| Phase 1B | Provider profiling | Implemented |
| Phase 1.5 | Strategy resolution | Not yet implemented |
| Phase 2 | Document discovery and download | Not yet implemented |
| Phase 3 | Document classification | Not yet implemented |
| Phase 4 | Parsing and staging | Not yet implemented |
| Phase 5+ | Validation, quarantine, canonical PostgreSQL | Not yet implemented |

**Before implementing any phase, read its spec in `docs/design/mutual_fund_ingestion/`.**

---

## 7. File and Module Creation Rules

Before creating any file, answer all four explicitly:

1. Does similar functionality already exist? (Check `docs/ai_context/CODEBASE_MAP.md` first.)
2. Can an existing module be extended instead?
3. Is this logic specific to one module or shared across modules?
4. If shared — does it belong in `utils/`?

If creating a new module directory, add a `README.md` using `SKILL: write-module-readme`.
If adding a new module to the codebase, update `docs/ai_context/CODEBASE_MAP.md` using `SKILL: update-codebase-map`.

---

## 8. Import Rules

- Import only from `__init__.py`, `cli.py`, `registry.py`, or `interfaces.py` — not from internal files.
- Import order: **standard library → third-party → internal**, with a blank line between groups.
- No wildcard imports (`from module import *`).
- No circular imports.
- No unused imports left in any file.

---

## 9. Naming Rules

| Element | Convention | Example |
|---|---|---|
| Function / variable | `snake_case` | `profile_source()` |
| Class | `PascalCase` | `ProviderProfile` |
| Constant | `UPPER_SNAKE_CASE` | `DEFAULT_REGISTRY` |
| Module / file | `snake_case`, responsibility-named | `source_discovery.py` |
| Directory | `snake_case`, purpose-named | `provider_profiles/` |

**Forbidden names:** `helper.py`, `utils2.py`, `misc.py`, `everything.py`, `main2.py`, or any file with version suffixes (`_v1`, `_v2`, `_new`, `_final`).

---

## 10. Forbidden Patterns

- **No giant pipeline functions.** One function = one responsibility. Follow `SKILL: design-runner`.
- **No hardcoded values.** Model names, paths, thresholds, credentials → `configs/` or `api.env`.
- **No duplicated schemas.** One canonical location. Do not redefine what already exists.
- **No dead code in active files.** Deprecated code goes to `unused_codebase/` following `SKILL: deprecate-code`.
- **No commented-out code as backup.** Use version control.
- **No silent exceptions.** Every caught error must be logged with actionable context.
- **No shared utilities buried in a single feature module.** Move to `utils/`.
- **No outputs written to source directories.** All run outputs go to `data/raw/`, `data/reports/`, or `data/debug/`.

---

## 11. Required Outputs Per Phase

Every implemented phase must produce all of the following:

1. **Machine-readable artifacts** — JSON/JSONL written to `data/raw/`
2. **Human-readable reports** — HTML or CSV written to `data/reports/`
3. **Quantifiable metrics** — counts, status distributions, failure reasons
4. **Failure/debug artifacts** — saved HTML, screenshots, network logs, error JSON
5. **A Jupyter review notebook** — under `notebooks/mutual_fund_ingestion/`
6. **Lightweight tests** — under `tests/`

---

## 12. Notebook Policy

Every phase implementation, design-spec change, or meaningful pipeline change must create or update the corresponding notebook under `notebooks/mutual_fund_ingestion/`.

The notebook must:

- explain the implemented code path and link to the relevant design spec
- import and call production code from `mutual_fund_ingestion/`
- run a small sample, fixture, or dry-run
- show inputs and outputs as DataFrames where useful
- compute summary metrics
- show debug/report paths and screenshots when useful
- state known gaps and readiness guidance for the next phase

Do not duplicate production logic inside notebooks. Do not run full live crawls by default.

---

## 13. Existing Codebase Audit

Before adding new code, inspect the existing codebase to determine what can be reused.

| Location | What you find |
|---|---|
| `mutual_fund_ingestion/` | Current Phase 1 implementation — do not duplicate |
| `amfi_disclosure/` | Standalone AMFI crawler prototype — isolated, not coupled to Phase 1+ |
| `Code Base/` | Legacy experiments — inspect, do not import into current implementation |
| `Dataset/` | Historical sample XLSX/CSV — fixtures for parser tests only, not Phase 1 |
| `tests/fixtures/` | Phase 1 unit test fixtures |

Reuse policy:

- Reuse only code that is simple, readable, compatible, and easy to test.
- If existing code is useful but messy, wrap it rather than rewriting.
- Mark obsolete code as deprecated rather than deleting.
- Do not import `amfi_disclosure/` into Phase 1+ without explicit justification.

---

## 14. Code Standards

Full details in `CONVENTIONS.md`. Non-negotiables:

- All public functions and classes must have **type hints** and a **docstring**.
- A function does one thing. If you are writing "and" in the function name, split it.
- Use **classes** for shared state or shared config. Use **functions** for stateless, single-purpose operations.
- Every new package must be added to `requirements.txt` or `pyproject.toml` immediately.
- Secrets go in `api.env`. Never in code. `api.env` is in `.gitignore`.

---

## 15. Documentation Rules

All documentation updates happen **in the same change set** as the implementation.

| What changed | What to update |
|---|---|
| New module or directory | `docs/ai_context/CODEBASE_MAP.md` + module `README.md` |
| Public API change | Module `README.md` + relevant spec in `docs/design/mutual_fund_ingestion/` |
| Schema or config change | Relevant spec + `CODEBASE_MAP.md` |
| Pipeline behavior change | `docs/design/mutual_fund_ingestion/` spec |
| Code moved from `mutual_fund_ingestion/` | Note source, destination, and any callers updated |

Follow `SKILL: update-docs` for the step-by-step process.
If implementation diverges from the spec, update the spec to match reality.

---

## 16. Safety and Compliance

Only ingest **public investor disclosure documents**.

Use polite crawling: timeouts, retry with backoff, user-agent header, sequential requests, no CAPTCHA bypass, no auth bypass, no login walls, no aggressive crawling.

**Never use:** buy/sell language, investment advice, or personalized recommendations.

---

## 17. Self-Check Before Finalizing

- [ ] No logic duplicated from an existing module.
- [ ] No misplaced code — ownership confirmed against `docs/ai_context/CODEBASE_MAP.md`.
- [ ] All public functions have type hints and a one-line docstring minimum.
- [ ] No hardcoded values (paths, model names, credentials, thresholds).
- [ ] No wildcard, circular, or unused imports.
- [ ] No dead or commented-out code in active files.
- [ ] No silent exception handling.
- [ ] No giant orchestration function containing all logic.
- [ ] No outputs written to source directories.
- [ ] Correct phase — no later-phase behavior implemented early.
- [ ] Strategy order followed (static → network → playwright → vlm → manual).
- [ ] Provider-first principle respected (AMFI/SEBI are reference, not primary).
- [ ] Layer plan was produced and followed.
- [ ] Documentation updated per §15.
- [ ] `requirements.txt` updated if new packages added.
- [ ] Backward compatibility preserved unless explicitly instructed otherwise.

---

## 18. Required Change Report

Output this after every task. Write `None` if a section has nothing to report.

```
## Change Report

### Files Modified
- `path/to/file.py` — what changed and why

### Files Created
- `path/to/new_file.py` — purpose and which layer it belongs to

### Files Deleted / Archived
- `path/to/old_file.py` -> `unused_codebase/old_file.py` — reason

### Documentation Updated
- Which docs updated and what changed (CODEBASE_MAP, spec, README)

### Validation Run
- Command / notebook / test, and result

### Validation NOT Run
- What was not tested and why

### Known Limitations / Follow-up Work
- Gaps, edge cases not handled, tasks for the next session
```

---

## Skills Reference

Use the skills in `SKILLS.md` for all recurring tasks. Do not invent your own procedure when a skill exists.

| Situation | Skill to follow |
|---|---|
| Before any implementation | `SKILL: discover-codebase` |
| Starting a new feature | `SKILL: implement-feature` |
| No spec exists yet | `SKILL: write-spec` |
| Creating a new module | `SKILL: create-module` |
| Designing a runner or workflow | `SKILL: design-runner` |
| Writing a companion notebook | `SKILL: write-notebook` |
| Writing a module README | `SKILL: write-module-readme` |
| After any structural change | `SKILL: update-codebase-map` |
| After any implementation | `SKILL: update-docs` |
| Cleaning up an existing module | `SKILL: refactor-module` |
| Retiring deprecated code | `SKILL: deprecate-code` |
| Writing human-readable docs | `SKILL: write-human-doc` |
