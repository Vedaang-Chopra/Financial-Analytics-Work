"""Validation, quarantine, and retry queue."""
from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Literal, overload

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
    "invalid_isin",
    "low_parser_confidence",
    "blocked_or_unreachable",
    "browser_timeout",
    "vlm_unparseable_response",
    "download_failed",
    "file_too_large",
    "pdf_scanned_or_image_based",
    "unknown_schema",
]

# ISIN: 2 letters (country code) + 9 alphanumeric + 1 check digit
ISIN_PATTERN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")

# Snapshot-level pct-sum gate bounds (percentage_to_nav sum per snapshot group)
PCT_SUM_LOWER_BOUND = 85.0
PCT_SUM_UPPER_BOUND = 115.0


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
    isin = record.get("isin")
    if isin:
        # Reject non-empty ISIN values that do not match ISO 6166 format
        if not ISIN_PATTERN.match(str(isin).strip().upper()):
            errors.append("invalid_isin")
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


def check_snapshot_pct_sums(
    records: list[dict[str, Any]],
    lower_bound: float = PCT_SUM_LOWER_BOUND,
    upper_bound: float = PCT_SUM_UPPER_BOUND,
) -> list[dict[str, Any]]:
    """Snapshot-level gate: group records by (scheme, reporting_date) and flag
    groups whose percentage-to-NAV sum falls outside [lower_bound, upper_bound].

    This is a WARN-level check — it never drops rows. Returns one entry per
    flagged group:
        {"scheme", "reporting_date", "pct_sum", "n_records", "message"}
    """
    groups: dict[tuple[Any, Any], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        scheme = record.get("scheme_name") or record.get("scheme") or record.get("sheet_name")
        reporting_date = record.get("reporting_date")
        groups[(scheme, reporting_date)].append(record)

    warnings: list[dict[str, Any]] = []
    for (scheme, reporting_date), group_records in groups.items():
        pct_sum = 0.0
        has_any = False
        for r in group_records:
            pct = r.get("percentage_to_nav")
            if pct is None:
                continue
            try:
                pct_sum += float(pct)
                has_any = True
            except (ValueError, TypeError):
                continue
        if not has_any:
            continue
        if not (lower_bound <= pct_sum <= upper_bound):
            message = (
                f"snapshot_pct_sum out of range [{lower_bound}, {upper_bound}]: "
                f"scheme={scheme!r} reporting_date={reporting_date!r} "
                f"pct_sum={round(pct_sum, 4)} n_records={len(group_records)}"
            )
            warnings.append(
                {
                    "check_name": "snapshot_pct_sum",
                    "severity": "warn",
                    "status": "warning",
                    "scheme": scheme,
                    "reporting_date": reporting_date,
                    "pct_sum": round(pct_sum, 4),
                    "n_records": len(group_records),
                    "message": message,
                }
            )
            LOGGER.warning(message)
    return warnings


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


@overload
def validate_and_filter_records(
    parser_result: ParserResult,
    run_id: str,
    return_warnings: Literal[True],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]: ...


@overload
def validate_and_filter_records(
    parser_result: ParserResult,
    run_id: str,
    return_warnings: Literal[False] = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]: ...


def validate_and_filter_records(
    parser_result: ParserResult,
    run_id: str,
    return_warnings: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]] | tuple[
    list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]
]:
    """Validate and filter parsed records, separating valid from quarantined.

    Handles two validator signatures:
    - list[str]: existing validators (nav, portfolio) — truthy = has errors
    - tuple[bool, str]: new validators (scheme_master, amc) — bool=True means valid

    When ``return_warnings=True`` a third list of snapshot-level WARN entries
    (e.g. from ``check_snapshot_pct_sums``) is returned; these never drop rows
    and are meant to be logged to ``validation_results`` by the caller.
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

    snapshot_warnings: list[dict[str, Any]] = []
    if parser_result.dataset_type == "portfolio_disclosure":
        snapshot_warnings = check_snapshot_pct_sums(parser_result.records)

    if return_warnings:
        return valid_records, quarantined_records, snapshot_warnings
    return valid_records, quarantined_records
