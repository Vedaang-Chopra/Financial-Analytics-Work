"""Franklin: probe main.js for reports filter API + try firstFilter variants."""
import re
import time

import requests

H = {"User-Agent": "Mozilla/5.0"}
r = requests.get("https://www.franklintempletonindia.com/main.290c50984c6d19c0.js", headers=H, timeout=90)
t = r.text
print("main.js len:", len(t))
for pat in [r'.{100}resourceapi/reports.{200}', r'.{60}first-load.{160}', r'.{80}firstFilter.{140}']:
    for m in re.findall(pat, t)[:6]:
        print(">>", m.replace("\n", " ")[:320])
        print("---")

# try variants directly
for q in [
    "https://www.franklintempletonindia.com/resourceapi/reports?first-load=true&segment=investor&firstFilter=2",
    "https://www.franklintempletonindia.com/resourceapi/reports?firstFilter-10&segment=investor",
]:
    rr = requests.get(q, headers=H, timeout=60)
    xls = sorted(set(re.findall(r'https://[^"\\\s]+\.(?:xlsx|xls)', rr.text)))
    print(q[-60:], rr.status_code, "xls urls:", len(xls))
    time.sleep(1)
