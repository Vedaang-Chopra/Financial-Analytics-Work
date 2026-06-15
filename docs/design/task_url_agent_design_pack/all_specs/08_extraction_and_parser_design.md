# 08 — Extraction and Parser Design

## Parser Router

Create a parser router that selects parser by:

- dataset type,
- file type,
- MIME type,
- file extension,
- content sniffing,
- source hints.

Example:

```text
nav_history + html/text/csv → NAV parser
portfolio_disclosure + xlsx/xls → Excel portfolio parser
portfolio_disclosure + pdf → PDF portfolio parser
factsheet + pdf → factsheet metadata parser
zip → unpack and recursively route contained files
json/api → JSON parser
```

## Required Parsers

### 1. AMC/provider list parser

Inputs:

- HTML tables,
- AMFI list pages,
- links from AMFI to provider websites.

Outputs:

- AMC name,
- normalized name,
- website URL,
- AMFI code if available,
- provenance.

### 2. Scheme metadata parser

Inputs:

- AMFI scheme pages/downloads,
- CSV/text tables,
- HTML tables,
- API responses.

Outputs:

- scheme code,
- scheme name,
- AMC hint,
- category/subcategory if available,
- plan/option if available.

### 3. NAV history parser

Inputs:

- AMFI NAV pages/downloads,
- text/CSV/HTML/API data.

Outputs:

- scheme code,
- date,
- NAV value,
- sale/repurchase price if available.

Validation:

- scheme code present,
- NAV date parseable,
- NAV numeric,
- unique scheme_code + date.

### 4. Excel/CSV portfolio parser

Inputs:

- XLS,
- XLSX,
- CSV,
- extracted files from ZIP.

Outputs:

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
- coupon,
- maturity date,
- rating.

Parser must handle:

- multiple sheets,
- merged headers,
- extra title rows,
- different column names,
- summary rows,
- debt/equity sections,
- empty rows,
- inconsistent date formats.

Column mapping should be heuristic and configurable.

Common column aliases:

```text
security_name: Name of Instrument, Security, Company, Name, Instrument
isin: ISIN, ISIN Code
quantity: Quantity, No. of Shares, Face Value, Units
market_value: Market Value, Market Value (Rs. in Lakhs), Value, Fair Value
percentage_to_nav: % to NAV, % of Net Assets, % Net Assets, Percentage
sector: Industry, Sector, Rating/Industry
rating: Rating, Credit Rating
maturity_date: Maturity, Maturity Date
coupon: Coupon, Coupon Rate
```

### 5. PDF portfolio parser

Use best-effort PDF table extraction.

Inputs:

- text-based PDFs,
- table PDFs.

Outputs:

- same as portfolio parser where possible.

If the PDF is scanned/image-heavy or table extraction confidence is low, quarantine with reason.

### 6. Factsheet metadata parser

Initial version may extract metadata only:

- AMC,
- scheme hints,
- document month/reporting date,
- source URL,
- file checksum,
- detected schemes,
- pages count if available.

Detailed factsheet financial extraction can be added later.

## Staging First

All parser output must go to staging rows before canonical loading.

Never directly trust parser output.

## Parser Result Contract

Each parser should return:

```python
ParserResult(
    dataset_type="portfolio_disclosure",
    parser_name="excel_portfolio_v1",
    parser_version="1.0.0",
    confidence=0.84,
    records=[...],
    warnings=[...],
    errors=[...],
    metadata={...}
)
```

## Parser Failure Handling

If parsing fails:

1. Store raw artifact metadata.
2. Store error in quarantine.
3. Mark retryable if a different strategy may work.
4. Do not crash the whole run unless configured with `--fail-fast`.
