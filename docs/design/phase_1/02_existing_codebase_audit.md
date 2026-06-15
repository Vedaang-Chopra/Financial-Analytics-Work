# Existing Codebase Audit Specification

## Purpose

Before implementing new ingestion code, inspect the existing repository and determine what can be reused.

The repository may already contain:

- previous AMFI crawler code
- provider crawler code
- Excel sheets in dataset folders
- parsing utilities
- download utilities
- PostgreSQL helpers
- CLI patterns
- logging configuration
- tests
- notebooks
- Codex-generated code from earlier attempts

The goal is not to start from scratch blindly. The goal is to reuse compatible parts and isolate or replace incompatible parts.

## Required Audit Before Phase 1 Implementation

Before implementing Phase 1 provider profiling, perform a codebase audit.

The audit must inspect:

```text
repository root
package/module structure
existing ingestion scripts
existing crawler/downloader code
dataset folders
Excel/PDF samples
parser utilities
database utilities
configuration files
tests
notebooks
requirements/pyproject/environment files
logging patterns
CLI entrypoints
```

## Audit Output

Create or update:

```text
docs/design/mutual_fund_ingestion/generated/existing_codebase_audit_report.md
```

If the `generated/` folder does not exist, create it.

The audit report must include:

```text
1. Repository structure summary
2. Relevant existing files
3. Reusable modules/functions
4. Code that should be modified
5. Code that should be avoided or deprecated
6. Existing data samples and how they can be used
7. Existing dependencies available
8. Missing dependencies
9. Suggested implementation location for Phase 1
10. Risks and unknowns
```

## Reuse Policy

Reuse code only if it is:

- simple
- readable
- compatible with the phase architecture
- not tightly coupled to obsolete assumptions
- easy to test
- unlikely to break existing workflows

If code is useful but messy, wrap it instead of rewriting the whole system.

If code is obsolete, do not delete it immediately. Mark it as deprecated in the audit report.

## Existing Dataset Handling

If dataset folders contain Excel, CSV, PDF, or ZIP samples, inspect them.

Record:

```text
file path
file type
likely AMC/source
likely document type
whether it can be used as a fixture
whether it is suitable for parser tests later
```

Do not parse these files in Phase 1 unless needed only for understanding existing code.

## Existing Parser Handling

If existing parsers are found, classify them as:

```text
reusable_now
reusable_later
needs_refactor
not_recommended
unknown
```

For Phase 1, parsers are not required. They may be useful for later phases.

## Existing Crawler Handling

If existing crawler code exists, evaluate:

```text
Does it support multiple AMC providers?
Does it rely only on AMFI?
Does it support Playwright?
Does it save metadata?
Does it produce debug artifacts?
Does it have tests?
Can it be reused for provider profiling?
```

## Existing PostgreSQL Handling

If database utilities exist, inspect them but do not implement database loading in Phase 1.

Record whether they are likely useful for later phases.

## Required Codex Behavior

Codex must not implement Phase 1 until it has produced the audit report.

The audit report should guide implementation choices.

If Codex cannot determine whether a module is reusable, it should mark it as `unknown` and avoid deep integration.

## Acceptance Criteria

The audit is complete when:

- an audit report exists
- the report identifies where Phase 1 code should live
- the report lists reusable and non-reusable code
- the report identifies existing sample data
- the report identifies missing dependencies
- implementation risks are documented
