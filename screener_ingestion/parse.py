"""Parsers for screener.in company pages.

Every parser returns plain dicts/lists so db.py stays storage-only.
All selectors are centralized here so markup drift is fixed in one place.
"""

from __future__ import annotations

import logging
import re
from datetime import date

from bs4 import BeautifulSoup, Tag

LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------- helpers

_NUM_RE = re.compile(r"-?[\d,]+\.?\d*")


def clean_text(el) -> str:
    if el is None:
        return ""
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip()


def to_number(text: str | None) -> float | None:
    """'3,34,388' -> 334388.0 ; '₹ 5,000' -> 5000.0 ; '12.63%' -> 12.63.

    Returns None for blanks, '-', or anything without digits.
    """
    if text is None:
        return None
    m = _NUM_RE.search(clean_text_of_tags(text))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def clean_text_of_tags(value) -> str:
    if isinstance(value, Tag):
        return value.get_text(" ", strip=True)
    return str(value)


def parse_period_date(date_key: str) -> date | None:
    """'2026-06-30' -> date; returns None on malformed keys."""
    try:
        return date.fromisoformat(date_key.strip())
    except ValueError:
        return None


def _period_iso(date_key: str) -> str | None:
    d = parse_period_date(date_key)
    return d.isoformat() if d else None


# ---------------------------------------------------------------- meta

def parse_company_meta(soup: BeautifulSoup) -> dict:
    """Name, exchange codes, sector hierarchy, about text."""
    meta: dict = {}
    h1 = soup.find("h1")
    meta["name"] = clean_text(h1) if h1 else None

    # BSE/NSE codes live in the .sub.company-links block
    codes_block = soup.select_one(".sub.company-links")
    codes: dict[str, str] = {}
    if codes_block:
        for a in codes_block.find_all("a"):
            text = clean_text(a)
            m = re.match(r"^(BSE|NSE):\s*([\w&.-]+)", text)
            if m:
                codes[m.group(1).lower()] = m.group(2)
    meta["bse_code"] = codes.get("bse")
    meta["nse_code"] = codes.get("nse")

    # sector hierarchy from peers section breadcrumb links
    peers_sec = soup.find("section", id="peers")
    sectors: list[str] = []
    if peers_sec:
        sub = peers_sec.select_one("p.sub")
        if sub:
            sectors = [clean_text(a) for a in sub.find_all("a")]
    # Industrials -> Capital Goods -> Aerospace & Defense -> Aerospace & Defense
    meta["sector_broad"] = sectors[0] if len(sectors) > 0 else None
    meta["sector"] = sectors[1] if len(sectors) > 1 else None
    meta["industry"] = sectors[-1] if sectors else None

    # about text
    about = soup.select_one(".company-info")
    meta["about_text"] = clean_text(about) if about else None

    # warehouse id (for the lazy-loaded peers table)
    wh = soup.find(attrs={"data-warehouse-id": True})
    meta["warehouse_id"] = wh["data-warehouse-id"] if wh else None

    # company id (for the chart endpoint)
    comp = soup.find(attrs={"data-company-id": True})
    meta["company_id"] = comp["data-company-id"] if comp else None
    return meta


def parse_chart_data(chart_json: dict) -> list[dict]:
    """Normalize the chart endpoint's datasets into price-point rows.

    Returns rows of {point_date, series, close, volume, delivery_pct} where
    series ∈ {price, dma50, dma200, volume}.
    """
    series_map = {"Price": "price", "DMA50": "dma50", "DMA200": "dma200", "Volume": "volume"}
    rows: list[dict] = []
    for ds in chart_json.get("datasets") or []:
        series = series_map.get(ds.get("metric"))
        if series is None:
            continue
        for val in ds.get("values") or []:
            if not val or len(val) < 2:
                continue
            point_date, v = val[0], val[1]
            row: dict = {"point_date": point_date, "series": series,
                         "close": None, "volume": None, "delivery_pct": None}
            if series == "volume":
                try:
                    row["volume"] = int(v)
                except (TypeError, ValueError):
                    continue
                meta = val[2] if len(val) > 2 else {}
                if isinstance(meta, dict) and "delivery" in meta:
                    row["delivery_pct"] = float(meta["delivery"])
            else:
                try:
                    row["close"] = float(v)
                except (TypeError, ValueError):
                    continue
            rows.append(row)
    return rows


