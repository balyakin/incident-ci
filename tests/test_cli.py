import json
from pathlib import Path

from typer.testing import CliRunner

from incident_ci.cli import app

FIXTURES_DIR = Path("tests/fixtures")


def test_cli_explicit_valid_file_returns_ok() -> None:
    # ARRANGE
    runner = CliRunner()
    command_args = [
        "check",
        str(FIXTURES_DIR / "valid_detected.md"),
        "--config",
        str(FIXTURES_DIR / ".incident-ci.yaml"),
    ]

    # ACT
    result = runner.invoke(app, command_args)

    # ASSERT
    assert result.exit_code == 0
    assert "Incident Card validation passed" in result.stdout


def test_cli_explicit_invalid_file_returns_dataerr() -> None:
    # ARRANGE
    runner = CliRunner()
    command_args = [
        "check",
        str(FIXTURES_DIR / "invalid_yaml.md"),
        "--config",
        str(FIXTURES_DIR / ".incident-ci.yaml"),
    ]

    # ACT
    result = runner.invoke(app, command_args)

    # ASSERT
    assert result.exit_code == 65
    assert "YAML_INVALID" in result.stdout


def test_cli_files_from_without_incident_label_and_without_files_returns_ok() -> None:
    # ARRANGE
    runner = CliRunner()
    command_args = [
        "check",
        "--config",
        str(FIXTURES_DIR / ".incident-ci.yaml"),
        "--files-from",
        str(FIXTURES_DIR / "changed_files_empty.txt"),
    ]

    # ACT
    result = runner.invoke(app, command_args)

    # ASSERT
    assert result.exit_code == 0


def test_cli_files_from_with_incident_label_and_without_files_returns_dataerr() -> None:
    # ARRANGE
    runner = CliRunner()
    command_args = [
        "check",
        "--config",
        str(FIXTURES_DIR / ".incident-ci.yaml"),
        "--files-from",
        str(FIXTURES_DIR / "changed_files_empty.txt"),
        "--labels",
        "incident",
    ]

    # ACT
    result = runner.invoke(app, command_args)

    # ASSERT
    assert result.exit_code == 65
    assert "INCIDENT_CARD_REQUIRED" in result.stdout


def test_cli_files_from_with_mixed_case_incident_label_returns_dataerr() -> None:
    # ARRANGE
    runner = CliRunner()
    command_args = [
        "check",
        "--config",
        str(FIXTURES_DIR / ".incident-ci.yaml"),
        "--files-from",
        str(FIXTURES_DIR / "changed_files_empty.txt"),
        "--labels",
        "Incident",
    ]

    # ACT
    result = runner.invoke(app, command_args)

    # ASSERT
    assert result.exit_code == 65
    assert "INCIDENT_CARD_REQUIRED" in result.stdout


def test_cli_exempt_label_returns_ok_and_empty_checked_files() -> None:
    # ARRANGE
    runner = CliRunner()
    command_args = [
        "check",
        "--config",
        str(FIXTURES_DIR / ".incident-ci.yaml"),
        "--files-from",
        str(FIXTURES_DIR / "changed_files.txt"),
        "--labels",
        "incident,incident-card-exempt",
        "--format",
        "json",
    ]

    # ACT
    result = runner.invoke(app, command_args)

    # ASSERT
    assert result.exit_code == 0
    assert json.loads(result.stdout)["checked_files"] == []


def test_cli_two_incident_files_merges_report() -> None:
    # ARRANGE
    runner = CliRunner()
    command_args = [
        "check",
        "--config",
        str(FIXTURES_DIR / ".incident-ci.yaml"),
        "--files-from",
        str(FIXTURES_DIR / "changed_files_two_incidents.txt"),
        "--labels",
        "incident",
        "--format",
        "json",
    ]

    # ACT
    result = runner.invoke(app, command_args)
    payload = json.loads(result.stdout)

    # ASSERT
    assert result.exit_code == 0
    assert payload["checked_files"] == [
        "tests/fixtures/valid_detected.md",
        "tests/fixtures/valid_resolved.md",
    ]


