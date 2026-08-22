"""One-off probe: UTI / Kotak / Franklin SPA bundles for API endpoints."""
import re
import time

import requests

H = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}


def get(url, **kw):
    return requests.get(url, headers=H, timeout=40, **kw)


# --- UTI: find JS bundles from a real page
r = get("https://www.utimf.com/downloads/consolidate-debt-portfolio-disclosure")
print("UTI page:", r.status_code, len(r.text))
scripts = sorted(set(re.findall(r'src="([^"]+\.js[^"]*)"', r.text)))
print("UTI scripts:", scripts[:10])
time.sleep(1)

for s in scripts:
    url = s if s.startswith("http") else "https://www.utimf.com/" + s.lstrip("/")
    try:
        rr = get(url)
    except Exception as e:
        print("  EXC", url, e)
        continue
    t = rr.text
    hits = set()
    for m in re.findall(r'["\']([^"\']*(?:api|Api)[^"\']*)["\']', t):
        if len(m) < 120 and ("portfolio" in m.lower() or "download" in m.lower() or m.startswith("/api") or "/api/" in m):
            hits.add(m)
    if hits:
        print(f"== {s} ({len(t)}b):")
        for h in sorted(hits)[:25]:
            print("   ", h[:130])
    time.sleep(1)
