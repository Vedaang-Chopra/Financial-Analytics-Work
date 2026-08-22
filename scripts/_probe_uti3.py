"""One-off probe 6: UTI main.js grep for downloads API patterns."""
import re

import requests

H = {"User-Agent": "Mozilla/5.0"}
r = requests.get("https://www.utimf.com/main.d4481564c1609f6a.js", headers=H, timeout=60)
t = r.text
pats = [
    r'["\'][^"\']*(?:fd_target|field_category|forms_and_downloads|FormsAndDownload|download)[^"\']*["\']',
    r'api/[^"\']{0,80}',
]
seen = set()
for pat in pats:
    for m in re.findall(pat, t, re.I):
        m2 = m[:140]
        if m2 not in seen and len(m) < 150:
            seen.add(m2)
            print("  ", m2)
