import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Callable, List, Optional, Sequence

import typer

from incident_ci.config import IncidentCIConfig, load_config
from incident_ci.constants import DEFAULT_CONFIG_PATH, EX_DATAERR, EX_OK, EX_SOFTWARE
from incident_ci.exceptions import IncidentCIError, InputError, ParseError
from incident_ci.file_selection import (
    has_exempt_label,
    read_changed_files,
    require_incident_card,
    select_incident_files,
)
from incident_ci.logging_config import LOGGER_NAME, configure_logging
from incident_ci.models import Issue, ValidationResult
from incident_ci.parser import parse_incident_file
from incident_ci.reporters import render_json_report, render_sarif_report, render_text_report
from incident_ci.validator import validate_parsed_card

app = typer.Typer(no_args_is_help=True)
DEFAULT_CONFIG_FILE = Path(DEFAULT_CONFIG_PATH)
SUPPORTED_FORMATS = {"text", "json", "sarif"}
SUPPORTED_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR"}


@app.callback()
def main() -> None:
    """incident-ci command line interface."""


@app.command()
def check(
    files: Annotated[Optional[List[Path]], typer.Argument()] = None,
    config_path: Annotated[Path, typer.Option("--config")] = DEFAULT_CONFIG_FILE,
    files_from: Annotated[Optional[Path], typer.Option("--files-from")] = None,
    labels: Annotated[str, typer.Option("--labels")] = "",
    report_format: Annotated[str, typer.Option("--format")] = "text",
    output_path: Annotated[Optional[Path], typer.Option("--output")] = None,
    log_level: Annotated[str, typer.Option("--log-level")] = "INFO",
) -> None:
    """Validate incident cards."""

    logger = logging.getLogger(LOGGER_NAME)

    try:
        _validate_log_level(log_level=log_level)
        logger = configure_logging(level=log_level)
        exit_code = run_check_command(
            files=files,
            config_path=config_path,
            files_from=files_from,
            labels=labels,
            report_format=report_format,
            output_path=output_path,
            logger=logger,
        )
    except IncidentCIError as error:
        logger.exception("incident_ci_failed", extra={"exit_code": error.exit_code})
        raise typer.Exit(code=error.exit_code) from error
    except Exception as error:
        logger.exception("incident_ci_unhandled_error", extra={"exit_code": EX_SOFTWARE})
        raise typer.Exit(code=EX_SOFTWARE) from error

    raise typer.Exit(code=exit_code)


def run_check_command(
    files: Optional[List[Path]],
    config_path: Path,
    files_from: Optional[Path],
    labels: str,
    report_format: str,
    output_path: Optional[Path],
    logger: logging.Logger,
) -> int:
    """Run incident card validation command."""

    config = load_config(config_path=config_path)
    _validate_input_modes(files=files, files_from=files_from)
    _validate_report_format(report_format=report_format)

    label_values = _parse_labels(labels=labels)
    selected_files = _select_files_for_mode(files=files, files_from=files_from, labels=label_values, config=config)
    result = _validate_selected_files(
        selected_files=selected_files,
        files_from=files_from,
        labels=label_values,
        config=config,
        logger=logger,
    )
    _write_report(result=result, report_format=report_format, output_path=output_path)

    if result.is_valid:
        return EX_OK

    return EX_DATAERR


def _validate_input_modes(files: Optional[List[Path]], files_from: Optional[Path]) -> None:
    has_files = files is not None and len(files) > 0
    if has_files and files_from is not None:
        raise InputError("Pass either FILES or --files-from, not both")

    if not has_files and files_from is None:
        raise InputError("Pass FILES or --files-from")


def _validate_report_format(report_format: str) -> None:
    if report_format not in SUPPORTED_FORMATS:
        raise InputError(f"Unsupported report format: {report_format}")


def _validate_log_level(log_level: str) -> None:
    if log_level not in SUPPORTED_LOG_LEVELS:
        raise InputError(f"Unsupported log level: {log_level}")


def _parse_labels(labels: str) -> List[str]:
    parsed_labels: List[str] = []
    for label in labels.split(","):
        normalized_label = label.strip().lower()
        if normalized_label != "":
            parsed_labels.append(normalized_label)

    return parsed_labels


def _select_files_for_mode(
    files: Optional[List[Path]],
    files_from: Optional[Path],
    labels: Sequence[str],
    config: IncidentCIConfig,
) -> List[Path]:
    if files_from is not None:
        return _select_files_from_changed_list(files_from=files_from, labels=labels, config=config)

    if files is None:
        return []

    return select_incident_files(changed_files=files, config=config)


def _select_files_from_changed_list(
    files_from: Path,
    labels: Sequence[str],
    config: IncidentCIConfig,
) -> List[Path]:
    if has_exempt_label(labels=labels, config=config):
        return []

    changed_files = read_changed_files(files_path=files_from)
    return select_incident_files(changed_files=changed_files, config=config)


def _validate_selected_files(
    selected_files: Sequence[Path],
    files_from: Optional[Path],
    labels: Sequence[str],
    config: IncidentCIConfig,
    logger: logging.Logger,
) -> ValidationResult:
    if files_from is not None and has_exempt_label(labels=labels, config=config):
        return ValidationResult(issues=[], checked_files=[])

    required = files_from is not None and require_incident_card(labels=labels, config=config)
    if required and len(selected_files) == 0:
        return ValidationResult(
            issues=[
                Issue(
                    code="INCIDENT_CARD_REQUIRED",
                    severity="error",
                    message="Incident Card is required for this pull request",
                    file_path=DEFAULT_CONFIG_PATH,
                    field_path=None,
                    line_start=1,
                    line_end=1,
                ),
            ],
            checked_files=[],
        )

    checked_files: List[str] = []
    issues: List[Issue] = []
    clock = datetime.now(tz=UTC)
    for incident_file in selected_files:
        file_path = str(incident_file)
        checked_files.append(file_path)
        try:
            parsed_card = parse_incident_file(file_path=incident_file)
        except ParseError as error:
            issues.append(_issue_from_parse_error(error=error, fallback_file_path=file_path))
            continue

        logger.debug("validated_incident_file", extra={"file_path": file_path})
        validation_result = validate_parsed_card(parsed_card, config=config, clock=clock)
        issues.extend(validation_result.issues)

    return ValidationResult(issues=issues, checked_files=checked_files)


def _issue_from_parse_error(error: ParseError, fallback_file_path: str) -> Issue:
    file_path = error.file_path
    if file_path == "<unknown>":
        file_path = fallback_file_path

    line_start = error.line_start or 1
    line_end = error.line_end or line_start
    return Issue(
        code=error.issue_code,
        severity="error",
        message=error.message,
        file_path=file_path,
        field_path=error.field_path,
        line_start=line_start,
        line_end=line_end,
    )


def _write_report(result: ValidationResult, report_format: str, output_path: Optional[Path]) -> None:
    renderer = _renderer_for_format(report_format=report_format)
    report = renderer(result)
    if output_path is None:
        sys.stdout.write(report + "\n")
        return

    output_path.write_text(report + "\n", encoding="utf-8")


def _renderer_for_format(report_format: str) -> Callable[[ValidationResult], str]:
    if report_format == "json":
        return render_json_report
    if report_format == "sarif":
        return render_sarif_report

    return render_text_report
