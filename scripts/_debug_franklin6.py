"""Debug: inspect MONTHLY-PORTFOLIO-DSCLR linkdata entries."""
import json

import requests

H = {"User-Agent": "Mozilla/5.0"}
r = requests.get("https://www.franklintempletonindia.com/api/literature/v1/responseLitJson?type=report", headers=H, timeout=90)
j = r.json()
for cat in j["FirstDropDown"]:
    if cat.get("id") in ("MONTHLY-PORTFOLIO-DSCLR", "FORTNIGHT-PORTFOLIO-DEBT-SCHEMES"):
        ld = cat["dataRecords"]["linkdata"]
        print("==", cat["id"], len(ld))
        print(json.dumps(ld[0], indent=1)[:900])
        print(json.dumps(ld[1], indent=1)[:400])
