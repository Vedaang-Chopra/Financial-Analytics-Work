"""Check Gilt Fund sheet: are we losing rows (e.g. SOV section) or is the
disclosure genuinely partial (cash/TREPS not itemized)?"""
import sys
import io
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import requests
import pandas as pd

url = "https://www.icicipruamc.com/blob/downloads/Files/Fortnightly%20Portfolio%20Disclosures/2026/Fortnightly%20Debt%20Scheme%20Portfolio%20-%2015th%20August%202026.zip"
resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=120)
zf = zipfile.ZipFile(io.BytesIO(resp.content))
name = [n for n in zf.namelist() if "Gilt Fund" in n and "Constant" not in n]
print("candidates:", name)
df = pd.read_excel(io.BytesIO(zf.read(name[0])), sheet_name=None, header=None)
for sheet, d in df.items():
    print("=== sheet:", sheet, d.shape)

d = df[list(df.keys())[0]]
# print last 30 rows to see totals / cash sections
print(d.tail(28).to_string(max_colwidth=38))
