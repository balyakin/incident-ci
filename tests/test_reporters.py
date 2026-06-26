import json
from pathlib import Path

from incident_ci.constants import SARIF_VERSION
from incident_ci.models import Issue, ValidationResult
from incident_ci.reporters import render_json_report, render_sarif_report, render_text_report


def _issue(severity: str = "error", message: str = "Missing title") -> Issue:
    return Issue(
        code="FIELD_REQUIRED",
        severity=severity,
        message=message,
        file_path="incidents/INC-2026-001.md",
        field_path="incident_card.title",
        line_start=5,
        line_end=5,
    )


def test_render_text_report_success() -> None:
    # ARRANGE
    result = ValidationResult(issues=[], checked_files=[])

    # ACT
    report = render_text_report(result=result)

    # ASSERT
    assert report == "Incident Card validation passed"


def test_render_text_report_failure() -> None:
    # ARRANGE
    result = ValidationResult(issues=[_issue()], checked_files=["incidents/INC-2026-001.md"])

    # ACT
    report = render_text_report(result=result)

    # ASSERT
    assert "Incident Card validation failed: 1 issue(s)" in report
    assert "error FIELD_REQUIRED incidents/INC-2026-001.md:5 incident_card.title Missing title" in report


def test_render_json_report_contains_is_valid() -> None:
    # ARRANGE
    result = ValidationResult(issues=[], checked_files=[])

    # ACT
    payload = json.loads(render_json_report(result=result))

    # ASSERT
    assert payload == {"issues": [], "checked_files": [], "is_valid": True}


def test_render_sarif_report_version_and_error_mapping() -> None:
    # ARRANGE
    result = ValidationResult(issues=[_issue()], checked_files=["incidents/INC-2026-001.md"])

    # ACT
    payload = json.loads(render_sarif_report(result=result))

    # ASSERT
    assert payload["version"] == SARIF_VERSION
    assert payload["runs"][0]["results"][0]["level"] == "error"


def test_render_sarif_report_warning_mapping() -> None:
    # ARRANGE
    result = ValidationResult(issues=[_issue(severity="warning")], checked_files=[])

    # ACT
    payload = json.loads(render_sarif_report(result=result))

    # ASSERT
    assert payload["runs"][0]["results"][0]["level"] == "warning"


def test_render_sarif_report_info_mapping() -> None:
    # ARRANGE
    result = ValidationResult(issues=[_issue(severity="info")], checked_files=[])

    # ACT
    payload = json.loads(render_sarif_report(result=result))

    # ASSERT
    assert payload["runs"][0]["results"][0]["level"] == "note"


def test_render_sarif_report_truncates_long_message() -> None:
    # ARRANGE
    issue = Issue.model_construct(
        code="FIELD_REQUIRED",
        severity="error",
        message="x" * 20_001,
        file_path="incidents/INC-2026-001.md",
        field_path="incident_card.title",
        line_start=5,
        line_end=5,
    )
    result = ValidationResult(issues=[issue], checked_files=[])

    # ACT
    payload = json.loads(render_sarif_report(result=result))

    # ASSERT
    assert len(payload["runs"][0]["results"][0]["message"]["text"]) == 20_000


def test_render_sarif_report_truncates_long_message_by_utf8_bytes() -> None:
    # ARRANGE
    issue = Issue.model_construct(
        code="FIELD_REQUIRED",
        severity="error",
        message="€" * 7_000,
        file_path="incidents/INC-2026-001.md",
        field_path="incident_card.title",
        line_start=5,
        line_end=5,
    )
    result = ValidationResult(issues=[issue], checked_files=[])

    # ACT
    payload = json.loads(render_sarif_report(result=result))
    truncated_message = payload["runs"][0]["results"][0]["message"]["text"]

    # ASSERT
    assert len(truncated_message.encode("utf-8")) <= 20_000


def test_render_sarif_report_uses_relative_posix_paths() -> None:
    # ARRANGE
    absolute_path = Path.cwd() / "incidents" / "INC-2026-001.md"
    issue = Issue(
        code="FIELD_REQUIRED",
        severity="error",
        message="Missing title",
        file_path=str(absolute_path),
        field_path="incident_card.title",
        line_start=None,
        line_end=None,
    )
    result = ValidationResult(issues=[issue], checked_files=[])

    # ACT
    payload = json.loads(render_sarif_report(result=result))
    physical_location = payload["runs"][0]["results"][0]["locations"][0]["physicalLocation"]

    # ASSERT
    assert physical_location["artifactLocation"]["uri"] == "incidents/INC-2026-001.md"
    assert physical_location["region"]["startLine"] == 1


def test_render_sarif_report_deduplicates_rules() -> None:
    # ARRANGE
    result = ValidationResult(issues=[_issue(), _issue(message="Still missing title")], checked_files=[])

    # ACT
    payload = json.loads(render_sarif_report(result=result))

    # ASSERT
    assert payload["runs"][0]["tool"]["driver"]["rules"] == [
        {
            "id": "FIELD_REQUIRED",
            "name": "FIELD_REQUIRED",
            "shortDescription": {"text": "FIELD_REQUIRED"},
            "defaultConfiguration": {"level": "error"},
        }
    ]


def test_render_sarif_report_external_absolute_path_is_made_relative() -> None:
    # ARRANGE
    issue = Issue(
        code="FIELD_REQUIRED",
        severity="error",
        message="Missing title",
        file_path="/tmp/incident-ci/INC-2026-001.md",
        field_path="incident_card.title",
        line_start=5,
        line_end=5,
    )
    result = ValidationResult(issues=[issue], checked_files=[])

    # ACT
    payload = json.loads(render_sarif_report(result=result))
    physical_location = payload["runs"][0]["results"][0]["locations"][0]["physicalLocation"]

    # ASSERT
    assert physical_location["artifactLocation"]["uri"] == "tmp/incident-ci/INC-2026-001.md"
