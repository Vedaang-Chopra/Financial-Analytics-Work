"""Debug: test Franklin document download endpoint."""
import json

import requests

H = {"User-Agent": "Mozilla/5.0"}
r = requests.get("https://www.franklintempletonindia.com/api/literature/v1/responseLitJson?type=report", headers=H, timeout=90)
j = r.json()
href = None
for cat in j["FirstDropDown"]:
    if cat.get("id") == "MONTHLY-PORTFOLIO-DSCLR":
        href = cat["dataRecords"]["linkdata"][0]["literatureHref"]
        break
print("href:", href)

for candidate in [
    f"https://www.franklintempletonindia.com/api/literature/v1/documents{href}",
    f"https://www.franklintempletonindia.com/api/literature/v1/document{href}",
    f"https://www.franklintempletonindia.com{href}?download=true",
]:
    rr = requests.get(candidate, headers=H, timeout=60, allow_redirects=True)
    ct = rr.headers.get("content-type", "")
    print("==", candidate[:110], "->", rr.status_code, ct, len(rr.content), rr.content[:4])
