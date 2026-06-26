from datetime import datetime
from typing import Any, List, Mapping, Optional, Sequence, TypedDict, Unpack, cast

from pydantic import ValidationError

from incident_ci.config import IncidentCIConfig
from incident_ci.constants import MAX_ISSUES_PER_FILE
from incident_ci.models import IncidentCardV1, Issue, SourceLocation, ValidationResult
from incident_ci.parser import FieldLineIndex, ParsedIncidentCard


class ValidationContextKwargs(TypedDict):
    """Keyword arguments for incident validation context."""

    config: IncidentCIConfig
    clock: datetime


def validate_parsed_card(
    parsed_card: ParsedIncidentCard,
    **context: Unpack[ValidationContextKwargs],
) -> ValidationResult:
    """Validate parsed incident card."""

    config = context["config"]
    clock = context["clock"]
    issues: List[Issue] = []

    try:
        card = IncidentCardV1.model_validate(parsed_card.payload, context={"clock": clock})
    except ValidationError as error:
        for pydantic_error in error.errors():
            issues.append(
                map_pydantic_error_to_issue(
                    error=pydantic_error,
                    file_path=parsed_card.file_path,
                    field_locations=parsed_card.field_locations,
                    fallback_location=parsed_card.card_location,
                ),
            )

        return ValidationResult(
            issues=issues[:MAX_ISSUES_PER_FILE],
            checked_files=[parsed_card.file_path],
        )

    if card.service not in config.allowed_services:
        location = _location_for_field(
            field_name="service",
            field_locations=parsed_card.field_locations,
            fallback_location=parsed_card.card_location,
        )
        issues.append(
            Issue(
                code="SERVICE_UNKNOWN",
                severity="error",
                message=f"Unknown service: {card.service}",
                file_path=parsed_card.file_path,
                field_path="incident_card.service",
                line_start=location.line_start,
                line_end=location.line_end,
            ),
        )

    return ValidationResult(issues=issues[:MAX_ISSUES_PER_FILE], checked_files=[parsed_card.file_path])


def map_pydantic_error_to_issue(
    error: Mapping[str, Any],
    file_path: str,
    field_locations: FieldLineIndex,
    fallback_location: SourceLocation,
) -> Issue:
    """Convert one Pydantic error to validation issue."""

    message = _error_message(error=error)
    field_name = _field_name_from_error(error=error, message=message)
    field_path = _field_path(field_name=field_name)
    location = _location_for_field(
        field_name=field_name,
        field_locations=field_locations,
        fallback_location=fallback_location,
    )
    return Issue(
        code=_issue_code(error=error, message=message),
        severity="error",
        message=message,
        file_path=file_path,
        field_path=field_path,
        line_start=location.line_start,
        line_end=location.line_end,
    )


def _error_message(error: Mapping[str, Any]) -> str:
    return str(error.get("msg", "Invalid incident card field"))


def _field_name_from_error(error: Mapping[str, Any], message: str) -> Optional[str]:
    loc = tuple(cast(Sequence[object], error.get("loc", ())))
    if len(loc) > 0:
        return str(loc[0])

    return _field_name_from_business_message(message=message)


def _field_name_from_business_message(message: str) -> Optional[str]:
    candidates = [
        "resolved_at",
        "mitigated_at",
        "detected_at",
        "mitigation",
        "root_cause",
        "commander",
        "impact",
        "logs",
    ]
    for candidate in candidates:
        if candidate in message:
            return candidate

    return None


def _field_path(field_name: Optional[str]) -> Optional[str]:
    if field_name is None:
        return None

    return f"incident_card.{field_name}"


def _location_for_field(
    field_name: Optional[str],
    field_locations: FieldLineIndex,
    fallback_location: SourceLocation,
) -> SourceLocation:
    if field_name is None:
        return fallback_location

    location = field_locations.get(field_name)
    if location is None:
        return fallback_location

    return location


def _issue_code(error: Mapping[str, Any], message: str) -> str:
    error_type = str(error.get("type", ""))
    if error_type.startswith("missing"):
        return "FIELD_REQUIRED"
    if error_type.startswith("string_too_short"):
        return "FIELD_TOO_SHORT"
    if error_type.startswith("string_too_long"):
        return "FIELD_TOO_LONG"
    if error_type.startswith("literal_error"):
        return "FIELD_INVALID_VALUE"
    if error_type.startswith("datetime_") or error_type == "timezone_aware":
        return "FIELD_INVALID_DATETIME"
    if error_type.startswith("extra_forbidden"):
        return "FIELD_UNKNOWN"
    if error_type.startswith("value_error"):
        if "detected_at" in message and "future" in message:
            return "DATETIME_IN_FUTURE"
        return "SCHEMA_INVALID"

    return "SCHEMA_INVALID"
