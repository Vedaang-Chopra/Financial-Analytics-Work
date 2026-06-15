# Conversation Decisions Captured

## 1. mfapi.in Is Not Enough

mfapi.in mainly provides scheme search, scheme metadata, NAV history, latest NAV, and scheme lists. It does not provide stock-level portfolio holdings, monthly portfolio disclosure data, fund overlap, fund manager consensus, or month-over-month buying/selling trends.

Therefore, mfapi.in is useful only as a NAV enrichment layer, not the core ingestion source.

## 2. AMFI Website Is Not the Main Dependency

The AMFI portfolio disclosure hub may be dynamic and dicey. It can be used as an index/reference, but the stronger architecture is to rely on direct AMC/provider websites.

## 3. Provider Websites Are the Primary Source

The user provided a curated list of AMC/provider disclosure/download URLs. These should be treated as seed URLs for a provider-first ingestion system.

## 4. Start Deterministic, Add Agentic Recovery Later

The system should not begin as a fully autonomous Chromium/VLM agent.

Preferred hierarchy:

```text
static scraping
→ network/API extraction
→ deterministic Playwright
→ local VLM/LLM recovery
→ manual review
```

The VLM is useful but should be a fallback, not the default.

## 5. Persistent Provider Profiles Are Critical

The system should not rediscover how each AMC website works on every run.

Phase 1 must produce persistent provider profiles containing AMC name, seed URL, detected strategy, JS requirement, known selectors, known link patterns, debug artifacts, last successful evidence, and failure reason.

Future runs should first try the known strategy and re-profile only when that strategy fails.

## 6. Existing Codebase Must Be Audited First

The repository may already contain Codex-generated crawler code, parsing tools, Excel sheets in dataset folders, PostgreSQL utilities, CLI patterns, and tests.

Codex should audit before implementing new code.

## 7. Every Phase Needs a Notebook

At the end of every implemented phase, a simple Jupyter notebook should be created. The notebook should explain the implemented phase, run a small sample, show important outputs, display metrics and reports, and help decide whether the next phase is ready.

## 8. Manual Review Should Become Phase 1.5

If Phase 1 produces many `manual_review`, `unknown`, or `vlm_required` providers, the next step is Phase 1.5: Strategy Resolution.

This step uses saved artifacts, rules, and optional local VLM assistance to classify unresolved providers into concrete strategies.

## 9. Financial Framing

The system should be framed as public disclosure analytics and financial transparency. It must not imply buy/sell recommendations or investment advice.
