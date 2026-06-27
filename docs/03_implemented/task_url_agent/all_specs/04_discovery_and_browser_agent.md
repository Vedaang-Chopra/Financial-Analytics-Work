# 04 — Discovery and Browser Agent

## Purpose

The discovery/browser agent is responsible for navigating task URLs and relevant linked pages to locate datasets and raw files.

It must work on both simple static pages and complex JavaScript-driven pages.

## Static Discovery

For every page, attempt static extraction first:

- HTTP GET,
- status code,
- content type,
- page title,
- meta tags,
- anchor links,
- direct file links,
- table detection,
- script references,
- form actions.

If enough data is found statically, avoid launching Chromium for that page.

## Browser Discovery

Use Playwright/Chromium when:

- static HTML is thin,
- page requires JavaScript,
- links appear only after rendering,
- downloads require button clicks,
- forms/dropdowns are needed,
- network calls expose APIs,
- static fetch is blocked but browser loads.

Browser actions:

- navigate to URL,
- wait for DOM content loaded / network idle,
- capture screenshot,
- capture rendered HTML,
- extract text, links, buttons, inputs, selects, tables,
- listen to network requests/responses,
- detect downloadable responses,
- trigger safe clicks on relevant controls.

## Safe Interaction Rules

The agent may click:

- disclosure tabs,
- download buttons,
- NAV links,
- scheme data links,
- factsheet links,
- portfolio disclosure links,
- month/year dropdowns,
- search buttons for public data.

The agent must avoid:

- login forms,
- payment flows,
- personal data forms,
- feedback/contact submission,
- unsubscribe/subscribe actions,
- destructive actions,
- anything requiring credentials.

## Download Handling

When the browser triggers a file download:

1. Save temporarily under run-specific temp directory.
2. Compute checksum.
3. Detect MIME type and file extension.
4. Store raw artifact metadata.
5. Queue for classification and parsing.
6. Delete raw file after successful parse unless configured to keep raw files.

## Network/API Capture

Capture network requests and responses.

Look for:

- JSON endpoints,
- CSV/Excel/PDF downloads,
- POST requests that return datasets,
- query parameters for date, scheme, AMC, document type,
- API endpoints backing tables.

Store useful network evidence in `raw_artifacts` and `dataset_candidates`.

## Crawl Limits

Mandatory limits:

- `max_pages`,
- `max_depth`,
- `max_files`,
- `max_runtime_minutes`,
- `max_file_size_mb`,
- per-page timeout,
- per-download timeout.

No unbounded crawling.
