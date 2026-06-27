# Phase 1 — Source Registry Bootstrap and Provider Website Profiling

## Phase Goal

Build persistent knowledge of Indian mutual fund sources and provider websites
without downloading or parsing investor documents.

Phase 1 has two internal parts:

```text
Phase 1A — Source Registry Bootstrap
Phase 1B — Provider Website Profiling
```

AMFI and SEBI are reference/source-discovery layers. Direct AMC/provider
websites remain the primary sources for future disclosure ingestion.

## Phase 1A — Source Registry Bootstrap

Phase 1A loads `configs/amc_sources.yaml`, discovers candidate AMC/provider
records from AMFI and optional SEBI evidence, merges those candidates, and
writes a provenance-aware registry.

AMFI discovery uses static HTTP first and may use deterministic Playwright
rendering when the static members page does not expose usable links. SEBI is
corroborative and non-authoritative; binary, stale, unsupported, or unreachable
SEBI evidence produces a warning rather than failing Phase 1.

### Registry roles

```text
primary_provider — direct AMC/provider website; eligible for Phase 1B
reference_index  — AMFI, SEBI, or another discovery/validation index
```

Reference indexes use `priority: secondary` and are never profiled as provider
websites.

### Merge rules

Candidates are deduplicated by normalized AMC name and compatible provider
domain. Reference indexes are never merged into provider records.

Field precedence:

1. Locked manual value
2. Existing curated provider seed URL
3. High-confidence AMFI/provider evidence
4. Existing unlocked value
5. SEBI corroborative evidence

Manual locks are declared per field:

```yaml
manual_overrides:
  - seed_url
  - source_type
```

List fields such as `discovered_from` and `expected_document_types` are unioned.
Provider entries without usable seed URLs remain in the registry with
`unresolved_reasons` and are excluded from Phase 1B.

### Phase 1A outputs

```text
configs/amc_sources.yaml
data/raw/mutual_funds/source_registry/source_registry_candidates.jsonl
data/raw/mutual_funds/source_registry/source_registry.latest.json
data/reports/mutual_funds/source_registry_report.html
```

YAML and latest snapshots are written atomically. Dry runs do not write files.

## Phase 1B — Provider Website Profiling

Phase 1B profiles enabled `primary_provider` entries with valid seed URLs.
Each provider receives a persistent profile describing the best known
deterministic extraction strategy and supporting evidence.

Strategy order and classifications:

```text
static_html
network_api
playwright
vlm_required
manual_review
failed_blocked
```

- `static_html`: useful links are present in raw HTML.
- `network_api`: useful URLs or likely endpoints are exposed through network/API evidence.
- `playwright`: deterministic rendering or UI interaction is required.
- `vlm_required`: relevant visual controls exist but deterministic extraction is insufficient.
- `manual_review`: the site is reachable but evidence is insufficient.
- `failed_blocked`: the site is blocked, unreachable, or repeatedly fails.

Phase 1B may inspect links and make minimal classification requests. It must not
download all disclosure documents.

### Phase 1B outputs

```text
data/raw/mutual_funds/provider_profiles/provider_profiles.jsonl
data/raw/mutual_funds/provider_profiles/provider_profiles.latest.json
data/reports/mutual_funds/provider_profile_summary.csv
data/reports/mutual_funds/provider_profile_report.html
data/debug/mutual_funds/provider_profiles/<safe_amc_name>/
```

Profiles preserve registry context through `source_role`, `source_type`,
`source_provenance`, `strategy_confidence`, and rendered/static link counts.
Existing `provider_profile_v1` records without the new fields remain loadable.

## CLI

```bash
python -m mutual_fund_ingestion bootstrap-sources
python -m mutual_fund_ingestion profile-providers
python -m mutual_fund_ingestion phase-1
```

`profile-sites` remains a compatibility alias for `profile-providers`.
`--registry` remains an alias for `--config`.

Useful options:

```text
--config configs/amc_sources.yaml
--limit N
--amc "HDFC Mutual Fund"
--dry-run
--force
--no-browser
--use-playwright true|false
--no-reference-network
--log-level INFO
```

`phase-1` runs Phase 1A then profiles the resulting in-memory provider entries.
Reference-source failures do not block Phase 1B when usable provider entries
remain.

## Metrics and Review

The source registry report includes total/reference/provider/manual sources,
merge counts, missing seed URLs, and manual-completion counts.

The provider report includes status and strategy distributions, static/rendered
link counts, candidate counts, file types, provenance, failures, and debug
folders.

The Phase 1 review notebook must remain a thin, non-mutating-by-default runner
that shows Phase 1A candidates/metrics/unresolved entries and a bounded Phase 1B
sample before recommending readiness for Phase 1.5.

## Acceptance Criteria

Phase 1 is complete when:

1. Existing, curated, AMFI, and optional SEBI candidates can be merged.
2. Manual field locks and provenance are preserved.
3. Reference indexes are stored but excluded from provider profiling.
4. Unresolved provider records remain inspectable.
5. Enabled primary provider sites receive compatible provider profiles.
6. Machine-readable artifacts, HTML reports, metrics, and debug evidence exist.
7. Offline tests cover registry validation, merging, profile compatibility,
   classifications, JSONL, reports, and CLI dry runs.
8. No document downloading, parsing, PostgreSQL loading, validation, analytics,
   dashboards, investment advice, or autonomous VLM control is implemented.

## Phase 1.5 Readiness

Phase 1.5 may begin when the merged registry is valid, unresolved entries are
inspectable, and a bounded provider sample demonstrates usable profiling
artifacts. Every provider does not need to succeed before Phase 1.5 begins.
