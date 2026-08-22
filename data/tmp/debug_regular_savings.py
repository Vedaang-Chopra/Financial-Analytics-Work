"""Check Regular Savings Fund: 121-126% — what's double-counted?"""
import sys, io, zipfile
sys.path.insert(0, '.')
import requests, pandas as pd

url = "https://www.icicipruamc.com/blob/downloads/Files/Fortnightly%20Portfolio%20Disclosures/2026/Fortnightly%20Debt%20Scheme%20Portfolio%20-%2015th%20August%202026.zip"
resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=120)
zf = zipfile.ZipFile(io.BytesIO(resp.content))
names = [n for n in zf.namelist() if "Regular Savings" in n]
print("files:", names)
for n in names:
    sheets = pd.read_excel(io.BytesIO(zf.read(n)), sheet_name=None, header=None)
    for sh, d in sheets.items():
        # find total row
        mask = d.apply(lambda row: row.astype(str).str.contains("Total Net Assets", case=False).any(), axis=1)
        idxs = list(d[mask].index)
        for i in idxs:
            row = d.iloc[i]
            print(n[:40], "| sheet:", sh, "| row:", [str(v)[:30] for v in row.values if str(v) != 'nan'][:4])
