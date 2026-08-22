"""Debug 2: HDFC link location + Franklin URL extraction."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from mutual_fund_ingestion.agent.portfolio_navigators import _get_with_headers
from bs4 import BeautifulSoup

r = _get_with_headers("https://www.hdfcfund.com/statutory-disclosure/portfolio/monthly-portfolio")
t = r.text
hits = sorted(set(re.findall(r'(https?://files\.hdfcfund\.com/s3fs-public/[^"\']*\.xlsx)', t)))
print("HDFC s3fs xlsx urls:", len(hits), hits[:2])
# where do they live? inside <a>?
soup = BeautifulSoup(t, "html.parser")
cnt_in_a = sum(1 for a in soup.find_all("a", href=True) if "s3fs-public" in a["href"] and a["href"].endswith(".xlsx"))
print("in <a> tags:", cnt_in_a)
# maybe in data attributes / json
for m in re.finditer(r'.{80}Monthly%20HDFC%20Arbitrage.{40}', t):
    print("CTX:", repr(m.group(0)[:220]))
    break
