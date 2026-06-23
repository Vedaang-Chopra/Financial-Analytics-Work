# mutual_fund_ingestion/amfi_disclosure — Isolated Prototype

This module is a Phase 0 proof-of-concept for crawling the AMFI portfolio disclosure page.
It is fully functional but **not integrated** with the main ingestion agent pipeline.

## Status
- All 11 tests pass (tests/test_amfi_disclosure.py)
- Not imported by mutual_fund_ingestion/
- Do not extend this module — the agent handles portfolio disclosure via Epic P tasks

## Reference use only
The Playwright and HTTP download patterns here may be useful as reference.
Do not copy code from here into the agent without adapting to the agent's layer model.