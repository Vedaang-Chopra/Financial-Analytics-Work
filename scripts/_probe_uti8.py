"""One-off probe 11: find getFilesData impl + service endpoints in UTI chunk."""
import re
import time

import requests

H = {"User-Agent": "Mozilla/5.0"}
r = requests.get("https://www.utimf.com/9880.a5ac9d706e6fce75.js", headers=H, timeout=60)
t = r.text
for pat in [r'getFilesData[^}]{0,400}', r'schemeWisePortfolioDisclosure\([^)]{0,200}\)?[^}]{0,300}', r'getSchemesBasedOnCategory[^}]{0,200}', r'\.subscribe\(e=>.{0,120}rows']:
    for m in re.findall(pat, t)[:4]:
        print(">>", m[:420])
        print("---")
