"""One-off probe 8: resolve UTI lazy chunks and grep them."""
import re
import time

import requests

H = {"User-Agent": "Mozilla/5.0"}
r = requests.get("https://www.utimf.com/runtime.f65cd7a13bffabf2.js", headers=H, timeout=60)
t = r.text
print("runtime len", len(t))
# Angular runtime has chunk->hash map, e.g. {8592:"abc123"} and a template like main.<hash>.js
names = re.findall(r'(\d+)\s*:\s*"([0-9a-f]{8,16})"', t)
print("chunk map entries:", len(names))
m = dict(names)
for cid in ("8592", "9880"):
    print(cid, "->", m.get(cid))

# find the js filename pattern
pm = re.findall(r'"\."?\+\w+\.\{1\}\+"\.js"', t)
print("template:", pm[:3])
tpl = re.search(r'\+\s*\w+\s*\+\s*"\.js"', t)
# typical: script.src = __webpack_require__.p + "" + (chunkId) + "." + {...}[chunkId] + ".js"
idx = t.find(".js")
print(t[max(0, idx-400):idx+50])
