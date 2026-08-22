# AMC Parser-Ready — Session Kickoff Prompt (Phase 1: breadth to ≥2 months)

Work in `~/all_data/complete_technical_work/all_projects_implemented/Financial Analytics Work` (read AGENTS.md at repo root first; venv `./financial_env`; DB `postgresql://vlmrouter:vlmrouter@localhost:5432/mutual_funds` via Docker container `vlmrouter-postgres` — `docker start vlmrouter-postgres` if down).

Execute the plan at `.hermes/plans/2026-08-22_amc-parser-ready-plan.md` top-to-bottom. It is self-contained: verified census, waves, per-AMC sub-agent splits, acceptance gate, coordination rules.

Mission: get ALL 52 real AMCs in the registry to a working parser + ≥2 months of portfolio data in PostgreSQL. Census today: 19 READY / 13 PARTIAL (1 date, need archive walk) / 20 MISSING (SBI + Kotak are the hard Playwright cases).

Rules of engagement:
- Parallelize within waves using sub-agents (one agent per AMC during ingestion; wave splits are in the plan). Waves themselves are sequential.
- Acceptance gate per AMC (from the plan): ≥2 distinct reporting dates spanning ≥45 days, latest ≈today, ≥1 snapshot with ≥10 holdings summing 90–110% NAV, capability matrix updated, committed.
- Shared repo: re-read files before patching; never `git add -A`; stage explicit paths only. Another Hermes session may be active.
- Polite crawling only; never hand-edit canonical tables; do not delete files (`scripts/apply_retention.py` owns deletion).
- Deep-history backfill is Phase 2, explicitly out of scope now.
- Report per-AMC done/not-done with evidence as each completes; honest failures documented in configs/amc_capability_matrix.yaml, never silent skips.
