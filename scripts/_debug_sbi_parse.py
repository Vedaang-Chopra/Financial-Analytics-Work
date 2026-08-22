"""Debug: parse SBI file directly with logging."""
import logging

import requests

logging.basicConfig(level=logging.DEBUG)

H = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
url = "https://www.sbimf.com/docs/default-source/scheme-portfolios/all-schemes-monthly-portfolio---as-on-31st-may-2026.xlsx?sfvrsn=1e792ce4_2"
r = requests.get(url, headers=H, timeout=120)
print("status:", r.status_code, len(r.content), r.content[:4])
if not r.content.startswith(b"PK"):
    # try half-yearly
    url = "https://www.sbimf.com/docs/default-source/scheme-portfolios/all-scheme-half-yearly-portfolio---as-on-30th-september-2025.xlsx?sfvrsn=f56282e3_2"
    r = requests.get(url, headers=H, timeout=120)
    print("2nd status:", r.status_code, len(r.content), r.content[:4])

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mutual_fund_ingestion.agent.parser import parse_file

result = parse_file(
    "portfolio_disclosure", "xlsx", r.content,
    {"source_url": url, "amc_name": "SBI Mutual Fund", "run_id": "debug"},
)
print("parser:", result.parser_name, "records:", len(result.records), "conf:", result.confidence)
for rec in result.records[:3]:
    print({k: rec.get(k) for k in ("scheme_name", "reporting_date", "security_name", "percentage_to_nav")})
