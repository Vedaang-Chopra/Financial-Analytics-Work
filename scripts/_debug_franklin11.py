"""Debug: Franklin main.js - how is literatureApi/documents used for downloads."""
import re

import requests

H = {"User-Agent": "Mozilla/5.0"}
r = requests.get("https://www.franklintempletonindia.com/main.290c50984c6d19c0.js", headers=H, timeout=90)
t = r.text
idx = 0
for m in re.finditer(r'getLiteratureApiUrl|/api/literature/v1/documents|literatureHref\)', t):
    s = max(0, m.start() - 150)
    frag = t[s:m.start() + 300].replace("\n", " ")
    print(">>", frag[:420])
    print("---")
    idx += 1
    if idx > 8:
        break
