"""Debug: Franklin literatureApi config + file download URL pattern."""
import re

import requests

H = {"User-Agent": "Mozilla/5.0"}
r = requests.get("https://www.franklintempletonindia.com/main.290c50984c6d19c0.js", headers=H, timeout=90)
t = r.text
for pat in [r'literatureApi[^,}]{0,140}', r'.{120}getLiteratureApiUrl\(\)\(\).{0,250}', r'.{60}/en-in/.{0,120}', r'widen[^"]{0,100}']:
    for m in sorted(set(re.findall(pat, t)))[:6]:
        print(">>", m.replace("\n", " ")[:320])
        print("---")
