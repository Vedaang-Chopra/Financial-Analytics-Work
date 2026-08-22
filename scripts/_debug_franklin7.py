"""Debug: how does Franklin resolve literatureHref to a file download?"""
import re

import requests

H = {"User-Agent": "Mozilla/5.0"}
for js in ["main.290c50984c6d19c0.js", "scripts.72039fd36c8dfade.js", "vendor.1008ff81df6cb926.js"]:
    r = requests.get(f"https://www.franklintempletonindia.com/{js}", headers=H, timeout=90)
    t = r.text
    for pat in [r'.{80}literatureHref.{200}', r'.{60}download[^"\']{0,40}(?:api|service|url).{0,120}']:
        hits = re.findall(pat, t, re.I)[:4]
        for m in hits:
            print(f"[{js}]>>", m.replace("\n", " ")[:300])
            print("---")
