"""One-off probe 16: inspect Kotak challenge page + sitemap index."""
import requests

H = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}
r = requests.get("https://www.kotakmf.com/sitemap.xml", headers=H, timeout=30)
print(r.text[:600])
print("=====")
r = requests.get("https://www.kotakmf.com/Information/statutory-disclosure/information", headers=H, timeout=30)
t = r.text
print("page len:", len(t))
import re
title = re.search(r"<title>(.*?)</title>", t, re.S)
print("title:", title.group(1)[:120] if title else None)
print(t[:800])
