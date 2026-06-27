# 12 — Reuse Existing Phase 1A / Phase 1B Work

## Context

The repository may already contain earlier work for Phase 1A and Phase 1B provider profiling. That work may include source registries, provider profiles, static crawlers, Playwright code, reports, notebooks, and strategy detection.

The new target is not phase-first delivery. The new target is an end-to-end task-URL driven ingestion agent.

## Reuse Rule

Reuse existing code if it helps the end-to-end agent. Do not preserve phase boundaries merely because they exist.

## Likely Reusable Pieces

Inspect and reuse if compatible:

- URL normalization utilities,
- safe filename utilities,
- source registry loader,
- provider profile schema,
- static link extractor,
- Playwright browser setup,
- screenshot/debug artifact logic,
- network log capture,
- candidate link classifier,
- report generation helpers,
- JSONL artifact writers,
- tests for link extraction/schema validation,
- any database connection utilities.

## What Must Change

Old assumption:

```text
The user maintains a curated provider registry, then the system profiles those providers phase by phase.
```

New assumption:

```text
The user provides task URLs. The agent builds and updates the source/provider registry automatically by crawling relevant AMFI and linked provider pages.
```

## How to Adapt Provider Profiles

Provider profiles can become `source_entities` or `provider_candidates`.

Map old fields:

```text
amc_name → source_entities.name / amcs.name
seed_url → discovered source URL
status → source_entities.status / dataset_candidates.status
detected_strategy → preferred_extraction_strategy
requires_javascript → requires_browser
candidate_links → discovered_links
file_types_found → dataset/file type hints
debug_artifacts → source_pages artifact paths
```

## How to Adapt Strategy Resolution

Old strategy resolution can become an internal strategy selector:

```text
static_html
network_api
playwright
vlm_required
failed_blocked
manual_review
```

But do not make the user run a separate strategy-resolution phase. The agent should resolve and act during the same pipeline.

## Notebook Policy

Existing notebooks can remain for debugging. Do not make notebook creation a blocking deliverable.

The main deliverable is the runnable ingestion agent and PostgreSQL data.
