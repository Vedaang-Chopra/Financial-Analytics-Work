# AMFI Portfolio Disclosure Investigation

## Source

- Current source: <https://www.amfiindia.com/online-center/portfolio-disclosure>
- Historical URL found in this repository:
  `https://www.amfiindia.com/investor-corner/online-center/portfoliodisclosure`

## Confirmed behavior

The current AMFI page is a disclosure hub with a **Select Disclosure Type**
control. Disclosure results are expected to appear after choosing a disclosure
type rather than being presented as a normal static article.

The repository contains an older Selenium exploration notebook at
`Code Base/Dataset_Collection_Module/data_collection_module/jupyter notebooks/portfolio_distribution.ipynb`.
That notebook attempted to interact with the historical page and looked for a
`divMonthlyPortfolio` result section, but its saved execution failed before it
extracted any links. It is evidence of dynamic behavior, not a working crawler
or a reliable current selector.

During implementation on June 6, 2026, direct HTTPS requests and browser
navigation to the current AMFI source timed out from the development
environment. Therefore, the current response HTML and network endpoints could
not be conclusively inspected from this machine.

## Implemented discovery strategy

1. Request the AMFI page with a descriptive user agent, timeout, retry, and
   exponential backoff.
2. Extract direct PDF, XLS, XLSX, CSV, and ZIP links from static HTML.
3. Identify relevant portfolio/disclosure landing pages and follow them by one
   hop to locate raw files.
4. If static AMFI discovery yields neither files nor landing pages, use
   Playwright to operate native disclosure selectors, click uniquely identified
   portfolio disclosure controls, inspect resulting HTML, and observe direct
   file network responses.
5. Save screenshots and HTML under `data/debug/amfi/` when browser discovery
   fails.

Playwright is a fallback rather than the primary discovery mechanism because a
direct endpoint or static link is simpler to automate and less dependent on
page structure.

## Limitations

- AMC websites do not share one disclosure-page structure. The first milestone
  follows only the AMC pages linked from AMFI and does not recursively crawl
  their websites.
- AMC names and dates are best-effort metadata inferred from link labels,
  titles, URLs, and file names.
- A source timeout is treated as a failure, not as a successful discovery run
  containing zero links.
- Live discovery must be rerun from a network that can reach AMFI to confirm
  the current disclosure selector and any underlying API requests.

## Recommended next phase

After a representative raw-file sample is collected, classify files by AMC and
format, retain the original files unchanged, and build separate normalized
portfolio parsers with fixture-based tests. Parsing and analytics are
intentionally outside this milestone.
