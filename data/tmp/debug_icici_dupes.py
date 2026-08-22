"""Debug: find where duplicate NULL-isin holdings originate for ICICI zips."""
import sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import requests

from mutual_fund_ingestion.agent.parser import parse_file
from mutual_fund_ingestion.agent.validate import validate_and_filter_records

url = "https://www.icicipruamc.com/blob/downloads/Files/Fortnightly%20Portfolio%20Disclosures/2026/Fortnightly%20Debt%20Scheme%20Portfolio%20-%2015th%20August%202026.zip"
resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=120)
print("fetched", len(resp.content))

result = parse_file("portfolio_disclosure", "zip", resp.content,
                    {"source_url": url, "amc_name": "ICICI Prudential Mutual Fund", "file_ext": ".zip"})
records = result.records
print("total parsed records:", len(records))

valid, quarantined, warnings = validate_and_filter_records(result, "debug", return_warnings=True)
print("valid:", len(valid), "quarantined:", len(quarantined))

# group like upsert_portfolio does (by scheme_name + reporting_date pre-DB)
groups = Counter()
dupes = Counter()
for r in valid:
    key = (r.get("scheme_name"), r.get("reporting_date"))
    groups[key] += 1
    hkey = (key, r.get("security_name"), str(r.get("isin")))
    dupes[hkey] += 1

real_dupes = {k: v for k, v in dupes.items() if v > 1}
print("groups:", len(groups))
print("duplicate (scheme,date,security,isin) keys within valid records:", len(real_dupes))
for k, v in list(real_dupes.items())[:10]:
    print("  DUP x%d:" % v, k)

# specifically the failing row
target = [r for r in valid if r.get("security_name") == "Interest Rate Swaps- MD -14-May-2029 (Pay float/receive fixed)"]
print("\nrows matching failing security:", len(target))
for r in target:
    print("   ", {k: r.get(k) for k in ("scheme_name", "reporting_date", "isin", "market_value", "percentage_to_nav", "source_zip_file", "sheet_name")})
