"""Download SBI sample with requests (follows redirects) and inspect sheets."""
import sys
from pathlib import Path

import pandas as pd
import requests

H = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
url = "https://www.sbimf.com/docs/default-source/scheme-portfolios/all-schemes-monthly-portfolio---as-on-30th-september-2025.xlsx?sfvrsn=72d21cf2_2"
r = requests.get(url, headers=H, timeout=120)
print("status:", r.status_code, "bytes:", len(r.content), r.content[:4])
out = Path("data/tmp/sbi_sample2.xlsx")
out.write_bytes(r.content)

x = pd.ExcelFile(out, engine="openpyxl")
print("sheets:", len(x.sheet_names), x.sheet_names[:12])
df = pd.read_excel(x, sheet_name=x.sheet_names[0], header=None, dtype=str)
print(df.shape)
print(df.head(10).to_string()[:1800])
