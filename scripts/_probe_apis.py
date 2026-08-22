"""One-off probe: UTI + Franklin JSON APIs via plain requests."""
import json
import re
import time

import requests

H = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}


def dump(label, url):
    r = requests.get(url, headers=H, timeout=60)
    print(f"\n### {label}: {r.status_code} {r.headers.get('content-type','')[:40]} len={len(r.content)}")
    if r.status_code == 200:
        try:
            j = r.json()
            print("  JSON ok, top keys:", list(j.keys())[:15] if isinstance(j, dict) else type(j))
            return j
        except Exception as e:
            print("  not json:", str(e)[:80])
    return None


j = dump("UTI downloads", "https://www.utimf.com/api/page/forms-and-downloads-downloads")
if isinstance(j, dict):
    txt = json.dumps(j)
    hits = sorted(set(re.findall(r'https?://[^"\\ ]*\.(?:xlsx?|zip)', txt)))
    print("  file urls:", len(hits))
    for h in hits[:12]:
        print("   ", h[:150])
    # also relative
    rel = sorted(set(re.findall(r'"(/[^"]*\.(?:xlsx?|zip))"', txt)))
    print("  rel urls:", len(rel), rel[:6])
time.sleep(1.5)

for u in [
    "https://www.franklintempletonindia.com/resourceapi/reports?first-load=true&segment=investor",
    "https://www.franklintempletonindia.com/api/literature/v1/responseLitJson?type=report",
]:
    j = dump("FRANKLIN " + u[-50:], u)
    if j is not None:
        txt = json.dumps(j)
        hits = sorted(set(re.findall(r'https?://[^"\\ ]*\.(?:xlsx?|zip|pdf)', txt)))
        xls = [h for h in hits if ".xls" in h or ".zip" in h]
        print("  total file urls:", len(hits), "| xls/zip:", len(xls))
        for h in hits[:10]:
            print("   ", h[:150])
    time.sleep(1.5)
