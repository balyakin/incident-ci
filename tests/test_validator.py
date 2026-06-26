from datetime import UTC, datetime
from pathlib import Path
from typing import Dict

from incident_ci.config import IncidentCIConfig, load_config
from incident_ci.models import ValidationResult
from incident_ci.parser import ParsedIncidentCard, parse_incident_file
from incident_ci.validator import (
    _field_name_from_business_message,
    _field_path,
    _location_for_field,
    validate_parsed_card,
)

FIXTURES_DIR = Path("tests/fixtures")
CLOCK = datetime(2026, 2, 1, 0, 0, 0, tzinfo=UTC)


def _config() -> IncidentCIConfig:
    return load_config(config_path=FIXTURES_DIR / ".incident-ci.yaml")


def _parsed_fixture(name: str) -> ParsedIncidentCard:
    return parse_incident_file(file_path=FIXTURES_DIR / name)


def _with_payload(parsed_card: ParsedIncidentCard, payload: Dict[str, object]) -> ParsedIncidentCard:
    return ParsedIncidentCard(
        file_path=parsed_card.file_path,
        payload=payload,
        card_location=parsed_card.card_location,
        field_locations=parsed_card.field_locations,
    )


def _validate_fixture(name: str) -> ValidationResult:
    parsed_card = _parsed_fixture(name=name)
    return validate_parsed_card(parsed_card, config=_config(), clock=CLOCK)


def test_validate_parsed_card_valid_detected() -> None:
    # ARRANGE / ACT
    result = _validate_fixture(name="valid_detected.md")

    # ASSERT
    assert result.is_valid is True
    assert result.issues == []


def test_validate_parsed_card_valid_mitigated() -> None:
    # ARRANGE / ACT
    result = _validate_fixture(name="valid_mitigated.md")

    # ASSERT
    assert result.is_valid is True
    assert result.issues == []


def test_validate_parsed_card_valid_resolved() -> None:
    # ARRANGE / ACT
    result = _validate_fixture(name="valid_resolved.md")

    # ASSERT
    assert result.is_valid is True
    assert result.issues == []


def test_validate_parsed_card_missing_title() -> None:
    # ARRANGE
    parsed_card = _parsed_fixture(name="valid_detected.md")
    payload = dict(parsed_card.payload)
    del payload["title"]

    # ACT
    result = validate_parsed_card(_with_payload(parsed_card, payload), config=_config(), clock=CLOCK)

    # ASSERT
    assert {issue.code for issue in result.issues} == {"FIELD_REQUIRED"}
    assert {issue.field_path for issue in result.issues} == {"incident_card.title"}


def test_validate_parsed_card_description_too_short() -> None:
    # ARRANGE
    parsed_card = _parsed_fixture(name="valid_detected.md")
    payload = dict(parsed_card.payload)
    payload["description"] = ""

    # ACT
    result = validate_parsed_card(_with_payload(parsed_card, payload), config=_config(), clock=CLOCK)

    # ASSERT
    assert {issue.code for issue in result.issues} == {"FIELD_TOO_SHORT"}


def test_validate_parsed_card_description_too_long() -> None:
    # ARRANGE
    parsed_card = _parsed_fixture(name="valid_detected.md")
    payload = dict(parsed_card.payload)
    payload["description"] = "x" * 5_001

    # ACT
    result = validate_parsed_card(_with_payload(parsed_card, payload), config=_config(), clock=CLOCK)

    # ASSERT
    assert {issue.code for issue in result.issues} == {"FIELD_TOO_LONG"}


def test_validate_parsed_card_invalid_id() -> None:
    # ARRANGE
    parsed_card = _parsed_fixture(name="valid_detected.md")
    payload = dict(parsed_card.payload)
    payload["id"] = "BAD-1"

    # ACT
    result = validate_parsed_card(_with_payload(parsed_card, payload), config=_config(), clock=CLOCK)

    # ASSERT
    assert {issue.code for issue in result.issues} == {"SCHEMA_INVALID"}
    assert {issue.field_path for issue in result.issues} == {"incident_card.id"}


def test_validate_parsed_card_invalid_status_literal() -> None:
    # ARRANGE
    parsed_card = _parsed_fixture(name="valid_detected.md")
    payload = dict(parsed_card.payload)
    payload["status"] = "closed"

    # ACT
    result = validate_parsed_card(_with_payload(parsed_card, payload), config=_config(), clock=CLOCK)

    # ASSERT
    assert {issue.code for issue in result.issues} == {"FIELD_INVALID_VALUE"}
    assert {issue.field_path for issue in result.issues} == {"incident_card.status"}


def test_validate_parsed_card_invalid_commander_format() -> None:
    # ARRANGE
    parsed_card = _parsed_fixture(name="valid_detected.md")
    payload = dict(parsed_card.payload)
    payload["commander"] = "alice"

    # ACT
    result = validate_parsed_card(_with_payload(parsed_card, payload), config=_config(), clock=CLOCK)

    # ASSERT
    assert {issue.field_path for issue in result.issues} == {"incident_card.commander"}


