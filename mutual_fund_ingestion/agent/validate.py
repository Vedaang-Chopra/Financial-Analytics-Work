"""Validation, quarantine, and retry queue."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from .models import ParserResult

if TYPE_CHECKING:
    pass


LOGGER = logging.getLogger(__name__)


QUARANTINE_REASONS = [
    "unsupported_file_type",
    "unsupported_dataset_type",
    "parse_error",
    "missing_required_field",
    "invalid_date",
    "invalid_numeric_value",
    "low_parser_confidence",
    "blocked_or_unreachable",
    "browser_timeout",
    "vlm_unparseable_response",
    "download_failed",
    "file_too_large",
    "pdf_scanned_or_image_based",
    "unknown_schema",
]


def validate_nav_record(record: dict[str, Any]) -> list[str]:
    errors = []
    if not record.get("scheme_code"):
        errors.append("missing_scheme_code")
    if not record.get("nav_value"):
        errors.append("missing_nav_value")
    else:
        try:
            val = float(record["nav_value"])
            if val <= 0:
                errors.append("nav_value_not_positive")
        except (ValueError, TypeError):
            errors.append("nav_value_not_numeric")
    if not record.get("nav_date"):
        errors.append("missing_nav_date")
    if not record.get("source_url"):
        errors.append("missing_source_url")
    return errors


def validate_portfolio_record(record: dict[str, Any]) -> list[str]:
    errors = []
    if not record.get("security_name"):
        errors.append("missing_security_name")
    if record.get("percentage_to_nav") is not None:
        try:
            val = float(record["percentage_to_nav"])
            if val < 0 or val > 100:
                errors.append("percentage_out_of_range")
        except (ValueError, TypeError):
            errors.append("percentage_not_numeric")
    if record.get("market_value") is not None:
        try:
            float(record["market_value"])
        except (ValueError, TypeError):
            errors.append("market_value_not_numeric")
    return errors


def validate_scheme_master_record(record: dict[str, Any]) -> tuple[bool, str]:
    """Validate a scheme_master record.

    Returns (True, "") if valid, (False, "reason: <description>") if invalid.
    Checks required fields: scheme_code, scheme_name.
    Per TASK-G001 per docs/06_plans/active/BATCH_E_validation.md.
    """
    missing: list[str] = []
    if not record.get("scheme_code"):
        missing.append("scheme_code")
    if not record.get("scheme_name"):
        missing.append("scheme_name")
    if missing:
        return False, "missing_required_field: " + ", ".join(missing)
    return True, ""


def validate_amc_record(record: dict[str, Any]) -> tuple[bool, str]:
    """Validate an amc_provider_list record.

    Returns (True, "") if valid, (False, "reason: <description>") if invalid.
    Checks required fields: amc_code, amc_name, source_url.
    Per TASK-G002 per docs/06_plans/active/BATCH_E_validation.md.
    """
    missing: list[str] = []
    if not record.get("amc_code"):
        missing.append("amc_code")
    if not record.get("amc_name"):
        missing.append("amc_name")
    if not record.get("source_url"):
        missing.append("source_url")
    if missing:
        return False, "missing_required_field: " + ", ".join(missing)
    return True, ""


def write_quarantine_row(
    run_id: str,
    reason: str,
    raw_data: dict[str, Any] | None,
    parser_error: str | None,
    retryable: bool,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "reason": reason,
        "raw_data_json": raw_data,
        "parser_error": parser_error,
        "retryable": retryable,
    }


def write_validation_result(
    run_id: str,
    entity_type: str,
    entity_id: str | None,
    check_name: str,
    severity: str,
    status: str,
    message: str | None,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "check_name": check_name,
        "severity": severity,
        "status": status,
        "message": message,
    }


def write_retry_task(
    run_id: str,
    url: str,
    task_type: str,
    failure_reason: str,
    retryable: bool,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "url": url,
        "task_type": task_type,
        "failure_reason": failure_reason,
        "retryable": retryable,
        "status": "pending",
        "retry_count": 0,
    }


def validate_and_filter_records(
    parser_result: ParserResult, run_id: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Validate and filter parsed records, separating valid from quarantined.

    Handles two validator signatures:
    - list[str]: existing validators (nav, portfolio) — truthy = has errors
    - tuple[bool, str]: new validators (scheme_master, amc) — bool=True means valid
    """
    valid_records: list[dict[str, Any]] = []
    quarantined_records: list[dict[str, Any]] = []

    if parser_result.dataset_type == "nav_history":
        validate_fn = validate_nav_record
    elif parser_result.dataset_type == "portfolio_disclosure":
        validate_fn = validate_portfolio_record
    elif parser_result.dataset_type == "scheme_master":
        validate_fn = validate_scheme_master_record
    elif parser_result.dataset_type == "amc_provider_list":
        validate_fn = validate_amc_record
    else:
        validate_fn = lambda r: ["unknown_dataset_type"]

    for record in parser_result.records:
        result = validate_fn(record)
        if isinstance(result, tuple):
            # New-style validator: tuple[bool, str]
            is_valid, reason = result
            if is_valid:
                valid_records.append(record)
            else:
                quarantined_records.append(
                    write_quarantine_row(run_id, reason, record, None, False)
                )
        else:
            # Legacy-style validator: list[str] of errors
            errors: list[str] = result
            if errors:
                quarantined_records.append(
                    write_quarantine_row(run_id, "; ".join(errors), record, None, False)
                )
            else:
                valid_records.append(record)

    return valid_records, quarantined_records
