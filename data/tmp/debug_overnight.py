"""Overnight Fund: 4.5-86% — check the raw sheet. Overnight funds hold mostly
TREPS/cbloc which ICICI may disclose as aggregate-only."""
import sys, io, zipfile
sys.path.insert(0, '.')
import requests, pandas as pd

url = "https://www.icicipruamc.com/blob/downloads/Files/Fortnightly%20Portfolio%20Disclosures/2026/Fortnightly%20Debt%20Scheme%20Portfolio%20-%2015th%20August%202026.zip"
resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=120)
zf = zipfile.ZipFile(io.BytesIO(resp.content))
name = [n for n in zf.namelist() if "Overnight" in n][0]
d = pd.read_excel(io.BytesIO(zf.read(name)), sheet_name=0, header=None)
mask = d[1].astype(str).str.contains("Total Net Assets", case=False, na=False)
i = list(d[mask].index)[0]
print(d.iloc[max(0, i-14):i+1, [1, 2, 6, 7]].to_string(max_colwidth=40))
