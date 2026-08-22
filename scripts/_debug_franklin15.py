"""Debug: Franklin - find getData$(...) call sites and documents API params."""
import re

import requests

H = {"User-Agent": "Mozilla/5.0"}
r = requests.get("https://www.franklintempletonindia.com/main.290c50984c6d19c0.js", headers=H, timeout=90)
t = r.text
for m in re.finditer(r'\.getData\$\(([^)]{0,120})\)', t):
    frag = t[max(0, m.start() - 200):m.end() + 100].replace("\n", " ")
    print(">>", frag[:400])
    print("---")
