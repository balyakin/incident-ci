import json
from pathlib import Path
from typing import Any, Dict, List, Literal, Set

from incident_ci.constants import MAX_SARIF_MESSAGE_LENGTH, SARIF_SCHEMA_URL, SARIF_VERSION
from incident_ci.models import Issue, ValidationResult

ReportFormat = Literal["text", "json", "sarif"]
SARIF_INFORMATION_URI = "https://github.com/org/incident-ci"


def render_text_report(result: ValidationResult) -> str:
    """Render human-readable text report."""

    if len(result.issues) == 0:
        return "Incident Card validation passed"

    lines: List[str] = [f"Incident Card validation failed: {len(result.issues)} issue(s)"]
    for issue in result.issues:
        line_start = issue.line_start or 1
        field_path = issue.field_path or "-"
        lines.append(
            f"{issue.severity} {issue.code} {issue.file_path}:{line_start} {field_path} {issue.message}",
        )

    return "\n".join(lines)


def render_json_report(result: ValidationResult) -> str:
    """Render machine-readable JSON report."""

    payload = result.model_dump(mode="json")
    payload["is_valid"] = result.is_valid
    return json.dumps(payload, indent=2, ensure_ascii=False)


def render_sarif_report(result: ValidationResult) -> str:
    """Render SARIF 2.1.0 report."""

    sarif_payload: Dict[str, Any] = {
        "version": SARIF_VERSION,
        "$schema": SARIF_SCHEMA_URL,
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "incident-ci",
                        "informationUri": SARIF_INFORMATION_URI,
                        "rules": _build_sarif_rules(issues=result.issues),
                    },
                },
                "results": [build_sarif_result(issue=issue) for issue in result.issues],
            },
        ],
    }
    return json.dumps(sarif_payload, indent=2, ensure_ascii=False)


def build_sarif_result(issue: Issue) -> Dict[str, Any]:
    """Build SARIF result for one issue."""

    line_start = issue.line_start or 1
    line_end = issue.line_end or line_start
    return {
        "ruleId": issue.code,
        "level": _sarif_level(severity=issue.severity),
        "message": {"text": _truncate_message(message=issue.message)},
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": {"uri": _relative_posix_path(path=issue.file_path)},
                    "region": {
                        "startLine": line_start,
                        "endLine": line_end,
                    },
                },
            },
        ],
    }


def _build_sarif_rules(issues: List[Issue]) -> List[Dict[str, Any]]:
    rules: List[Dict[str, Any]] = []
    seen_rule_ids: Set[str] = set()
    for issue in issues:
        if issue.code in seen_rule_ids:
            continue

        rules.append(
            {
                "id": issue.code,
                "name": issue.code,
                "shortDescription": {"text": issue.code},
                "defaultConfiguration": {"level": _sarif_level(severity=issue.severity)},
            },
        )
        seen_rule_ids.add(issue.code)

    return rules


def _sarif_level(severity: str) -> str:
    if severity == "error":
        return "error"
    if severity == "warning":
        return "warning"

    return "note"


def _truncate_message(message: str) -> str:
    encoded_message = message.encode("utf-8")
    if len(encoded_message) <= MAX_SARIF_MESSAGE_LENGTH:
        return message

    return encoded_message[:MAX_SARIF_MESSAGE_LENGTH].decode("utf-8", errors="ignore")


def _relative_posix_path(path: str) -> str:
    normalized_path = path.replace("\\", "/")
    path_obj = Path(normalized_path)
    if not path_obj.is_absolute():
        return normalized_path

    try:
        return path_obj.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path_obj.as_posix().lstrip("/")
