"""One-off probe 15: Kotak statutory disclosure pages (single polite attempt)."""
import re
import time

import requests

H = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

for u in [
    "https://www.kotakmf.com/Information/statutory-disclosure/information",
    "https://www.kotakmf.com/sitemap.xml",
]:
    r = requests.get(u, headers=H, timeout=60)
    print("==", u, "->", r.status_code, len(r.text))
    if r.ok:
        links = sorted(set(re.findall(r'href="([^"]*(?:xls|zip)[^"]*)"', r.text, re.I)))
        print("   file links:", len(links))
        for l in links[:10]:
            print("   ", l[:160])
        apis = sorted(set(re.findall(r'["\'](/[^"\']*(?:api|Api|get)[^"\']{0,80})["\']', r.text)))[:20]
        print("   api hints:", apis)
    time.sleep(3)
