"""One-off probe 3: UTI api field_api_path + Franklin JSON structure."""
import json
import re

import requests

H = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

r = requests.get("https://www.utimf.com/api/page/forms-and-downloads-downloads", headers=H, timeout=60)
j = r.json()
print("field_api_path:", j.get("field_api_path"))
print("sections_list:", json.dumps(j.get("sections_list"))[:800])
sd = j.get("sections_data")
print("sections_data type:", type(sd), str(sd)[:600])
import time; time.sleep(1)

# Franklin structure
r = requests.get(
    "https://www.franklintempletonindia.com/resourceapi/reports?first-load=true&segment=investor",
    headers=H, timeout=60,
)
j = r.json()


def walk(node, depth=0, path=""):
    if depth > 4:
        return
    if isinstance(node, dict):
        for k, v in list(node.items())[:20]:
            print("  " * depth + f"{k}: {type(v).__name__}" + (f" = {str(v)[:80]}" if not isinstance(v, (dict, list)) else f" len={len(v)}"))
            if k in ("document", "root", "channel", "items", "data", "list", "results") or depth < 2:
                walk(v, depth + 1, path + "/" + k)
    elif isinstance(node, list) and node:
        print("  " * depth + f"[0] sample:")
        walk(node[0], depth + 1, path + "[0]")


walk(j)
