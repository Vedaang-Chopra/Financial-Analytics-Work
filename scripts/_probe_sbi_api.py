"""One-off probe: SBI GetSchemePortfolioSheets via plain requests."""
import json
import time

import requests
from bs4 import BeautifulSoup

H = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Content-Type": "application/json; charset=utf-8",
    "Referer": "https://www.sbimf.com/portfolios",
}

for freq in ("Monthly",):
    r = requests.post(
        "https://www.sbimf.com/ajaxcall/CMS/GetSchemePortfolioSheets",
        headers=H,
        data=json.dumps({"FundId": "", "PSYear": "", "PSMonth": "", "PSFrequency": freq}),
        timeout=30,
    )
    print(freq, r.status_code, len(r.text))
    soup = BeautifulSoup(r.text, "html.parser")
    urls = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().split("?")[0].endswith((".xlsx", ".xls", ".zip")):
            urls.append(href)
    print("file links:", len(urls))
    for u in urls[:6]:
        print("  ", u[:150])
    # also try Half Yearly
    time.sleep(1.5)

r = requests.post(
    "https://www.sbimf.com/ajaxcall/CMS/GetSchemePortfolioSheets",
    headers=H,
    data=json.dumps({"FundId": "", "PSYear": "", "PSMonth": "", "PSFrequency": "Half Yearly"}),
    timeout=30,
)
print("HalfYearly", r.status_code, len(r.text))
soup = BeautifulSoup(r.text, "html.parser")
urls = [a["href"] for a in soup.find_all("a", href=True) if a["href"].lower().split("?")[0].endswith((".xlsx", ".xls", ".zip"))]
print("half-yearly links:", len(urls))
for u in urls[:4]:
    print("  ", u[:150])
