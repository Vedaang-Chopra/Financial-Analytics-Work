"""Debug: Franklin envConfig - downloadsApi / indiaLiterature endpoints."""
import re

import requests

H = {"User-Agent": "Mozilla/5.0"}
r = requests.get("https://www.franklintempletonindia.com/main.290c50984c6d19c0.js", headers=H, timeout=90)
t = r.text
for pat in [r'downloadsApi[^,}]{0,140}', r'indiaLiterature[^,}]{0,140}', r'.{40}downloadFile.{200}', r'literatureBRConfig[^;]{0,160}']:
    for m in sorted(set(re.findall(pat, t)))[:8]:
        print(">>", m.replace("\n", " ")[:260])
        print("---")
