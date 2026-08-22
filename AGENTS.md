# Financial Analytics Work — Project AGENTS.md
# Global rules: ~/agent-governance/AGENTS.md — read that first.
# This file contains ONLY project-specific overrides.
# Do not repeat any rule from the global file.

---

## Global Rules

All global rules and skills apply unchanged.
Global rules: `~/agent-governance/AGENTS.md`
Skills root:  `~/agent-governance/skills/core/`

---

## §1 Read These First (Project Overrides)

**Product vision (read before any implementation work): `docs/VISION.md`**
**Current build plan: `docs/plans/EXECUTION_PLAN_v2_fix_rulers.md`** (v1 `EXECUTION_PLAN_consensus_platform.md` Tracks A–D are COMPLETE — do not redo)

These paths override the global `docs/ai_context/` references in `~/agent-governance/AGENTS.md`.

| File | What it tells you |
|---|---|
| `docs/VISION.md` | The product we are building (consensus/dissent MF intelligence platform) — all work serves this |
| `docs/02_architecture/codebase_map.md` | Module ownership, entry points, what not to duplicate |
| `docs/01_status/AGENT_EXECUTION_LOG.md` | What was tried before, what failed, what not to repeat |
| `docs/01_status/session_state.md` | Current implementation state if resuming |
| `docs/01_status/MASTER_STATE.md` | Verified test baseline (122 passed / 3 skipped) and feature completion map |
| `docs/02_architecture/system_overview.md` | End-to-end pipeline structure (stub — not yet created) |

---

## Project Overview

**Project:** Financial Analytics Work — Mutual Fund Disclosure Ingestion Pipeline
**Language:** Python
**Environment:** (fill in conda env or venv path)
**Entry point:** `mutual_fund_ingestion/` — see README.md for CLI commands
**Test command:** `pytest tests/ -v`
**Secrets file:** `api.env` (this project uses api.env, not .env)

---

## Model Registry

| Alias | Models (priority order) | Rate tier | Use case |
|---|---|---|---|
| `planning` | (fill in) | paid | Spec, plan, decompose only |
| `complex-reasoning` | (fill in) | paid | Complex logic, debugging |
| `fast-code` | (fill in) | free (rate limited) | Boilerplate, simple functions |
| `local` | (fill in) | local, unlimited | Simple edits, formatting |

---

## Project Constraints

### Secrets file override
This project uses `api.env` for API keys and secrets (not `.env`).
`api.env` is in `.gitignore`. Never commit it.

### Deprecated code path
Dead code goes to `archive/YYYY-MM/<original_path>` — matches global convention.

### Provider-First Principle
- AMC/provider websites are the **primary source** of disclosure documents.
- AMFI and SEBI are **secondary reference indexes** for discovery and corroboration only.
- Phase 1A uses AMFI/SEBI to discover candidate provider URLs; they are not the primary holdings source.
- Every future phase must load existing provider profiles and try the known strategy first before re-profiling.

### Deterministic Strategy Order
Every extraction or profiling attempt must follow this order. Do not skip ahead.

```
1. static_html     — direct HTTP + HTML link extraction
2. network_api     — embedded API hints, JSON endpoints
3. playwright      — deterministic JavaScript rendering + network capture
4. vlm_required    — local VLM/LLM-assisted fallback (explicit, not default)
5. manual_review   — human inspection required
```

A provider profile's `detected_strategy` field records which step succeeded.
Future runs load this and try the known strategy first.

### Data Flow and Storage

```
configs/amc_sources.yaml          <- curated source registry (primary input)
  -> Phase 1A -> data/raw/mutual_funds/source_registry/
  -> Phase 1B -> data/raw/mutual_funds/provider_profiles/
                 data/reports/mutual_funds/
                 data/debug/mutual_funds/provider_profiles/<safe_amc_name>/
  -> Phase 2+  -> data/raw/mutual_funds/links/ | files/
  -> Parsing -> staging -> validation -> canonical PostgreSQL -> quarantine
```

Raw files are never modified. All transformed output goes to `processed/` or a staging layer.

### Phase-Based Implementation

Implement one phase at a time. Do not jump ahead.

| Phase | Scope | Status |
|---|---|---|
| Phase 1A | Source registry bootstrap | Implemented |
| Phase 1B | Provider profiling | Implemented |
| Phase 1.5 | Strategy resolution | Not yet implemented |
| Phase 2 | Document discovery and download | Not yet implemented |
| Phase 3 | Document classification | Not yet implemented |
| Phase 4 | Parsing and staging | Not yet implemented |
| Phase 5+ | Validation, quarantine, canonical PostgreSQL | Not yet implemented |

Before implementing any phase, read its spec in `docs/05_planned/` (planned phases) or `docs/03_implemented/` (completed phases).

### Required Outputs Per Phase

Every implemented phase must produce:
1. Machine-readable artifacts — JSON/JSONL written to `data/raw/`
2. Human-readable reports — HTML or CSV written to `data/reports/`
3. Quantifiable metrics — counts, status distributions, failure reasons
4. Failure/debug artifacts — saved HTML, screenshots, network logs, error JSON
5. A Jupyter review notebook — under `notebooks/mutual_fund_ingestion/`
6. Lightweight tests — under `tests/`

### Notebook Policy

Every phase implementation must create or update the corresponding notebook under
`notebooks/mutual_fund_ingestion/`. The notebook must call production code only —
no duplicated logic inside cells.

### Existing Codebase Isolation

| Location | Policy |
|---|---|
| `mutual_fund_ingestion/` | Current Phase 1 — do not duplicate |
| `amfi_disclosure/` | Standalone prototype — do not import into Phase 1+ |
| `Code Base/` | Legacy experiments — inspect only, do not import |
| `Dataset/` | Historical fixtures for parser tests only |

### Safety and Compliance

- Only ingest **public investor disclosure documents**.
- Polite crawling: timeouts, retry with backoff, user-agent header, sequential requests.
- No CAPTCHA bypass, no auth bypass, no login walls, no aggressive crawling.
- Never use buy/sell language, investment advice, or personalized recommendations.
