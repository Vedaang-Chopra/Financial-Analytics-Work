"""Debug: list Franklin FirstDropDown categories + find portfolio ones."""
import json
import re
import time

import requests

H = {"User-Agent": "Mozilla/5.0"}
r = requests.get("https://www.franklintempletonindia.com/api/literature/v1/responseLitJson?type=report", headers=H, timeout=90)
j = r.json()
for cat in j["FirstDropDown"]:
    cid = cat.get("id")
    n_links = len(cat.get("dataRecords", {}).get("linkdata", []))
    print(f"{cid}: linkdata={n_links} secondDD={len(cat.get('secondDropDown', []))}")

# find portfolio-ish category and sample its links
print("\n--- portfolio categories:")
for cat in j["FirstDropDown"]:
    if "portfolio" in cat.get("id", "").lower() or "portfolio" in json.dumps(cat).lower():
        s = json.dumps(cat)
        xls = sorted(set(re.findall(r'https://[^"\\\s]+?\.(?:xlsx|xls|zip)', s)))
        print(cat.get("id"), "file urls:", len(xls))
        for u in xls[:5]:
            print("   ", u[:150])
