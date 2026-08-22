"""Debug: Franklin reports API - find how category filters map to requests."""
import re

import requests

H = {"User-Agent": "Mozilla/5.0"}
# custom script likely holds the app config
r = requests.get("https://www.franklintempletonindia.com/scripts.72039fd36c8dfade.js", headers=H, timeout=60)
t = r.text
print("scripts.js len:", len(t))
for pat in [r'.{80}resourceapi.{150}', r'.{60}firstFilter.{120}', r'.{50}first-load.{120}']:
    for m in re.findall(pat, t)[:6]:
        print(">>", m[:260])
        print("---")
