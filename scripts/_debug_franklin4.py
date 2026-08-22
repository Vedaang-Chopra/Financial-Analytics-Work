"""Debug: Franklin literature API structure (FirstDropDown etc.)."""
import json
import re
import time

import requests

H = {"User-Agent": "Mozilla/5.0"}
r = requests.get("https://www.franklintempletonindia.com/api/literature/v1/responseLitJson?type=report", headers=H, timeout=90)
j = r.json()
print("top keys:", list(j.keys()))


def show(node, depth=0, maxdepth=3):
    if depth > maxdepth:
        return
    if isinstance(node, dict):
        for k, v in list(node.items())[:12]:
            desc = f"len={len(v)}" if isinstance(v, (list, dict)) else str(v)[:70]
            print("  " * depth + f"{k}: {type(v).__name__} {desc}")
            if isinstance(v, (dict, list)) and depth < maxdepth:
                show(v, depth + 1, maxdepth)
    elif isinstance(node, list) and node:
        print("  " * depth + f"[0]:")
        show(node[0], depth + 1, maxdepth)


show(j)
