"""One-off probe 7: find UTI downloads data endpoint."""
import re
import time

import requests

H = {"User-Agent": "Mozilla/5.0"}
r = requests.get("https://www.utimf.com/main.d4481564c1609f6a.js", headers=H, timeout=60)
t = r.text
for pat in [r'.{80}download-list.{200}', r'.{60}scheme-wise-portfolio.{150}', r'.{80}consolidate-debt.{150}', r'get_forms[^"\']{0,60}', r'forms_download_url.{0,120}']:
    for m in re.findall(pat, t):
        print(">>", m[:280])
        print("---")

# try candidate endpoints
for u in [
    "https://www.utimf.com/api/download-list",
    "https://www.utimf.com/api/get_forms_and_downloads",
    "https://www.utimf.com/api/forms-and-downloads",
    "https://www.utimf.com/api/downloads",
]:
    rr = requests.get(u, headers=H, timeout=30)
    print(u, rr.status_code, len(rr.content))
    time.sleep(1)
