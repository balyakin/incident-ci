from pathlib import Path
from typing import Annotated, List, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError
from yaml import YAMLError

from incident_ci.exceptions import ConfigError, InputError

LabelName = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")]
ServiceName = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")]
GlobPattern = Annotated[str, StringConstraints(min_length=1, max_length=256, strip_whitespace=True)]


class IncidentCIConfig(BaseModel):
    """Repository configuration for incident-ci."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = Field(default=1)
    required_labels: List[LabelName] = Field(min_length=1)
    exempt_labels: List[LabelName] = Field(default_factory=list)
    strict: bool = Field(default=True)
    incident_file_globs: List[GlobPattern] = Field(min_length=1)
    allowed_services: List[ServiceName] = Field(min_length=1)


def load_config(config_path: Path) -> IncidentCIConfig:
    """Load and validate repository configuration."""

    if not config_path.exists():
        raise InputError(f"Config file does not exist: {config_path}")

    if not config_path.is_file():
        raise InputError(f"Config path is not a file: {config_path}")

    try:
        config_text = config_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise InputError(f"Cannot read config file: {config_path}") from error

    try:
        raw_config = yaml.safe_load(config_text)
    except YAMLError as error:
        raise ConfigError(f"Invalid YAML in config file: {config_path}") from error

    try:
        return IncidentCIConfig.model_validate(raw_config)
    except ValidationError as error:
        raise ConfigError(f"Invalid incident-ci config: {config_path}") from error
