"""One-off probe 14: UTI consolidate portfolio disclosure APIs."""
import time

import requests

H = {"User-Agent": "Mozilla/5.0"}
for u in [
    "https://www.utimf.com/api/get-consolidate-portfolio-disclosure?year=2026&month=July",
    "https://www.utimf.com/api/get-consolidate-debt-portfolio-disclosure?year=2026&month=July",
]:
    r = requests.get(u, headers=H, timeout=60)
    print("==", u)
    print(r.status_code, len(r.content), r.headers.get("content-type"))
    print(r.text[:1200])
    time.sleep(1.5)
