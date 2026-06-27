# 01 — Product Goal and Scope

## Product Goal

Build a practical financial data ingestion system that starts from user-provided task URLs and fills PostgreSQL with structured Indian mutual fund data.

The user does not want to manually maintain a full list of AMC/provider links. The agent must discover useful links from known entry points such as AMFI pages. If AMFI links to AMC/provider websites, those linked websites are part of the source graph and should be explored when relevant.

## User Mental Model

The user gives a URL and expects the system to handle the rest:

```text
task URL
→ discover relevant source pages and files
→ extract raw data
→ parse structured records
→ validate records
→ write PostgreSQL tables
```

The user should not need to decide whether a website needs static scraping, Playwright, network interception, form submission, PDF parsing, Excel parsing, or VLM assistance.

## Source Framing

Avoid rigid primary/secondary source terminology in the implementation. Instead, store provenance.

A source can be:

- AMFI page,
- AMC/provider website,
- registrar website,
- direct download URL,
- API endpoint,
- form-generated download,
- document file.

The database should record where each source was discovered from and where the final data came from.

## Data Domains

The system must focus first on Indian mutual fund data:

- AMC/provider list,
- schemes,
- NAV history,
- portfolio disclosures,
- holdings,
- factsheets,
- TER documents,
- SID/KIM documents,
- statutory disclosures,
- AUM/AAUM-related data where available.

The architecture should remain extensible to stocks, debt instruments, ETFs, indices, company filings, corporate actions, and other financial datasets later.

## Success Criteria

Minimum successful run:

1. Accept at least one AMFI task URL.
2. Discover at least some relevant dataset candidates.
3. Extract at least one actual dataset or raw file.
4. Parse at least one dataset type into structured records.
5. Insert records into PostgreSQL.
6. Store source provenance and run logs.
7. Log unsupported/failing items into quarantine or retry tables.

Better successful run:

1. Discover AMC/provider list from AMFI.
2. Discover NAV-related data and load NAV history.
3. Discover provider disclosure pages.
4. Download and parse at least one provider portfolio disclosure file.
5. Load portfolio holdings into canonical tables.
