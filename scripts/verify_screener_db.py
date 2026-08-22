"""Verify DB contents for the 10-stock ingestion run."""

import os
import sys

import psycopg2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from screener_ingestion import parse  # noqa: F401  (ensures package importable)
from db_config import screener_url  # noqa: E402

conn = psycopg2.connect(screener_url())
cur = conn.cursor()

print("== stocks ==")
cur.execute("""
    SELECT s.slug, s.name, s.sector, s.warehouse_id,
           (SELECT COUNT(*) FROM financial_periods fp WHERE fp.stock_id=s.id) AS periods,
           (SELECT COUNT(*) FROM financial_line_items li
              JOIN financial_periods fp ON fp.id=li.period_id WHERE fp.stock_id=s.id) AS items,
           (SELECT COUNT(*) FROM peer_rows pr WHERE pr.stock_id=s.id) AS peers,
           (SELECT COUNT(*) FROM documents d WHERE d.stock_id=s.id) AS docs,
           (SELECT COUNT(*) FROM stock_snapshots ss WHERE ss.stock_id=s.id) AS snaps
    FROM stocks s ORDER BY s.slug
""")
print(f"{'slug':<12}{'name':<32}{'sector':<28}{'periods':>8}{'items':>7}{'peers':>7}{'docs':>6}{'snaps':>7}")
for r in cur.fetchall():
    print(f"{r[0]:<12}{(r[1] or '')[:30]:<32}{(r[2] or '')[:26]:<28}{r[4]:>8}{r[5]:>7}{r[6]:>7}{r[7]:>6}{r[8]:>7}")

print("\n== ingestion runs ==")
cur.execute("SELECT stock_slug, status, COUNT(*) FROM ingestion_runs GROUP BY 1,2 ORDER BY 1")
for r in cur.fetchall():
    print(f"  {r[0]:<12} {r[1]:<8} x{r[2]}")

print("\n== spot-check: HAL quarters Sales, latest 3 periods ==")
cur.execute("""
    SELECT fp.period_key, li.value FROM financial_line_items li
    JOIN financial_periods fp ON fp.id = li.period_id
    JOIN stocks s ON s.id = fp.stock_id
    WHERE s.slug='HAL' AND fp.statement_type='quarters' AND li.line_item='Sales'
    ORDER BY fp.period_key DESC LIMIT 3
""")
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]}")

print("\n== spot-check: HAL shareholding quarterly Promoters, latest 3 ==")
cur.execute("""
    SELECT fp.period_key, li.value FROM financial_line_items li
    JOIN financial_periods fp ON fp.id = li.period_id
    JOIN stocks s ON s.id = fp.stock_id
    WHERE s.slug='HAL' AND fp.statement_type='shareholding_quarterly' AND li.line_item='Promoters'
    ORDER BY fp.period_key DESC LIMIT 3
""")
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]}%")

print("\n== spot-check: HAL peers ==")
cur.execute("""
    SELECT pr.peer_name, pr.cmp_price, pr.pe, pr.market_cap_cr FROM peer_rows pr
    JOIN stocks s ON s.id = pr.stock_id WHERE s.slug='HAL' ORDER BY pr.market_cap_cr DESC
""")
for r in cur.fetchall():
    print(f"  {r[0]:<22} CMP={r[1]} P/E={r[2]} MCap={r[3]}")

cur.execute("SELECT COUNT(*) FROM documents WHERE doc_type='annual_report'")
print(f"\nannual_report docs total: {cur.fetchone()[0]}")
conn.close()
