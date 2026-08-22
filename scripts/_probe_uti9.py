"""One-off probe 12: UTI dofa/document_filter_api endpoint patterns."""
import re
import time

import requests

H = {"User-Agent": "Mozilla/5.0"}
r = requests.get("https://www.utimf.com/main.d4481564c1609f6a.js", headers=H, timeout=60)
t = r.text
for pat in [r'.{100}dofa.{200}', r'getSchemesBasedOnCategory\(\)\{[^}]{0,400}', r'document_filter_api.{0,150}', r'api/get_investor_scheme_fund.{0,200}']:
    for m in re.findall(pat, t)[:5]:
        print(">>", m[:350])
        print("---")
