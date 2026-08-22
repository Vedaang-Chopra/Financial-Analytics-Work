"""One-off probe 4: Franklin SSD link context + UTI disclosure routes."""
import json
import re

import requests

H = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

# Franklin: find label text near each xls link
r = requests.get(
    "https://www.franklintempletonindia.com/resourceapi/reports?first-load=true&segment=investor",
    headers=H, timeout=60,
)
s = r.text
for m in set(re.findall(r'https?://portal\.amfiindia\.com/spages/SSD_\d+\.xls', s)):
    idx = s.find(m)
    print("CTX:", s[max(0, idx - 300):idx].replace("\\n", " ")[-260:])
    print("---")
