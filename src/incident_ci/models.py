from datetime import UTC, datetime, timedelta
from typing import Annotated, List, Literal, Mapping, Optional, cast

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StringConstraints,
    ValidationInfo,
    model_validator,
)

from incident_ci.constants import DEFAULT_CLOCK_SKEW_SECONDS

IncidentId = Annotated[str, StringConstraints(pattern=r"^INC-\d{4}-\d{3,}$", strip_whitespace=True)]
ShortText = Annotated[str, StringConstraints(min_length=10, max_length=200, strip_whitespace=True)]
MediumText = Annotated[str, StringConstraints(min_length=20, max_length=5_000, strip_whitespace=True)]
LongText = Annotated[str, StringConstraints(min_length=1, max_length=20_000, strip_whitespace=True)]
ServiceName = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$", strip_whitespace=True)]
CommanderName = Annotated[str, StringConstraints(pattern=r"^@[a-zA-Z0-9-]+$", strip_whitespace=True)]

Severity = Literal["low", "medium", "high", "critical"]
IncidentStatus = Literal["detected", "mitigated", "resolved"]
Environment = Literal["production", "staging", "dev", "test"]
IssueSeverity = Literal["error", "warning", "info"]


class SourceLocation(BaseModel):
    """Source location for reports."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    file_path: str = Field(min_length=1)
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)


class Issue(BaseModel):
    """Validation issue."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1, max_length=64)
    severity: IssueSeverity
    message: str = Field(min_length=1, max_length=20_000)
    file_path: str = Field(min_length=1)
    field_path: Optional[str] = Field(default=None)
    line_start: Optional[int] = Field(default=None, ge=1)
    line_end: Optional[int] = Field(default=None, ge=1)


class ValidationResult(BaseModel):
    """Validation result for one command run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    issues: List[Issue] = Field(default_factory=list)
    checked_files: List[str] = Field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Return whether validation has no blocking errors."""

        return all(issue.severity != "error" for issue in self.issues)


class IncidentCardV1(BaseModel):
    """Incident card schema version 1."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = Field(default=1)
    id: IncidentId
    status: IncidentStatus
    title: ShortText
    severity: Severity
    environment: Environment
    service: ServiceName
    commander: Optional[CommanderName] = Field(default=None)
    detected_at: AwareDatetime
    mitigated_at: Optional[AwareDatetime] = Field(default=None)
    resolved_at: Optional[AwareDatetime] = Field(default=None)
    description: MediumText
    impact: Optional[MediumText] = Field(default=None)
    mitigation: Optional[MediumText] = Field(default=None)
    root_cause: Optional[MediumText] = Field(default=None)
    postmortem_link: Optional[HttpUrl] = Field(default=None)
    logs: Optional[LongText] = Field(default=None)

    @model_validator(mode="after")
    def validate_business_rules(self, info: ValidationInfo) -> "IncidentCardV1":
        """Validate cross-field incident card business rules."""

        clock = self._get_clock(info=info)
        self._validate_detected_at(clock=clock)
        self._validate_chronology()
        self._validate_status_required_fields()
        self._validate_severity_required_fields()
        return self

    def _get_clock(self, info: ValidationInfo) -> datetime:
        context = cast(Mapping[str, object], info.context or {})
        clock = context.get("clock")
        if clock is None:
            return datetime.now(tz=UTC)

        return cast(datetime, clock)

    def _validate_detected_at(self, clock: datetime) -> None:
        allowed_future = clock + timedelta(seconds=DEFAULT_CLOCK_SKEW_SECONDS)
        if self.detected_at > allowed_future:
            raise ValueError("detected_at must not be in the future")

    def _validate_chronology(self) -> None:
        if self.mitigated_at is not None and self.mitigated_at < self.detected_at:
            raise ValueError("mitigated_at must be later than detected_at")

        if self.resolved_at is not None and self.resolved_at < self.detected_at:
            raise ValueError("resolved_at must be later than detected_at")

        if self.mitigated_at is not None and self.resolved_at is not None and self.resolved_at < self.mitigated_at:
            raise ValueError("resolved_at must be later than mitigated_at")

    def _validate_status_required_fields(self) -> None:
        if self.status == "detected" and self.resolved_at is not None:
            raise ValueError("resolved_at must be empty when status is detected")

        if self.status == "mitigated":
            if self.mitigated_at is None:
                raise ValueError("mitigated_at is required when status is mitigated")
            if self.mitigation is None:
                raise ValueError("mitigation is required when status is mitigated")
            if self.resolved_at is not None:
                raise ValueError("resolved_at must be empty when status is mitigated")

        if self.status == "resolved":
            if self.mitigated_at is None:
                raise ValueError("mitigated_at is required when status is resolved")
            if self.resolved_at is None:
                raise ValueError("resolved_at is required when status is resolved")
            if self.impact is None:
                raise ValueError("impact is required when status is resolved")
            if self.mitigation is None:
                raise ValueError("mitigation is required when status is resolved")
            if self.root_cause is None:
                raise ValueError("root_cause is required when status is resolved")

    def _validate_severity_required_fields(self) -> None:
        is_high_impact = self.severity == "high" or self.severity == "critical"
        if is_high_impact and self.commander is None:
            raise ValueError("commander is required for high and critical incidents")

        if is_high_impact and self.impact is None:
            raise ValueError("impact is required for high and critical incidents")

        if self.severity == "critical" and self.logs is None:
            raise ValueError("logs is required for critical incidents")
