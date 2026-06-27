# 06 — Data Sources and Dataset Types

## Source Discovery Model

The user provides task URLs. The agent discovers the source graph.

Example:

```text
AMFI task URL
→ AMFI AMC list page
→ AMC provider website
→ disclosure page
→ monthly portfolio disclosure XLSX/PDF
→ parsed holdings
→ PostgreSQL
```

AMFI may directly provide NAV history or may point to provider websites for disclosures. The system should handle both.

## Source Authority Types

Use provenance rather than rigid primary/secondary labels.

```text
amfi
amc_provider
registrar
regulator
exchange
index_provider
other
unknown
```

## Dataset Types

Supported dataset types:

```text
amc_provider_list
scheme_master
scheme_metadata
nav_history
latest_nav
portfolio_disclosure
portfolio_holdings
factsheet
ter
sid
kim
statutory_disclosure
aum_aaum
fund_manager_info
benchmark_info
sector_allocation
unknown
```

## Dataset Detection Hints

### AMC/provider list

Keywords:

```text
AMC
Mutual Fund
Fund House
Members
AMFI Members
```

Expected output:

- AMC name,
- website URL,
- AMFI/provider code if available,
- source URL.

### Scheme master / scheme metadata

Keywords:

```text
scheme
scheme code
scheme name
category
open ended
close ended
growth
direct
regular
```

Expected output:

- scheme code,
- scheme name,
- AMC,
- category,
- plan/option if available.

### NAV history

Keywords:

```text
NAV
Net Asset Value
historical NAV
NAV download
scheme code
NAV date
```

Expected output:

- scheme code,
- NAV date,
- NAV value,
- sale price/repurchase price if available,
- source URL.

### Portfolio disclosure

Keywords:

```text
portfolio
portfolio disclosure
monthly portfolio
holdings
security
ISIN
% to NAV
market value
quantity
sector
rating
maturity
```

Expected output:

- AMC,
- scheme,
- reporting date,
- security name,
- ISIN,
- quantity,
- market value,
- percentage to NAV,
- sector,
- asset class,
- coupon/rating/maturity if debt instrument.

### Factsheets

Keywords:

```text
factsheet
fact sheet
monthly factsheet
fund factsheet
```

Expected output initially:

- document metadata,
- AMC,
- scheme hints,
- reporting month,
- source URL,
- file metadata.

Detailed factsheet parsing can be best-effort initially.

## Priority

For urgent usefulness, prioritize:

1. NAV history from AMFI.
2. AMC/provider list from AMFI.
3. Portfolio disclosure files from linked AMC/provider pages.
4. Excel/CSV portfolio parsing.
5. PDF portfolio parsing where table extraction is feasible.
