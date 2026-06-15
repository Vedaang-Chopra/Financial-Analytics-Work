# 03 — Agent Runtime and Orchestration

## Runtime Model

Use a queue-driven runtime.

Main queues:

```text
url_queue
artifact_queue
parse_queue
validation_queue
retry_queue
```

The agent begins by inserting task URLs into `url_queue`. Each processed page can produce new URLs, raw artifacts, dataset candidates, or parser tasks.

## URL Processing Flow

For each URL:

1. Normalize and deduplicate.
2. Check crawl depth and page budget.
3. Fetch with static HTTP where possible.
4. Determine if browser rendering is required.
5. If required, open with Playwright.
6. Capture links, forms, downloads, tables, network calls, and screenshots.
7. Score relevance.
8. Store source page and discovered links.
9. Add relevant links to queue.
10. Add files/API/table artifacts to artifact queue.

## Strategy Selection

The system should use cheap methods first:

```text
static HTTP
→ HTML parsing
→ rendered DOM via Playwright
→ network/API capture
→ form/download interaction
→ VLM-guided action
→ retry/quarantine
```

VLM is not the primary extractor. It is a guide for ambiguous UI/page interpretation.

## Relevance Scoring

Score pages and links using:

- URL keywords,
- anchor text,
- page title,
- visible text,
- file extension,
- domain authority type,
- proximity to task URL,
- known financial terms,
- VLM judgment if enabled.

High-value terms:

```text
NAV
Net Asset Value
Scheme
Scheme Information
Portfolio
Portfolio Disclosure
Monthly Portfolio
Factsheet
Fact Sheet
Statutory Disclosure
SID
KIM
TER
Total Expense Ratio
AUM
AAUM
Disclosure
Download
Investor Services
Mutual Fund
AMC
```

Low-value terms:

```text
careers
contact
privacy
terms
sitemap
media
press release
investor education
login
feedback
branches
```

Low-value links can be stored but should not consume crawl budget unless explicitly configured.

## Domain Policy

Default behavior:

1. Always allow the task URL domain.
2. Allow off-domain links only if they appear relevant to mutual fund/provider data.
3. Track all newly discovered domains.
4. Store whether a domain is AMFI, AMC/provider, registrar, regulator, exchange, or unknown.

Optional CLI flags:

```text
--allow-off-domain true
--allowed-domain amfiindia.com
--blocked-domain example.com
```

## Reproducibility

Every action should be logged with:

- run ID,
- URL,
- strategy used,
- timestamp,
- inputs,
- output artifact IDs,
- error reason if any.

For VLM decisions, store:

- screenshot path,
- prompt payload,
- raw VLM response,
- parsed JSON decision,
- final action taken,
- whether the action succeeded.
