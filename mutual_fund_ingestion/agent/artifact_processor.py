"""Artifact processor — downloads, parses, validates, and upserts files."""
from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path
from typing import Any

from .db import (
    DatasetCandidate,
    QuarantineRow,
    RawArtifact,
    StagingRow,
)
from .parser import parse_file
from .validate import validate_and_filter_records


LOGGER = logging.getLogger(__name__)


class ArtifactProcessor:
    """Handles downloading, parsing, validating, and upserting a single artifact.

    Extracted from ``runner.py`` per ``docs/04_in_progress/REFACTOR_runner.md``.
    The caller (runner) passes in its own session — this function writes to it
    but never commits or closes it.
    """

    def __init__(
        self,
        run_id: str,
        stats: dict[str, Any],
        collector: Any,
        upsert_manager: Any,
        temp_dir: Path | None = None,
    ) -> None:
        self.run_id = run_id
        self.stats = stats
        self.collector = collector
        self.upsert_manager = upsert_manager
        self.temp_dir = temp_dir

    def process(self, session: Any, dataset_candidate: DatasetCandidate, raw_dir: Path | None = None) -> None:
        """Download file, parse, validate, and load to canonical tables.

        The ``session`` is owned and committed by the caller (the runner).
        This function only writes to it — it never commits or closes.
        """
        url = dataset_candidate.url
        LOGGER.info("Processing artifact: %s", url)

        # Download
        artifact_result = self.collector.download(url, self.run_id)

        if "error" in artifact_result:
            LOGGER.warning("Download failed for %s: %s", url, artifact_result.get("error"))
            dataset_candidate.status = "download_failed"  # type: ignore[assignment]
            self._add_retry_task(session, url, "download", artifact_result.get("reason", "download failed"), True)
            self.stats["retry_tasks"] = self.stats.get("retry_tasks", 0) + 1
            return

        self.stats["files_downloaded"] = self.stats.get("files_downloaded", 0) + 1
        LOGGER.info(
            "Downloaded %s: %d bytes sha256=%s",
            url,
            artifact_result.get("size_bytes", 0),
            (artifact_result.get("checksum", "") or "")[:12],
        )

        # Persist raw artifact record
        raw_artifact = RawArtifact(
            run_id=uuid.UUID(self.run_id),
            dataset_candidate_id=dataset_candidate.id,
            source_url=url,
            artifact_type="file",
            file_type=artifact_result.get("file_type"),
            content_type=artifact_result.get("content_type"),
            checksum=artifact_result.get("checksum"),
            size_bytes=artifact_result.get("size_bytes"),
            local_path=artifact_result.get("local_path"),
            retained=artifact_result.get("retained", False),
        )
        session.add(raw_artifact)
        session.flush()

        # L001: retain raw file to data/raw/ if configured
        if artifact_result.get("retained") and raw_dir:
            raw_dir.mkdir(parents=True, exist_ok=True)
            src = Path(artifact_result["local_path"])
            dest = raw_dir / src.name
            shutil.copy2(src, dest)
            raw_artifact.local_path = str(dest)
            LOGGER.info("Retained raw file at %s", dest)

        dataset_candidate.status = "downloaded"

        # Read file content
        content = None
        if artifact_result.get("local_path"):
            try:
                with open(artifact_result["local_path"], "rb") as f:
                    content = f.read()
            except Exception as exc:
                LOGGER.warning("Failed to read downloaded file %s: %s", artifact_result["local_path"], exc)
                self._add_retry_task(session, url, "parse", f"File read error: {exc}", True)
                dataset_candidate.status = "parse_failed"
                self.stats["retry_tasks"] = self.stats.get("retry_tasks", 0) + 1
                return

        if content is None:
            LOGGER.warning("No content for %s", url)
            return

        # Parse
        metadata = {"source_url": url, "raw_artifact_id": str(raw_artifact.id)}
        LOGGER.info(
            "Routing to parser for dataset_type=%s file_type=%s",
            dataset_candidate.dataset_type,
            dataset_candidate.file_type,
        )
        parser_result = parse_file(
            dataset_type=dataset_candidate.dataset_type,
            file_type=dataset_candidate.file_type,
            content=content,
            metadata=metadata,
        )

        LOGGER.info(
            "Parser %s returned %d records from %s (confidence=%.2f)",
            parser_result.parser_name,
            len(parser_result.records),
            url,
            parser_result.confidence,
        )
        if parser_result.errors:
            LOGGER.warning("Parser errors for %s: %s", url, "; ".join(parser_result.errors))

        if parser_result.confidence == 0.0:
            LOGGER.warning(
                "No parser for dataset_type=%s file_type=%s",
                dataset_candidate.dataset_type,
                dataset_candidate.file_type,
            )
            dataset_candidate.status = "no_parser"
            return

        self.stats["artifacts_parsed"] = self.stats.get("artifacts_parsed", 0) + 1

        # Stage all parsed records
        for i, record in enumerate(parser_result.records):
            staging_row = StagingRow(
                run_id=uuid.UUID(self.run_id),
                raw_artifact_id=raw_artifact.id,
                dataset_type=dataset_candidate.dataset_type,
                sheet_name=record.get("sheet_name"),
                row_number=i + 1,
                raw_row_json=record,
                parsed_fields_json=record,
                parser_name=parser_result.parser_name,
                parser_confidence=parser_result.confidence,
            )
            session.add(staging_row)

        self.stats["rows_staged"] = self.stats.get("rows_staged", 0) + len(parser_result.records)
        session.flush()

        # Validate and filter
        valid_records, quarantined_records, snapshot_warnings = validate_and_filter_records(
            parser_result, self.run_id, return_warnings=True
        )

        LOGGER.info(
            "Validation for %s: %d valid, %d quarantined, %d snapshot warnings",
            url,
            len(valid_records),
            len(quarantined_records),
            len(snapshot_warnings),
        )

        # Write validation results + quarantine rows
        for i, record in enumerate(parser_result.records):
            if i < len(valid_records):
                self.upsert_manager.write_validation_result(
                    session,
                    entity_type=dataset_candidate.dataset_type,
                    check_name="schema_validation",
                    severity="info",
                    status="passed",
                    message="Record passed validation",
                )
            else:
                quarantined = quarantined_records[i - len(valid_records)] if quarantined_records else None
                if quarantined:
                    self.upsert_manager.write_validation_result(
                        session,
                        entity_type=dataset_candidate.dataset_type,
                        check_name="schema_validation",
                        severity="error",
                        status="failed",
                        message=quarantined.get("reason", "validation failed"),
                    )
                    qr = QuarantineRow(
                        run_id=uuid.UUID(self.run_id),
                        raw_artifact_id=raw_artifact.id,
                        dataset_type=dataset_candidate.dataset_type,
                        reason=quarantined.get("reason", "unknown"),
                        raw_data_json=quarantined.get("raw_data_json"),
                        parser_error=quarantined.get("parser_error"),
                        retryable=quarantined.get("retryable", False),
                    )
                    session.add(qr)
                    self.stats["rows_quarantined"] = self.stats.get("rows_quarantined", 0) + 1

        # Snapshot-level WARN gate (e.g. pct-to-NAV sums outside bounds):
        # never drops rows — logged to validation_results only.
        for warning in snapshot_warnings:
            self.upsert_manager.write_validation_result(
                session,
                entity_type=dataset_candidate.dataset_type,
                check_name=warning.get("check_name", "snapshot_pct_sum"),
                severity=warning.get("severity", "warn"),
                status=warning.get("status", "warning"),
                message=warning.get("message"),
            )
        if snapshot_warnings:
            self.stats["snapshot_warnings"] = (
                self.stats.get("snapshot_warnings", 0) + len(snapshot_warnings)
            )

        # Upsert valid records to canonical tables with provenance
        self.upsert_manager.upsert_canonical(
            session,
            valid_records,
            dataset_candidate.dataset_type,
            raw_artifact.id,
            url,
            self.stats,
            checksum=raw_artifact.checksum,
        )

        dataset_candidate.status = "processed"

    def _add_retry_task(
        self, session: Any, url: str, task_type: str, failure_reason: str, retryable: bool
    ) -> None:
        """Add a task to the retry queue."""
        from .db import RetryQueue

        LOGGER.warning("Retry queued for %s: %s", url, failure_reason)
        retry = RetryQueue(
            run_id=uuid.UUID(self.run_id),
            url=url,
            task_type=task_type,
            failure_reason=failure_reason,
            retry_count=0,
            status="pending",
            retryable=retryable,
        )
        session.add(retry)