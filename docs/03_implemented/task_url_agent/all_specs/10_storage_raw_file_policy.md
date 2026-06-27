# 10 — Storage and Raw File Policy

## User Constraint

The user has limited disk space and does not want to permanently store all raw files by default.

## Default Policy

Default behavior:

1. Download raw files into a run-specific temp directory.
2. Compute checksum and file metadata.
3. Parse the file.
4. Store structured records and provenance in PostgreSQL.
5. Delete raw file after successful parse unless `--keep-raw-files true`.
6. Retain only small debug artifacts and metadata.

## Failed Parse Policy

If parsing fails:

- keep raw file only if size is below configured threshold,
- otherwise store source URL, checksum if available, MIME type, file size, failure reason, and enough metadata to re-download.

Suggested config:

```text
--keep-raw-files false
--keep-failed-raw-files true
--max-retained-file-size-mb 50
--raw-dir data/raw/mutual_funds/runtime
--temp-dir data/tmp/mutual_funds/runtime
```

## Artifact Metadata

Always store:

- source URL,
- discovered-from URL,
- run ID,
- fetch timestamp,
- content type,
- file type,
- file size,
- checksum where possible,
- local path if retained,
- retained flag,
- parser status,
- error reason if failed.

## Deduplication

Use checksum-based deduplication for files.

If the same file appears from multiple URLs, preserve all source URLs but avoid duplicate parsing when checksum matches.

## Temporary Directory Cleanup

At run end:

- delete successful temp files,
- keep retained failed files according to policy,
- keep logs/debug artifacts according to config,
- store cleanup summary in ingestion run metadata.
