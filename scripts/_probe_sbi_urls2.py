"""One-off probe: grep SBI portfolios page HTML for endpoint hints."""
import requests, re

H = {"User-Agent": "Mozilla/5.0"}
r = requests.get("https://www.sbimf.com/portfolios", headers=H, timeout=30)
t = r.text
print("len:", len(t))
for pat in [r"SCHEME_PORTFOLIO", r"GetPortfolio", r"Portfolios/", r"DataBindUrls", r"APIURLS"]:
    hits = sorted(set(re.findall(r".{40}" + pat + r".{100}", t)))
    print(f"== {pat}: {len(hits)}")
    for h in hits[:5]:
        print("   ", h.replace("\n", " ")[:200])
