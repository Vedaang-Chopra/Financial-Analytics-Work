"""One-off probe: UTI page api for portfolio disclosure + Franklin report JSON structure."""
import json
import re
import time

import requests

H = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

# UTI: try the page-specific API path
for path in [
    "consolidate-debt-portfolio-disclosure",
    "monthly-portfolio-disclosure",
    "downloads",
]:
    u = f"https://www.utimf.com/api/page/{path}"
    r = requests.get(u, headers=H, timeout=60)
    print("UTI", path, r.status_code, len(r.content))
    if r.status_code == 200:
        txt = r.text
        hits = sorted(set(re.findall(r'https?://[^"\\ ]*\.(?:xlsx?|zip)', txt)))
        rel = sorted(set(re.findall(r'"(/[^"]*\.(?:xlsx?|zip)[^"]*)"', txt)))
        print("   abs:", len(hits), "rel:", len(rel))
        for h in (hits + rel)[:10]:
            print("   ", h[:150])
    time.sleep(1.5)

# Franklin: structure of resourceapi/reports
r = requests.get("https://www.franklintempletonindia.com/resourceapi/reports?first-load=true&segment=investor", headers=H, timeout=60)
j = r.json()
doc = j.get("document")
print("\nFRANKLIN document type:", type(doc))
s = json.dumps(doc)
# find portfolio-ish entries
for m in re.finditer(r'\{[^{}]{0,400}?[Pp]ortfolio[^{}]{0,400}?\}', s):
    frag = m.group(0)
    if ".xls" in frag or ".zip" in frag:
        print("  ", frag[:400])
        break
# list distinct "type" or category fields
types = sorted(set(re.findall(r'"(?:type|docType|category|firstFilter)"\s*:\s*"([^"]+)"', s)))
print("types:", types[:40])
