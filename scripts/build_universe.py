"""Resolve NIFTY 500 constituents to screener.in slugs.

Sequential search-API calls with 1.5s delay; results cached to
data/raw/screener/slug_map.csv so this only ever runs once.
"""

from __future__ import annotations

import csv
import time
import urllib.parse

import requests

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

companies = []
with open("/tmp/nifty500.csv", newline="") as f:
    for row in csv.DictReader(f):
        companies.append((row["Company Name"].strip(), row["Symbol"].strip()))

print(f"constituents: {len(companies)}")

session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept": "application/json"})
results = []
unresolved = []

for i, (name, symbol) in enumerate(companies):
    q = name.replace(" Ltd.", "").replace(" Ltd", "").replace(" Limited", "").strip()
    url = "https://www.screener.in/api/company/search/?q=" + urllib.parse.quote(q)
    try:
        resp = session.get(url, timeout=15)
        if resp.status_code != 200:
            unresolved.append((name, symbol, f"http {resp.status_code}"))
            continue
        items = resp.json()
    except Exception as exc:
        unresolved.append((name, symbol, str(exc)[:80]))
        continue

    # pick best match: exact consolidated match on normalized name, else first result
    def norm(s: str) -> str:
        return s.lower().replace("&", "and").replace(".", "").replace(",", "").strip()

    target = norm(q)
    slug = None
    matched_name = None
    for it in items:
        u = it.get("url", "")
        if "/consolidated/" in u and norm(it.get("name", "")) == target:
            slug = u.split("/company/")[1].split("/")[0]
            matched_name = it.get("name")
            break
    if slug is None and items:
        u = items[0].get("url", "")
        slug = u.split("/company/")[1].split("/")[0] if "/company/" in u else None
        matched_name = items[0].get("name") if slug else None
    if slug:
        results.append((symbol, name, slug, matched_name))
    else:
        unresolved.append((name, symbol, "no results"))

    done = i + 1
    if done % 50 == 0:
        print(f"{done}/{len(companies)} resolved ({len(results)} ok, {len(unresolved)} unresolved)")
    time.sleep(1.5)

import os
os.makedirs("data/raw/screener", exist_ok=True)
with open("data/raw/screener/universe_nifty500.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["nse_symbol", "company_name", "screener_slug", "screener_name"])
    w.writerows(results)
with open("data/raw/screener/unresolved.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["company_name", "nse_symbol", "reason"])
    w.writerows(unresolved)

print(f"\nDONE: {len(results)} resolved -> data/raw/screener/universe_nifty500.csv")
print(f"      {len(unresolved)} unresolved -> data/raw/screener/unresolved.csv")
