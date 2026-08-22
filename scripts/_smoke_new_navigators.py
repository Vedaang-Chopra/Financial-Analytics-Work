"""Smoke test: run each new navigator and print URL counts."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mutual_fund_ingestion.agent.portfolio_navigators import (
    get_sbi_portfolio_urls,
    get_hdfc_portfolio_urls,
    get_nippon_india_portfolio_urls,
    get_uti_portfolio_urls,
    get_franklin_templeton_portfolio_urls,
)

for name, fn in [
    ("sbi", get_sbi_portfolio_urls),
    ("hdfc", get_hdfc_portfolio_urls),
    ("nippon_india", get_nippon_india_portfolio_urls),
    ("uti", get_uti_portfolio_urls),
    ("franklin_templeton", get_franklin_templeton_portfolio_urls),
]:
    try:
        urls = fn()
        print(f"{name}: {len(urls)} urls")
        for u in sorted(urls)[:3]:
            print("   ", u[:140])
        if not urls:
            print("    !! EMPTY")
    except Exception as exc:
        import traceback

        print(f"{name}: EXC {type(exc).__name__}: {exc}")
        traceback.print_exc()
