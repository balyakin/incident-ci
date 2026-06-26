from datetime import UTC, datetime
from typing import Dict

import pytest
from pydantic import ValidationError

from incident_ci.models import IncidentCardV1

CLOCK = datetime(2026, 2, 1, 0, 0, 0, tzinfo=UTC)


def _payload() -> Dict[str, object]:
    return {
        "schema_version": 1,
        "id": "INC-2026-150",
        "status": "detected",
        "title": "Payment API latency spike",
        "severity": "medium",
        "environment": "production",
        "service": "payment-api",
        "commander": None,
        "detected_at": "2026-01-15T08:10:00Z",
        "mitigated_at": None,
        "resolved_at": None,
        "description": "Payment API latency exceeded the SLO for checkout requests.",
        "impact": None,
        "mitigation": None,
        "root_cause": None,
        "postmortem_link": None,
        "logs": None,
    }


def test_incident_card_v1_uses_default_clock_without_context() -> None:
    # ARRANGE
    payload = _payload()

    # ACT
    card = IncidentCardV1.model_validate(payload)

    # ASSERT
    assert card.id == "INC-2026-150"


def test_incident_card_v1_future_without_context_raises_validation_error() -> None:
    # ARRANGE
    payload = _payload()
    payload["detected_at"] = datetime(2099, 1, 1, 0, 0, 0, tzinfo=UTC)

    # ACT / ASSERT
    with pytest.raises(ValidationError):
        IncidentCardV1.model_validate(payload)


def test_incident_card_v1_rejects_mitigated_before_detected() -> None:
    # ARRANGE
    payload = _payload()
    payload["status"] = "mitigated"
    payload["mitigated_at"] = "2026-01-15T08:00:00Z"
    payload["mitigation"] = "Traffic was shifted away from the affected payment shard."

    # ACT / ASSERT
    with pytest.raises(ValidationError, match="mitigated_at must be later than detected_at"):
        IncidentCardV1.model_validate(payload, context={"clock": CLOCK})


def test_incident_card_v1_rejects_mitigated_without_mitigation() -> None:
    # ARRANGE
    payload = _payload()
    payload["status"] = "mitigated"
    payload["mitigated_at"] = "2026-01-15T08:30:00Z"

    # ACT / ASSERT
    with pytest.raises(ValidationError, match="mitigation is required when status is mitigated"):
        IncidentCardV1.model_validate(payload, context={"clock": CLOCK})


def test_incident_card_v1_rejects_resolved_without_mitigated_at() -> None:
    # ARRANGE
    payload = _payload()
    payload["status"] = "resolved"
    payload["resolved_at"] = "2026-01-15T08:40:00Z"
    payload["impact"] = "Checkout requests were delayed for customers in the EU region."
    payload["mitigation"] = "Traffic was shifted away from the affected payment shard."
    payload["root_cause"] = "A queue worker deploy reduced payment event processing capacity."

    # ACT / ASSERT
    with pytest.raises(ValidationError, match="mitigated_at is required when status is resolved"):
        IncidentCardV1.model_validate(payload, context={"clock": CLOCK})


def test_incident_card_v1_rejects_high_without_commander() -> None:
    # ARRANGE
    payload = _payload()
    payload["severity"] = "high"
    payload["impact"] = "Checkout requests were delayed for customers in the EU region."

    # ACT / ASSERT
    with pytest.raises(ValidationError, match="commander is required for high and critical incidents"):
        IncidentCardV1.model_validate(payload, context={"clock": CLOCK})


def test_incident_card_v1_rejects_unknown_field() -> None:
    # ARRANGE
    payload = _payload()
    payload["unexpected"] = "value"

    # ACT / ASSERT
    with pytest.raises(ValidationError) as error_info:
        IncidentCardV1.model_validate(payload, context={"clock": CLOCK})

    assert error_info.value.errors()[0]["type"] == "extra_forbidden"


def test_incident_card_v1_rejects_invalid_id_pattern() -> None:
    # ARRANGE
    payload = _payload()
    payload["id"] = "BAD-1"

    # ACT / ASSERT
    with pytest.raises(ValidationError) as error_info:
        IncidentCardV1.model_validate(payload, context={"clock": CLOCK})

    assert error_info.value.errors()[0]["loc"] == ("id",)


def test_incident_card_v1_rejects_commander_without_at_prefix() -> None:
    # ARRANGE
    payload = _payload()
    payload["commander"] = "alice"

    # ACT / ASSERT
    with pytest.raises(ValidationError) as error_info:
        IncidentCardV1.model_validate(payload, context={"clock": CLOCK})

    assert error_info.value.errors()[0]["loc"] == ("commander",)