def parse_top_ratios(soup: BeautifulSoup) -> dict[str, float | None]:
    """Header metrics from ul#top-ratios."""
    out: dict[str, float | None] = {}
    ul = soup.find("ul", id="top-ratios")
    if ul is None:
        return out
    key_map = {
        "market cap": "market_cap_cr",
        "current price": "current_price",
        "high / low": "high_low",
        "stock p/e": "stock_pe",
        "book value": "book_value",
        "dividend yield": "dividend_yield",
        "roce": "roce_pct",
        "roe": "roe_pct",
        "face value": "face_value",
    }
    for li in ul.find_all("li"):
        name_el = li.select_one("span.name")
        val_el = li.select_one("span.value") or li.select_one("span.nowrap")
        if name_el is None or val_el is None:
            continue
        key = key_map.get(clean_text(name_el).lower())
        if key is None:
            continue
        if key == "high_low":
            nums = val_el.find_all("span", class_="number")
            out["high_52w"] = to_number(nums[0]) if len(nums) > 0 else None
            out["low_52w"] = to_number(nums[1]) if len(nums) > 1 else None
        else:
            num = val_el.select_one("span.number")
            out[key] = to_number(num) if num else None
    return out


# ------------------------------------------------- generic statement tables

def parse_statement_table(table: Tag) -> dict:
    """Parse one screener data-table into {periods: [...], rows: [{label, values}]}.

    Period keys come from th[data-date-key]; missing dates fall back to
    the header text (e.g. 'TTM', 'Mar 2026').
    """
    periods: list[str | None] = []
    head_row = table.find("thead")
    if head_row:
        for th in head_row.find_all("th"):
            dk = th.get("data-date-key")
            periods.append(_period_iso(dk) if dk else (clean_text(th) or None))

    rows: list[dict] = []
    body = table.find("tbody")
    if body is None:
        return {"periods": periods, "rows": rows}
    for tr in body.find_all("tr"):
        cells = tr.find_all(["td", "th"])
        if not cells:
            continue
        label = re.sub(r"\s*[\u00a0+]\s*$", "", clean_text(cells[0]))
        label = label.replace("+", "").strip()
        if not label:
            continue
        values = [to_number(c) for c in cells[1:]]
        if _is_junk_row(label, values):
            continue
        rows.append({"label": label, "values": values})
    return {"periods": periods, "rows": rows}


SECTION_IDS = (
    "quarters",
    "profit-loss",
    "balance-sheet",
    "cash-flow",
    "ratios",
)

# Non-data rows that appear inside screener tables (PDF/excel links, blank spacers)
_JUNK_LABELS = {"raw pdf", "raw page", "raw consolidated pdf", "raw standalone pdf",
                "raw financial data excel", "financial data excel", ""}


def _is_junk_row(label: str, values: list) -> bool:
    lab = label.strip().lower()
    if lab in _JUNK_LABELS or lab.startswith("raw "):
        return True
    return all(v is None for v in values)


def parse_financial_sections(soup: BeautifulSoup) -> dict[str, dict]:
    """Parse each financial section's main data-table."""
    out: dict[str, dict] = {}
    for sec_id in SECTION_IDS:
        sec = soup.find("section", id=sec_id)
        if sec is None:
            LOGGER.warning("Section #%s not found in page", sec_id)
            continue
        table = sec.find("table", class_=lambda c: c and "data-table" in c.split())
        if table is None:
            LOGGER.warning("No data-table inside #%s", sec_id)
            continue
        out[sec_id] = parse_statement_table(table)
    return out


