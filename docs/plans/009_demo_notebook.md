# Plan: Demo Notebook for Mutual Fund Ingestion System

## Overview
Create a comprehensive Jupyter notebook (`notebooks/mutual_fund_ingestion/00_demo_system_overview.ipynb`) that demonstrates the entire working pipeline — Phase 1A (Source Registry), Phase 1B (Provider Profiling), and Task-URL Agent — with live execution capability.

## Layer Plan

### Layer 1: Notebook
- **Path:** `notebooks/mutual_fund_ingestion/00_demo_system_overview.ipynb`
- **What it inspects:** All Phase 1A/1B artifacts, live CLI commands, agent dry-runs
- **Which runner/interface it calls:** `mutual_fund_ingestion.cli` (via subprocess), loads JSON/JSONL artifacts directly

### Layer 2: Public Interface
- No new public interface needed — notebook consumes existing CLI and artifacts

### Layer 3: Orchestration
- Notebook cells orchestrate the demo flow: Setup → Phase 1A → Phase 1B → Agent → AMFI

### Layer 4: Core Logic
- No new core logic — uses existing mutual_fund_ingestion modules

### Layer 5: Schemas / Utilities
- Reuses existing schemas from `mutual_fund_ingestion/schemas/`

## Implementation Sections

| Section | Notebook Cell Group | Purpose |
|---|---|---|
| 0 | Setup & Imports | Bootstrap, logging, path helpers, display utilities |
| 1 | Phase 1A: Source Registry | Load/inspect `source_registry.latest.json`, show report, run `--dry-run` |
| 2 | Phase 1B: Provider Profiling | Load/inspect `provider_profiles.latest.json`, strategy distribution, live profiling demo |
| 3 | Task-URL Agent | `init-db`, `run-agent --dry-run`, schema inspection, bounded live run |
| 4 | AMFI Disclosure (Legacy) | `amfi_discovery` CLI demo with bounded fetch |
| 5 | Live Demo Runner | Convenience cells to run profiling on specific providers |

## Dependencies
- Existing artifacts in `data/raw/mutual_funds/source_registry/` and `data/raw/mutual_funds/provider_profiles/`
- Existing reports in `data/reports/mutual_funds/`
- Working CLI: `bootstrap-sources`, `profile-providers`, `run-agent`, `init-db`

## Verification
- Notebook executes top-to-bottom without unhandled exceptions
- Network timeouts are caught and reported gracefully
- All existing artifacts load and display correctly
- Live demo cells have sensible bounds (`--limit`, `--dry-run`)

## Checkpoint
**Human sign-off required:** Review notebook execution output before finalizing.