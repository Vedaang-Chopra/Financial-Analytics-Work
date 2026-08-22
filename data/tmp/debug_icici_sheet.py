"""Check the actual ICICI source sheet: is 'Non-Convertible debentures / Bonds'
a section header (whose children are also listed) or a real aggregate row?"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import requests
import io
import zipfile
import pandas as pd

url = "https://www.icicipruamc.com/blob/downloads/Files/Fortnightly%20Portfolio%20Disclosures/2026/Fortnightly%20Debt%20Scheme%20Portfolio%20-%2015th%20August%202026.zip"
resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=120)
zf = zipfile.ZipFile(io.BytesIO(resp.content))
name = [n for n in zf.namelist() if "Credit Risk" in n][0]
print("sheet:", name)
df = pd.read_excel(io.BytesIO(zf.read(name)), sheet_name=None, header=None)
for sheet, d in df.items():
    print("=== sheet:", sheet, d.shape)
# find rows around 'Non-Convertible'
for sheet, d in df.items():
    mask = d.apply(lambda row: row.astype(str).str.contains("Non-Convertible", case=False).any(), axis=1)
    idxs = list(d[mask].index)
    for i in idxs[:1]:
        print(f"--- rows {max(0,i-3)}..{i+8} of {sheet}:")
        print(d.iloc[max(0, i - 3):i + 9].to_string(max_colwidth=40))
