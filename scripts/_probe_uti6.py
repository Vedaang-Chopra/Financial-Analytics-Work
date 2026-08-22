"""One-off probe 9: grep UTI lazy chunks for portfolio download APIs."""
import re
import time

import requests

H = {"User-Agent": "Mozilla/5.0"}
for cid, h in (("8592", "4abeb51ab1429847"), ("9880", "a5ac9d706e6fce75")):
    u = f"https://www.utimf.com/{cid}.{h}.js"
    r = requests.get(u, headers=H, timeout=60)
    print("==", u, r.status_code, len(r.text))
    t = r.text
    hits = set()
    for m in re.findall(r'["\'`]([^"\'`]{0,140})["\'`]', t):
        ml = m.lower()
        if ("api" in ml and ("portfolio" in ml or "download" in ml or "forms" in ml or "disclosure" in ml)) or "portfolio" in ml and "/" in ml:
            hits.add(m)
    for h2 in sorted(hits)[:40]:
        print("   ", h2[:150])
    time.sleep(1)
