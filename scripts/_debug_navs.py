"""Debug: why HDFC/Nippon/Franklin navigators return 0."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from mutual_fund_ingestion.agent.portfolio_navigators import _get_with_headers
from bs4 import BeautifulSoup

# HDFC
r = _get_with_headers("https://www.hdfcfund.com/statutory-disclosure/portfolio/monthly-portfolio")
print("HDFC:", r.status_code, len(r.text))
soup = BeautifulSoup(r.text, "html.parser")
xls = [a["href"] for a in soup.find_all("a", href=True) if a["href"].lower().split("?")[0].endswith((".xlsx", ".xls", ".zip"))]
print("  raw file links:", len(xls), xls[:2])

# Nippon
r = _get_with_headers("https://mf.nipponindiaim.com/investor-service/downloads/factsheet-portfolio-and-other-disclosures")
print("NIPPON:", r.status_code, len(r.text))
soup = BeautifulSoup(r.text, "html.parser")
nim = [a["href"] for a in soup.find_all("a", href=True) if "NIMF" in a["href"].upper()]
print("  NIMF links:", len(nim), nim[:2])

# Franklin
r = _get_with_headers("https://www.franklintempletonindia.com/resourceapi/reports?first-load=true&segment=investor")
print("FRANKLIN:", r.status_code, len(r.text))
idx = r.text.find("literatureHref")
print("  raw ctx:", repr(r.text[idx - 20:idx + 120]) if idx >= 0 else "not found")
