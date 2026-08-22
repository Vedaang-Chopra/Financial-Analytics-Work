"""Debug: Franklin - how mapped link is built from literatureHref."""
import re

import requests

H = {"User-Agent": "Mozilla/5.0"}
r = requests.get("https://www.franklintempletonindia.com/main.290c50984c6d19c0.js", headers=H, timeout=90)
t = r.text
for m in re.finditer(r'link:', t):
    frag = t[m.start() - 120:m.start() + 260].replace("\n", " ")
    if "iterature" in frag or "href" in frag.lower() or "baseUrl" in frag or "window.open" in frag:
        print(">>", frag[:360])
        print("---")
