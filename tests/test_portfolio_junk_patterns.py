"""Task A6 — unit tests for extended JUNK_ROW_PATTERNS in parser/portfolio.py.

Covers the observed canonical-data leaks purged by scripts/purge_junk_holdings.py,
plus guards that legitimate security names are NOT flagged as junk.
"""
import pytest

from mutual_fund_ingestion.agent.parser.portfolio import _is_section_header


class TestTaskA6JunkPatterns:
    """Observed leaks that must now be classified as section headers / junk."""

    @pytest.mark.parametrize("name", [
        "Total",
        "  Total  ",
        "Sub Total",
        "Grand Total",
        "Net Current Assets",
        "Net Current Asset",
        "Total Net Assets",
        "TREPS",
        "TREPS / Reverse Repo Investments",
        "TREPS / Reverse Repo Investment",
        "TREPS / Reverse Repo Investments / Corporate Debt Repo",
        "treps-17012022",
        "Commercial Papers",
        "Commercial Paper",
        "Government Securities",
        "Government Securities (Central/State)",
        "Certificate of Deposits",
        "Cash & Cash Equivalent",          # singular variant
        "Cash & Cash Equivalents",         # pre-existing plural pattern
        "Grand Total (AUM)",
        "Bond & NCD's",
        "Equity & Equity Related",
        "Equity & Equity Related Foreign Investments",
        "Market Value Includes Accrued Interest",
        "Scheme Name:",
        "As on (Date)",
        "Scheme Riskometer",
        "Macaulay Duration",
        "Residual Maturity",
        "Description (if any)",
        "Annualised Portfolio YTM*:",
        "Benchmark Riskometer: CRISIL Liquid Overnight Index",
        "SBI Funds Management Pvt Ltd/Fund Parent",
        "Notes:",
        "Notes & symbols :-",
        "~ yield to maturity (ytm) as on October 31, 2024",
        "* In case of semi-annual YTM, it will be annualised",
        "** Non Traded in accordance with SEBI Regulations.",
        "(2)  total value and percentage of illiquid equity shares: nil.",
        "1.  total value provided for securities classified as below investment grade or default and its percentage to nav - nil",
        "^ pursuant to AMFI circular no. 135/bp/91/2020-21, yield to call (YTC) ...",
        "as on March 31, 2025, the aggregate investments by the schemes of DSP Mutual Fund in DSP Savings Fund is Rs. 100 lakhs.",
    ])
    def test_junk_names_flagged(self, name):
        assert _is_section_header(name) is True, f"expected junk: {name!r}"

    @pytest.mark.parametrize("name", [
        # Real securities that must never be excluded
        "Clearing Corporation of India Ltd",   # real TREPS counterparty w/ ISIN
        "Adani Total Gas Limited",             # contains 'total' but is a company
        "HDFC Bank Limited**",
        "7.38% GOI 2027",
        "364 DAYS T-BILL 2025",
        "IL&FS Energy Development Company Limited (Maturity Date : 07-Jun-2019)",
        "Alternative Investment Funds (AIF)",  # ambiguous genuine holding category
        "Mutual Fund Units",
        None,
        "",
    ])
    def test_real_names_kept(self, name):
        assert _is_section_header(name) is False, f"expected NOT junk: {name!r}"
