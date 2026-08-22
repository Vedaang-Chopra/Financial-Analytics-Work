"""One-off probe: Kotak statutory-disclosure/information page + Franklin bundle."""
import re
import time

import requests

H = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}


def get(url, **kw):
    return requests.get(url, headers=H, timeout=40, **kw)


# --- Kotak information page (portfolio disclosures live here per SID)
for u in [
    "https://www.kotakmf.com/Information/statutory-disclosure/information",
    "https://www.kotakmf.com/Information/statutory-disclosure",
]:
    try:
        r = get(u)
        print("== KOTAK", u, r.status_code, len(r.text))
        if r.ok:
            links = sorted(set(re.findall(r'href="([^"]*(?:xls|zip)[^"]*)"', r.text, re.I)))
            print("   file links:", len(links))
            for l in links[:8]:
                print("   ", l[:150])
            apis = sorted(set(re.findall(r'["\'](/[^"\']*(?:api|Api)[^"\']{0,80})["\']', r.text)))[:15]
            print("   api hints:", apis)
    except Exception as e:
        print("   EXC", e)
    time.sleep(1.5)

# --- Franklin: fetch main bundle, grep for api endpoints
r = get("https://www.franklintempletonindia.com/investor/reports?firstFilter-10")
base = "https://www.franklintempletonindia.com"
scripts = sorted(set(re.findall(r'src="([^"]+\.js[^"]*)"', r.text)))
print("\nFRANKLIN scripts:", scripts)
for s in scripts:
    url = s if s.startswith("http") else base + s
    try:
        rr = get(url)
    except Exception as e:
        print("  EXC", url, e)
        continue
    t = rr.text
    hits = set()
    for m in re.findall(r'["\']([^"\']{4,120})["\']', t):
        ml = m.lower()
        if ("portfolio" in ml or "report" in ml or "download" in ml) and ("/" in m) and " " not in m and "\\" not in m:
            hits.add(m)
    if hits:
        print(f"== {s} ({len(t)}b): {len(hits)} hits")
        for h in sorted(hits)[:30]:
            print("   ", h[:140])
    time.sleep(1)
