"""One-off probe 2: deeper greps of UTI + Franklin bundles."""
import re
import time

import requests

H = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}


def get(url):
    return requests.get(url, headers=H, timeout=60)


# --- UTI main bundle
r = get("https://www.utimf.com/main.d4481564c1609f6a.js")
t = r.text
print("UTI main.js:", r.status_code, len(t))
pats = [r'["\'][^"\']*portfolio[^"\']*["\']', r'["\'][^"\']*Download[^"\']*["\']', r'https?://[^"\']*xls[^"\']*']
seen = set()
for pat in pats:
    for m in re.findall(pat, t):
        ml = m.lower()
        if len(m) < 150 and ("/" in m or "." in m) and " " not in m:
            key = m
            if key not in seen:
                seen.add(key)
                print("  ", m[:140])
    time.sleep(0.5)
