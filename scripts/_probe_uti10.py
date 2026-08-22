"""One-off probe 13: UTI forms-and-downloads page JSON — find document_filter_api."""
import json
import re

import requests

H = {"User-Agent": "Mozilla/5.0"}
r = requests.get("https://www.utimf.com/api/page/forms-and-downloads-downloads", headers=H, timeout=60)
t = r.text
print("len", len(t))
for pat in [r'document_filter_api', r'[^"]{0,120}portfolio[^"]{0,80}', r'/api/[A-Za-z0-9_/{}?\-&=\.]{2,90}']:
    hits = sorted(set(re.findall(pat, t, re.I)))
    print(f"== {pat[:30]}: {len(hits)}")
    for h in hits[:40]:
        print("   ", h[:160])
