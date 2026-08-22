"""One-off probe 10: loose grep of UTI chunk 9880 for endpoints + data fields."""
import re
import time

import requests

H = {"User-Agent": "Mozilla/5.0"}
u = "https://www.utimf.com/9880.a5ac9d706e6fce75.js"
r = requests.get(u, headers=H, timeout=60)
t = r.text
print("len", len(t))
for pat in [r'api/[A-Za-z0-9_/\-]{2,60}', r'cmsUrl[^,;]{0,80}', r'field_category[^"\']{0,40}', r'"[^"]*portfolio[^"]*"']:
    hits = sorted(set(re.findall(pat, t, re.I)))[:30]
    print(f"== {pat}: {len(hits)}")
    for h in hits:
        print("   ", h[:140])
