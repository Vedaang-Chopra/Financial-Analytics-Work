# 09 — Validation, Quarantine, and Provenance

## Principle

Parsed rows are not trusted immediately.

Flow:

```text
raw artifact
→ parser result
→ staging rows
→ validation
→ canonical upsert
→ quarantine for failed rows
```

## NAV Validation

Checks:

- scheme code is present,
- NAV date is parseable,
- NAV value is numeric and positive,
- duplicate scheme_code + nav_date conflicts are handled,
- source URL exists,
- raw artifact/source reference exists.

Rows that fail required checks go to quarantine.

## Portfolio Validation

Checks:

- reporting date present or inferable,
- scheme/fund name present or inferable,
- security name present,
- percentage_to_nav numeric where provided,
- market value numeric where provided,
- ISIN sanity if present,
- duplicate rows handled,
- asset class/sector preserved where available,
- sum of percentage_to_nav plausible when enough rows exist.

Do not reject entire documents if only a subset of rows fail. Load valid rows and quarantine invalid rows.

## Document Validation

Checks:

- source URL present,
- file type detected,
- checksum computed where file exists,
- dataset type classified,
- source page linked,
- parser result stored.

## Provenance Requirements

Every canonical row must be traceable to:

- ingestion run,
- task URL,
- source page,
- discovered link/dataset candidate,
- raw artifact or API response,
- parser name/version,
- validation result.

Where direct foreign keys are not practical, store provenance in JSONB metadata.

## Quarantine Reasons

Use structured reasons:

```text
unsupported_file_type
unsupported_dataset_type
parse_error
missing_required_field
invalid_date
invalid_numeric_value
low_parser_confidence
blocked_or_unreachable
browser_timeout
vlm_unparseable_response
download_failed
file_too_large
pdf_scanned_or_image_based
unknown_schema
```

## Retry Queue

Use retry queue for failures that may succeed later or with another strategy:

- network timeout,
- browser timeout,
- temporary blocked page,
- download failed,
- parser unsupported but raw file retained/re-downloadable,
- VLM suggested alternate action.

Do not retry permanent failures indefinitely.

## Metrics

At end of run, store:

- pages visited,
- links discovered,
- dataset candidates found,
- files downloaded,
- artifacts parsed,
- staging rows created,
- canonical rows inserted/updated,
- quarantine rows,
- retry tasks,
- errors by category.