def test_cli_mode_conflict_returns_noinput() -> None:
    # ARRANGE
    runner = CliRunner()
    command_args = [
        "check",
        str(FIXTURES_DIR / "valid_detected.md"),
        "--config",
        str(FIXTURES_DIR / ".incident-ci.yaml"),
        "--files-from",
        str(FIXTURES_DIR / "changed_files.txt"),
    ]

    # ACT
    result = runner.invoke(app, command_args)

    # ASSERT
    assert result.exit_code == 66


def test_cli_invalid_format_returns_noinput() -> None:
    # ARRANGE
    runner = CliRunner()
    command_args = [
        "check",
        str(FIXTURES_DIR / "valid_detected.md"),
        "--config",
        str(FIXTURES_DIR / ".incident-ci.yaml"),
        "--format",
        "xml",
    ]

    # ACT
    result = runner.invoke(app, command_args)

    # ASSERT
    assert result.exit_code == 66


def test_cli_log_level_debug_smoke() -> None:
    # ARRANGE
    runner = CliRunner()
    command_args = [
        "check",
        str(FIXTURES_DIR / "valid_detected.md"),
        "--config",
        str(FIXTURES_DIR / ".incident-ci.yaml"),
        "--log-level",
        "DEBUG",
    ]

    # ACT
    result = runner.invoke(app, command_args)

    # ASSERT
    assert result.exit_code == 0


def test_cli_invalid_log_level_returns_noinput() -> None:
    # ARRANGE
    runner = CliRunner()
    command_args = [
        "check",
        str(FIXTURES_DIR / "valid_detected.md"),
        "--config",
        str(FIXTURES_DIR / ".incident-ci.yaml"),
        "--log-level",
        "TRACE",
    ]

    # ACT
    result = runner.invoke(app, command_args)

    # ASSERT
    assert result.exit_code == 66


def test_cli_json_stdout() -> None:
    # ARRANGE
    runner = CliRunner()
    command_args = [
        "check",
        str(FIXTURES_DIR / "valid_detected.md"),
        "--config",
        str(FIXTURES_DIR / ".incident-ci.yaml"),
        "--format",
        "json",
    ]

    # ACT
    result = runner.invoke(app, command_args)

    # ASSERT
    assert json.loads(result.stdout)["is_valid"] is True


def test_cli_sarif_output_file_created_for_validation_errors(tmp_path: Path) -> None:
    # ARRANGE
    runner = CliRunner()
    output_path = tmp_path / "incident-ci.sarif"
    command_args = [
        "check",
        str(FIXTURES_DIR / "invalid_yaml.md"),
        "--config",
        str(FIXTURES_DIR / ".incident-ci.yaml"),
        "--format",
        "sarif",
        "--output",
        str(output_path),
    ]

    # ACT
    result = runner.invoke(app, command_args)
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    # ASSERT
    assert result.exit_code == 65
    assert payload["runs"][0]["results"][0]["ruleId"] == "YAML_INVALID"


def test_cli_missing_config_returns_noinput(tmp_path: Path) -> None:
    # ARRANGE
    runner = CliRunner()
    command_args = [
        "check",
        str(FIXTURES_DIR / "valid_detected.md"),
        "--config",
        str(tmp_path / ".incident-ci.yaml"),
    ]

    # ACT
    result = runner.invoke(app, command_args)

    # ASSERT
    assert result.exit_code == 66


def test_cli_invalid_config_returns_config_error(tmp_path: Path) -> None:
    # ARRANGE
    runner = CliRunner()
    config_path = tmp_path / ".incident-ci.yaml"
    config_path.write_text("schema_version: 2\n", encoding="utf-8")
    command_args = [
        "check",
        str(FIXTURES_DIR / "valid_detected.md"),
        "--config",
        str(config_path),
    ]

    # ACT
    result = runner.invoke(app, command_args)

    # ASSERT
    assert result.exit_code == 78
