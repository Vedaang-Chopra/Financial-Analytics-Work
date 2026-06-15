# Data Sources and Provider Strategy

## Primary Data Source

AMC/provider websites are the primary source.

The user provided a curated list of Indian AMC disclosure/download pages. These should be stored in a source registry such as `configs/amc_sources.yaml`.

## AMFI Role

AMFI may be used as reference index, source discovery aid, or fallback validation. It should not be the main dependency.

## mfapi.in Role

mfapi.in provides NAV history and scheme metadata. It is useful later for NAV enrichment, latest NAV, scheme search, and scheme metadata.

Do not rely on it for monthly holdings, portfolio disclosures, stock-level allocation, sector allocation from disclosures, or manager consensus.

## Source Registry Fields

Suggested fields:

```yaml
sources:
  - amc_name: "HDFC Mutual Fund"
    seed_url: "https://www.hdfcfund.com/statutory-disclosure/portfolio-disclosure"
    enabled: true
    source_type: "provider_disclosure_page"
    expected_document_types:
      - portfolio_disclosure
      - factsheet
    notes: ""
```

## Provider Profile Fields

Each provider profile should store schema_version, run_id, created_at, amc_name, seed_url, status, detected_strategy, requires_javascript, static_links_found, download_links_found, candidate_document_links_found, file_types_found, document_type_hints, known_link_patterns, known_selectors, source_pages_examined, candidate_links, debug_artifacts, failure_reason, and notes.

## Strategy Definitions

`static_html`: document links are directly available in HTML.  
`network_api`: internal API or JSON endpoints expose documents.  
`playwright`: JavaScript rendering or deterministic UI interaction is needed.  
`vlm_required`: visual/UI reasoning may be needed.  
`manual_review`: automation lacks enough evidence.  
`failed_blocked`: site is unreachable, blocked, or persistently fails.

## VLM Role

Local VLMs may be used for reading screenshots, identifying visible download buttons/tabs, suggesting click paths, interpreting UI state, and deciding whether Playwright can handle the site.

The VLM should output structured JSON, not freeform browsing.
