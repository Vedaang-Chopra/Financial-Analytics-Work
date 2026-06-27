# Project Brief — Indian Mutual Fund Ingestion and Analytics

## What This Is

A provider-first data ingestion platform for Indian mutual fund public disclosures.

It discovers, downloads, parses, validates, and loads investor disclosure documents from Indian AMC (Asset Management Company) websites into PostgreSQL. It is not a chatbot, not a one-off scraper, and not investment advice.

---

## Why It Exists

Indian mutual funds are required by SEBI to publish investor disclosures: portfolio holdings, NAV data, factsheets, SID/KIM documents, TER data, fund manager information. These are publicly available but scattered across 50+ individual AMC websites in inconsistent formats.

The goal is to make this data machine-readable so researchers can answer questions like:
- Which stocks are held by the most funds?
- Which stocks are being accumulated or reduced across AMCs?
- What overlap exists between funds?
- How concentrated are funds at the holding level?

No investment advice. No buy/sell recommendations. Financial transparency and research only.

---

## Data Source Philosophy

**AMC/provider websites are the primary source.**

Each AMC website publishes actual investor disclosure documents: portfolio Excel files, NAV text files, factsheets, SID/KIM documents, TER disclosures.

**AMFI and SEBI are secondary reference indexes.**

AMFI provides a member list and a daily NAV text file. SEBI provides a registered fund list. These are useful for discovery and corroboration, not as the primary holdings source.

---

## Deterministic Strategy Order

Every extraction attempt follows this order. Never skip ahead.

```
1. static_html    — direct HTTP + HTML link extraction
2. network_api    — embedded API hints, JSON endpoints
3. playwright     — deterministic JavaScript rendering + network capture
4. vlm_required   — VLM-assisted fallback (explicit fallback, not default)
5. manual_review  — human inspection required
```

A provider's `detected_strategy` is persisted. Future runs try the known strategy first.

---

## Staging/Validation/Canonical Loading Principle

No raw parsed row goes directly into a canonical table.

```
raw file download
  → parser → staging_rows table
    → validate_and_filter_records()
      → valid: canonical upsert (amcs, schemes, nav_history, portfolio_holdings, etc.)
      → invalid: quarantine_rows table with reason code
        → retry_queue for recovery
```

Every canonical row carries `raw_artifact_id` and `source_url` provenance.

---

## Phase Plan

| Phase | Scope | Status (2026-06-23) |
|---|---|---|
| Phase 1A | Source registry bootstrap | Complete |
| Phase 1B | Provider website profiling | Complete |
| Task-URL Agent | End-to-end ingestion pipeline | Substantially complete |
| Phase 2 | Document discovery from Phase 1 profiles | Not started |
| Phase 3 | Document classification | Not started |
| Phase 4 | Additional parsers (factsheet, SID, KIM, TER) | Stubbed only |
| Phase 5+ | Validation coverage, analytics, agentic query | Not started |

---

## Governance Rules

All agents must read `AGENTS.md` before writing any code. It is non-negotiable.
