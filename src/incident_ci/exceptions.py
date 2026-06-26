from typing import Optional

from incident_ci.constants import EX_CONFIG, EX_DATAERR, EX_NOINPUT, EX_SOFTWARE


class IncidentCIError(Exception):
    """Base application error."""

    def __init__(self, message: str, exit_code: int) -> None:
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code


class ConfigError(IncidentCIError):
    """Configuration error."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, exit_code=EX_CONFIG)


class InputError(IncidentCIError):
    """Input file error."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, exit_code=EX_NOINPUT)


class ParseError(IncidentCIError):
    """Markdown or YAML parsing error with issue metadata."""

    def __init__(
        self,
        message: str,
        issue_code: str = "SCHEMA_INVALID",
        file_path: str = "<unknown>",
        line_start: Optional[int] = 1,
        line_end: Optional[int] = 1,
        field_path: Optional[str] = None,
    ) -> None:
        super().__init__(message=message, exit_code=EX_DATAERR)
        self.issue_code = issue_code
        self.file_path = file_path
        self.line_start = line_start
        self.line_end = line_end
        self.field_path = field_path


class ValidationFailedError(IncidentCIError):
    """Validation failed error."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, exit_code=EX_DATAERR)


class InternalError(IncidentCIError):
    """Unexpected internal error."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, exit_code=EX_SOFTWARE)
