"""Debug: Franklin - find href binding for document rows."""
import re

import requests

H = {"User-Agent": "Mozilla/5.0"}
r = requests.get("https://www.franklintempletonindia.com/main.290c50984c6d19c0.js", headers=H, timeout=90)
t = r.text
for pat in [r'.{150}Q6J\("href".{0,200}', r'getDocumentLink[^;]{0,250}', r'\.link\b[^;]{0,80}window\.open[^;]{0,120}']:
    for m in sorted(set(re.findall(pat, t)))[:10]:
        print(">>", m.replace("\n", " ")[:380])
        print("---")
