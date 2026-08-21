# PHASE2_discovery_log

## D002 — Aditya Birla Sun Life Mutual Fund (dry-run)

**Command**

```bash
export DATABASE_URL='postgresql://vlmrouter:vlmrouter@localhost:5432/mutual_funds'
./financial_env/bin/python -m mutual_fund_ingestion run-agent \
  --task-url 'https://mutualfund.adityabirlacapital.com/forms-and-downloads/portfolio' \
  --database-url "$DATABASE_URL" \
  --max-pages 5 \
  --dry-run \
  --log-level INFO
```

**Run ID:** `2baa6263-7dc2-4ff5-a866-1afdadb26e07`

**Summary**

- pages visited: 5
- links discovered: 362
- dataset candidates: 5
- files downloaded: 1
- rows inserted: 0
- rows quarantined: 0
- retries: 0

**HTTP notes**

- Logged every GET before request.
- 2-second domain spacing applied between repeated `mutualfund.adityabirlacapital.com` requests.
- No 429 responses observed.

**Key output**

```text
Run 2baa6263-7dc2-4ff5-a866-1afdadb26e07 complete: pages=5 links=362 candidates=5 files=1 staged=0 inserted=0 quarantined=0 retries=0
```

## D003 — ICICI Prudential Mutual Fund (dry-run)

**Command**

```bash
export DATABASE_URL='postgresql://vlmrouter:vlmrouter@localhost:5432/mutual_funds'
./financial_env/bin/python -m mutual_fund_ingestion run-agent \
  --task-url 'https://www.icicipruamc.com/media-center/downloads?currentTabFilter=OtherSchemeDisclosures&&subCatTabFilter=FortnightlyPortfolioDisclosures' \
  --database-url "$DATABASE_URL" \
  --max-pages 5 \
  --dry-run \
  --log-level INFO
```

**Run ID:** `a154fff1-2ba0-4bcf-bf27-da570a27695a`

**Summary**

- pages visited: 1
- links discovered: 0
- dataset candidates: 1
- files downloaded: 0
- rows inserted: 0
- rows quarantined: 0
- retries: 1

**HTTP notes**

- Logged GET before request.
- No repeated same-domain requests after the initial 404.
- No 429 responses observed.

**Key output**

```text
Run a154fff1-2ba0-4bcf-bf27-da570a27695a complete: pages=1 links=0 candidates=1 files=0 staged=0 inserted=0 quarantined=0 retries=1
```

## D003 — PPFAS Mutual Fund (dry-run)

**Command**

```bash
export DATABASE_URL='postgresql://vlmrouter:vlmrouter@localhost:5432/mutual_funds'
./financial_env/bin/python -m mutual_fund_ingestion run-agent \
  --task-url 'https://amc.ppfas.com/downloads/' \
  --database-url "$DATABASE_URL" \
  --max-pages 5 \
  --dry-run \
  --log-level INFO
```

**Run ID:** `3d4c208b-addb-4b73-89a8-9066311e9cfb`

**Summary**

- pages visited: 5
- links discovered: 626
- dataset candidates: 5
- files downloaded: 21
- rows inserted: 0
- rows quarantined: 0
- retries: 7

**HTTP notes**

- Logged every GET before request.
- 2-second domain spacing applied within `amc.ppfas.com`.
- No 429 responses observed.

**Key output**

```text
Run 3d4c208b-addb-4b73-89a8-9066311e9cfb complete: pages=5 links=626 candidates=5 files=21 staged=0 inserted=0 quarantined=0 retries=7
```

## D004 — Aditya Birla Sun Life Mutual Fund (live limited run)

**Command**

```bash
export DATABASE_URL='postgresql://vlmrouter:vlmrouter@localhost:5432/mutual_funds'
./financial_env/bin/python -m mutual_fund_ingestion run-agent \
  --task-url 'https://mutualfund.adityabirlacapital.com/forms-and-downloads/portfolio' \
  --database-url "$DATABASE_URL" \
  --max-pages 10 \
  --max-files 3 \
  --log-level INFO
```

**Run ID:** `fd1040ef-2ede-4433-94e5-7f282ec3e392`

**Summary**

- pages visited: 10
- links discovered: 667
- dataset candidates: 10
- files downloaded: 1
- rows inserted: 0
- rows quarantined: 0
- retries: 0

**HTTP notes**

- Logged every GET before request.
- 2-second domain spacing applied within `mutualfund.adityabirlacapital.com`.
- No 429 responses observed.

**Key output**

```text
Run fd1040ef-2ede-4433-94e5-7f282ec3e392 complete: pages=10 links=667 candidates=10 files=1 staged=0 inserted=0 quarantined=0 retries=0
```

## D005 — Inspect discovered candidates in DB

**Command**

```bash
export DATABASE_URL='postgresql://vlmrouter:vlmrouter@localhost:5432/mutual_funds'
./financial_env/bin/python -m mutual_fund_ingestion inspect-run \
  --database-url "$DATABASE_URL" \
  --run-id fd1040ef-2ede-4433-94e5-7f282ec3e392
```

**Summary**

- DatasetCandidate rows: 1
- Dataset types found: `portfolio_disclosure`

**Candidate URL**

- `https://portfoliomanagementservices.adityabirlacapital.com/pdf/Forms/Common-Empanelment-form-AIF-PMS_13062025.pdf`

**Key output**

```text
=== Dataset Candidates (1) ===
  https://portfoliomanagementservices.adityabirlacapital.com/pdf/Forms/Common-Empanelment-form-AIF-PMS_13062025.pdf - portfolio_disclosure - no_parser
```
