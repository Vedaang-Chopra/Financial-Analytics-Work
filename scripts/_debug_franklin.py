"""Debug: Franklin resourceapi sections - where are real portfolio files?"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from mutual_fund_ingestion.agent.portfolio_navigators import _get_with_headers

r = _get_with_headers("https://www.franklintempletonindia.com/resourceapi/reports?first-load=true&segment=investor")
body = r.text
# Find section ids / names
for m in sorted(set(re.findall(r'\\?"id\\?":\\?"([^"\\]{3,60})\\?"', body)))[:80]:
    print("id:", m)
