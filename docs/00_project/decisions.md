# Architecture Decisions

_Stable. Update only when a major design decision is made or reversed._

---

## D001 — Provider-first, not AMFI-first

**Decision**: Use individual AMC websites as primary data source. AMFI/SEBI are discovery indexes only.

**Rationale**: AMFI NAV data is end-of-day aggregated. Real portfolio holdings, factsheets, SID/KIM documents exist only on individual AMC sites in provider-specific formats.

**Impact**: Requires provider profiling (Phase 1B) to detect per-AMC access strategies before ingestion.

---

## D002 — Deterministic strategy ladder

**Decision**: Every provider access attempt follows the same fixed order: static_html → network_api → playwright → vlm_required → manual_review. Never skip ahead.

**Rationale**: Cheap strategies first. Expensive strategies (Playwright, VLM) only when necessary. Provider strategy is persisted so future runs can fast-path.

---

## D003 — Staging → validate → canonical (never direct upsert)

**Decision**: Raw parsed rows always land in `staging_rows` before any canonical table write.

**Rationale**: Validation must be decoupled from parsing. Quarantine path must be available for every row. Provenance (`raw_artifact_id`, `source_url`) must be preserved end-to-end.

---

## D004 — profiling/ is frozen

**Decision**: `mutual_fund_ingestion/profiling/` is frozen after Phase 1B completion. No new logic added here.

**Rationale**: Phase 1 is complete and tested. Adding to it risks regressions against the 38 Phase 1 tests. Phase 2+ logic goes in `mutual_fund_ingestion/agent/`.

---

## D005 — amfi_disclosure/ is legacy prototype, not production

**Decision**: `mutual_fund_ingestion/amfi_disclosure/` is isolated. Never imported by the agent pipeline.

**Rationale**: It was a standalone exploration crawler. Its logic is superseded by the Task-URL agent. Its 11 tests are kept for reference but it is not on the critical path.

---

## D006 — SQLite for local dev, PostgreSQL for production

**Decision**: The agent pipeline uses SQLAlchemy with no dialect-specific SQL. SQLite for tests and local inspection; PostgreSQL for production runs.

**Rationale**: Keeps tests fast and portable. The 17-table schema works in both dialects.

---

## D007 — 5-layer architecture enforced on all new code

**Decision**: Every module follows the Layer 1–5 model defined in `docs/07_agent_rules/skills/design_layered_module.md`.

**Impact**: `runner.py` is currently a layer violation (821 lines mixing orchestration + core logic). Flagged for refactor; not addressed in this session.
