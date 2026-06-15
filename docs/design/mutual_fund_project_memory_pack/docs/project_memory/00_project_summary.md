# Project Summary

## What This Project Is

This project is an Indian mutual fund disclosure ingestion and analytics system.

It is intended to collect public investor documents from Indian mutual fund provider websites, structure the data, validate it, and store it in PostgreSQL for downstream financial transparency analytics.

The project is also a learning vehicle for Agentic AI. The data problem is intentionally real and messy: many AMC websites, different document structures, dynamic pages, PDFs, Excel files, inconsistent formats, and incomplete metadata.

## Primary User Goal

The user wants to learn and build agentic AI by creating a practical system that:

1. discovers mutual fund provider documents,
2. downloads raw public disclosures,
3. parses them into structured holdings data,
4. validates the data,
5. stores it in PostgreSQL,
6. enables analytics and agentic reasoning over the database.

## Why This Is Valuable

Indian mutual funds disclose holdings publicly, but the data is scattered across AMC websites and is not easy to aggregate.

Useful insights include consensus stocks across fund managers, stocks being accumulated or exited across AMCs, fund overlap and hidden concentration, sector exposure shifts, and fund-level diversification.

The public-good framing is financial transparency, not investment advice.

## Important Distinction

The project is not a stock recommendation engine, investment advice product, chatbot over NAV data, single AMFI scraper, or one-off download script.

The project is a reproducible provider-first ingestion system, structured financial data pipeline, and future agentic analytics platform.

## Key Decision

Use AMC/provider websites as the primary source.

AMFI is unreliable/dicey as the main ingestion dependency and should only be used as a reference or secondary index.

## Expected Long-Term Outcome

Eventually the user should be able to run one command that loads known provider profiles, checks which AMC sites still work, discovers new monthly disclosure documents, downloads new raw files, classifies document types, parses supported files, validates rows, loads trusted data into PostgreSQL, produces QA reports, and exposes analytics tools/agent queries.