def parse_growth_tables(soup: BeautifulSoup) -> list[dict]:
    """Compounded Sales/Profit growth, Stock Price CAGR, ROE — ranges tables."""
    results: list[dict] = []
    pl = soup.find("section", id="profit-loss")
    if pl is None:
        return results
    current_metric: str | None = None
    for el in pl.find_all(["h2", "table"], recursive=True):
        if el.name == "h2":
            txt = clean_text(el)
            if "growth" in txt.lower() or "cagr" in txt.lower() or "return on equity" in txt.lower():
                current_metric = txt
            continue
        classes = el.get("class") or []
        if "ranges-table" not in classes or current_metric is None:
            continue
        window = None
        value = None
        for tr in el.find_all("tr"):
            th, td = tr.find("th"), tr.find("td")
            if th is None or td is None:
                continue
            t = clean_text(th)
            if t.lower().startswith("compounded") or "cagr" in t.lower() or t == "ROE":
                window, value = t, to_number(td)
        if window and value is not None:
            metric_key = current_metric.split("\n")[0].strip()
            results.append({"metric": metric_key, "window": window, "value_pct": value})
    return results


def parse_shareholding(soup: BeautifulSoup) -> dict[str, dict]:
    """Two tables inside #shareholding: quarterly and yearly (% values)."""
    sec = soup.find("section", id="shareholding")
    out: dict[str, dict] = {}
    if sec is None:
        return out
    tables = sec.find_all("table")
    names = ["shareholding_quarterly", "shareholding_annual"]
    for name, table in zip(names, tables):
        parsed = parse_statement_table(table)
        # convert labels like 'Promoters +' -> 'Promoters'
        for row in parsed["rows"]:
            row["label"] = re.sub(r"\s*\+\s*$", "", row["label"])
        out[name] = parsed
    return out


def parse_documents(soup: BeautifulSoup) -> list[dict]:
    """BSE announcements + annual report links from #documents."""
    sec = soup.find("section", id="documents")
    docs: list[dict] = []
    if sec is None:
        return docs
    seen: set[str] = set()
    for a in sec.find_all("a", href=True):
        href = a["href"]
        if "bseindia.com" not in href and "nseindia.com" not in href:
            continue
        if href in seen:
            continue
        seen.add(href)
        text = clean_text(a)
        if not text:
            continue
        doc_type = "annual_report" if "annual report" in text.lower() else "announcement"
        docs.append({"title": text, "url": href, "doc_type": doc_type})
    return docs


def parse_peers_table(html: str) -> list[dict]:
    """Parse the AJAX peers response (a bare <table>)."""
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table")
    if table is None:
        return []
    headers = [clean_text(th) for th in table.find_all("th")]
    col_map = {}
    for i, h in enumerate(headers):
        hl = h.lower()
        if "name" in hl:
            col_map["name"] = i
        elif "cmp" in hl:
            col_map["cmp_price"] = i
        elif hl.startswith("p/e"):
            col_map["pe"] = i
        elif "mar cap" in hl:
            col_map["market_cap_cr"] = i
        elif "div yld" in hl:
            col_map["div_yield_pct"] = i
        elif "np qtr" in hl:
            col_map["np_qtr_cr"] = i
        elif "sales qtr" in hl:
            col_map["sales_qtr_cr"] = i
        elif "roce" in hl:
            col_map["roce_pct"] = i

    peers: list[dict] = []
    body = table.find("tbody")
    if body is None:
        return peers
    for tr in body.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 3:
            continue
        peer: dict = {}
        name_cell = cells[col_map["name"]] if "name" in col_map else None
        link = name_cell.find("a") if name_cell else None
        peer["peer_name"] = clean_text(name_cell)
        href = link.get("href", "") if link else ""
        m = re.search(r"/company/([^/]+)/", href)
        peer["peer_slug"] = m.group(1) if m else None
        for field, idx in col_map.items():
            if field in ("name",):
                continue
            peer[field] = to_number(cells[idx]) if idx < len(cells) else None
        peers.append(peer)
    return peers


def parse_company_page(html: str) -> dict:
    """Parse a full company page HTML into one normalized payload."""
    soup = BeautifulSoup(html, "lxml")
    payload: dict = {}
    payload.update(parse_company_meta(soup))
    payload["top_ratios"] = parse_top_ratios(soup)
    payload["financials"] = parse_financial_sections(soup)
    payload["growth"] = parse_growth_tables(soup)
    payload["shareholding"] = parse_shareholding(soup)
    payload["documents"] = parse_documents(soup)
    return payload