def test_validate_parsed_card_invalid_postmortem_link() -> None:
    # ARRANGE
    parsed_card = _parsed_fixture(name="valid_detected.md")
    payload = dict(parsed_card.payload)
    payload["postmortem_link"] = "not-a-url"

    # ACT
    result = validate_parsed_card(_with_payload(parsed_card, payload), config=_config(), clock=CLOCK)

    # ASSERT
    assert {issue.field_path for issue in result.issues} == {"incident_card.postmortem_link"}


def test_validate_parsed_card_unknown_service() -> None:
    # ARRANGE
    parsed_card = _parsed_fixture(name="valid_detected.md")
    payload = dict(parsed_card.payload)
    payload["service"] = "billing-api"

    # ACT
    result = validate_parsed_card(_with_payload(parsed_card, payload), config=_config(), clock=CLOCK)

    # ASSERT
    assert [issue.model_dump(mode="json") for issue in result.issues] == [
        {
            "code": "SERVICE_UNKNOWN",
            "severity": "error",
            "message": "Unknown service: billing-api",
            "file_path": "tests/fixtures/valid_detected.md",
            "field_path": "incident_card.service",
            "line_start": 11,
            "line_end": 11,
        }
    ]


def test_validate_parsed_card_timezone_naive_datetime() -> None:
    # ARRANGE
    parsed_card = _parsed_fixture(name="valid_detected.md")
    payload = dict(parsed_card.payload)
    payload["detected_at"] = "2026-01-15T08:10:00"

    # ACT
    result = validate_parsed_card(_with_payload(parsed_card, payload), config=_config(), clock=CLOCK)

    # ASSERT
    assert {issue.code for issue in result.issues} == {"FIELD_INVALID_DATETIME"}


def test_validate_parsed_card_future_datetime() -> None:
    # ARRANGE
    parsed_card = _parsed_fixture(name="valid_detected.md")
    payload = dict(parsed_card.payload)
    payload["detected_at"] = "2026-02-02T00:00:00Z"

    # ACT
    result = validate_parsed_card(_with_payload(parsed_card, payload), config=_config(), clock=CLOCK)

    # ASSERT
    assert {issue.code for issue in result.issues} == {"DATETIME_IN_FUTURE"}
    assert {issue.field_path for issue in result.issues} == {"incident_card.detected_at"}


def test_validate_parsed_card_wrong_chronology() -> None:
    # ARRANGE / ACT
    result = _validate_fixture(name="wrong_date_order.md")

    # ASSERT
    assert {issue.code for issue in result.issues} == {"SCHEMA_INVALID"}
    assert {issue.field_path for issue in result.issues} == {"incident_card.resolved_at"}


def test_validate_parsed_card_mitigated_before_detected() -> None:
    # ARRANGE
    parsed_card = _parsed_fixture(name="valid_mitigated.md")
    payload = dict(parsed_card.payload)
    payload["mitigated_at"] = "2026-01-16T08:00:00Z"

    # ACT
    result = validate_parsed_card(_with_payload(parsed_card, payload), config=_config(), clock=CLOCK)

    # ASSERT
    assert {issue.field_path for issue in result.issues} == {"incident_card.mitigated_at"}


def test_validate_parsed_card_resolved_before_mitigated() -> None:
    # ARRANGE
    parsed_card = _parsed_fixture(name="valid_resolved.md")
    payload = dict(parsed_card.payload)
    payload["resolved_at"] = "2026-01-17T08:30:00Z"

    # ACT
    result = validate_parsed_card(_with_payload(parsed_card, payload), config=_config(), clock=CLOCK)

    # ASSERT
    assert {issue.field_path for issue in result.issues} == {"incident_card.resolved_at"}


def test_validate_parsed_card_detected_with_resolved_at() -> None:
    # ARRANGE
    parsed_card = _parsed_fixture(name="valid_detected.md")
    payload = dict(parsed_card.payload)
    payload["resolved_at"] = "2026-01-15T09:00:00Z"

    # ACT
    result = validate_parsed_card(_with_payload(parsed_card, payload), config=_config(), clock=CLOCK)

    # ASSERT
    assert {issue.field_path for issue in result.issues} == {"incident_card.resolved_at"}


def test_validate_parsed_card_mitigated_without_mitigated_at() -> None:
    # ARRANGE
    parsed_card = _parsed_fixture(name="valid_mitigated.md")
    payload = dict(parsed_card.payload)
    payload["mitigated_at"] = None

    # ACT
    result = validate_parsed_card(_with_payload(parsed_card, payload), config=_config(), clock=CLOCK)

    # ASSERT
    assert {issue.field_path for issue in result.issues} == {"incident_card.mitigated_at"}


def test_validate_parsed_card_mitigated_without_mitigation() -> None:
    # ARRANGE
    parsed_card = _parsed_fixture(name="valid_mitigated.md")
    payload = dict(parsed_card.payload)
    payload["mitigation"] = None

    # ACT
    result = validate_parsed_card(_with_payload(parsed_card, payload), config=_config(), clock=CLOCK)

    # ASSERT
    assert {issue.field_path for issue in result.issues} == {"incident_card.mitigation"}


def test_validate_parsed_card_mitigated_with_resolved_at() -> None:
    # ARRANGE
    parsed_card = _parsed_fixture(name="valid_mitigated.md")
    payload = dict(parsed_card.payload)
    payload["resolved_at"] = "2026-01-16T09:00:00Z"

    # ACT
    result = validate_parsed_card(_with_payload(parsed_card, payload), config=_config(), clock=CLOCK)

    # ASSERT
    assert {issue.field_path for issue in result.issues} == {"incident_card.resolved_at"}


def test_validate_parsed_card_critical_without_logs() -> None:
    # ARRANGE
    parsed_card = _parsed_fixture(name="valid_resolved.md")
    payload = dict(parsed_card.payload)
    payload["logs"] = None

    # ACT
    result = validate_parsed_card(_with_payload(parsed_card, payload), config=_config(), clock=CLOCK)

    # ASSERT
    assert {issue.field_path for issue in result.issues} == {"incident_card.logs"}


def test_validate_parsed_card_high_without_commander() -> None:
    # ARRANGE
    parsed_card = _parsed_fixture(name="valid_detected.md")
    payload = dict(parsed_card.payload)
    payload["commander"] = None

    # ACT
    result = validate_parsed_card(_with_payload(parsed_card, payload), config=_config(), clock=CLOCK)

    # ASSERT
    assert {issue.field_path for issue in result.issues} == {"incident_card.commander"}


def test_validate_parsed_card_high_without_impact() -> None:
    # ARRANGE
    parsed_card = _parsed_fixture(name="valid_detected.md")
    payload = dict(parsed_card.payload)
    payload["impact"] = None

    # ACT
    result = validate_parsed_card(_with_payload(parsed_card, payload), config=_config(), clock=CLOCK)

    # ASSERT
    assert {issue.field_path for issue in result.issues} == {"incident_card.impact"}


def test_validate_parsed_card_resolved_without_root_cause() -> None:
    # ARRANGE
    parsed_card = _parsed_fixture(name="valid_resolved.md")
    payload = dict(parsed_card.payload)
    payload["root_cause"] = None

    # ACT
    result = validate_parsed_card(_with_payload(parsed_card, payload), config=_config(), clock=CLOCK)

    # ASSERT
    assert {issue.field_path for issue in result.issues} == {"incident_card.root_cause"}


def test_validate_parsed_card_resolved_without_resolved_at() -> None:
    # ARRANGE
    parsed_card = _parsed_fixture(name="valid_resolved.md")
    payload = dict(parsed_card.payload)
    payload["resolved_at"] = None

    # ACT
    result = validate_parsed_card(_with_payload(parsed_card, payload), config=_config(), clock=CLOCK)

    # ASSERT
    assert {issue.field_path for issue in result.issues} == {"incident_card.resolved_at"}


def test_validate_parsed_card_resolved_without_impact() -> None:
    # ARRANGE
    parsed_card = _parsed_fixture(name="valid_resolved.md")
    payload = dict(parsed_card.payload)
    payload["impact"] = None

    # ACT
    result = validate_parsed_card(_with_payload(parsed_card, payload), config=_config(), clock=CLOCK)

    # ASSERT
    assert {issue.field_path for issue in result.issues} == {"incident_card.impact"}


def test_validate_parsed_card_resolved_without_mitigation() -> None:
    # ARRANGE
    parsed_card = _parsed_fixture(name="valid_resolved.md")
    payload = dict(parsed_card.payload)
    payload["mitigation"] = None

    # ACT
    result = validate_parsed_card(_with_payload(parsed_card, payload), config=_config(), clock=CLOCK)

    # ASSERT
    assert {issue.field_path for issue in result.issues} == {"incident_card.mitigation"}


def test_validate_parsed_card_unknown_field() -> None:
    # ARRANGE
    parsed_card = _parsed_fixture(name="unknown_field.md")

    # ACT
    result = validate_parsed_card(parsed_card, config=_config(), clock=CLOCK)

    # ASSERT
    assert {issue.code for issue in result.issues} == {"FIELD_UNKNOWN"}
    assert {issue.line_start for issue in result.issues} == {22}


def test_validator_private_fallback_helpers() -> None:
    # ARRANGE
    fallback_location = _parsed_fixture(name="valid_detected.md").card_location

    # ACT
    unknown_field = _field_name_from_business_message(message="unmapped validation message")
    empty_path = _field_path(field_name=None)
    none_location = _location_for_field(
        field_name=None,
        field_locations={},
        fallback_location=fallback_location,
    )
    missing_location = _location_for_field(
        field_name="missing",
        field_locations={},
        fallback_location=fallback_location,
    )

    # ASSERT
    assert unknown_field is None
    assert empty_path is None
    assert none_location == fallback_location
    assert missing_location == fallback_location
