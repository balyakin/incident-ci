from pathlib import Path
from typing import Type

import pytest

from incident_ci.config import load_config
from incident_ci.exceptions import ConfigError, InputError

FIXTURES_DIR = Path("tests/fixtures")


def test_load_config_valid_config() -> None:
    # ARRANGE
    config_path = FIXTURES_DIR / ".incident-ci.yaml"

    # ACT
    config = load_config(config_path=config_path)

    # ASSERT
    assert config.schema_version == 1
    assert config.required_labels == ["incident"]
    assert config.allowed_services == ["payment-api", "auth-api", "order-api"]


def test_load_config_missing_config_raises_input_error(tmp_path: Path) -> None:
    # ARRANGE
    config_path = tmp_path / ".incident-ci.yaml"

    # ACT / ASSERT
    with pytest.raises(InputError):
        load_config(config_path=config_path)


def test_load_config_invalid_yaml_raises_config_error(tmp_path: Path) -> None:
    # ARRANGE
    config_path = tmp_path / ".incident-ci.yaml"
    config_path.write_text("schema_version: [", encoding="utf-8")

    # ACT / ASSERT
    with pytest.raises(ConfigError):
        load_config(config_path=config_path)


def test_load_config_invalid_utf8_raises_input_error(tmp_path: Path) -> None:
    # ARRANGE
    config_path = tmp_path / ".incident-ci.yaml"
    config_path.write_bytes(b"\xff")

    # ACT / ASSERT
    with pytest.raises(InputError):
        load_config(config_path=config_path)


@pytest.mark.parametrize(
    ("config_text", "expected_error"),
    [
        (
            """
schema_version: 1
required_labels:
  - incident
exempt_labels: []
strict: true
incident_file_globs:
  - incidents/**/*.md
allowed_services:
  - payment-api
unknown_key: true
""",
            ConfigError,
        ),
        (
            """
schema_version: 1
required_labels: []
exempt_labels: []
strict: true
incident_file_globs:
  - incidents/**/*.md
allowed_services:
  - payment-api
""",
            ConfigError,
        ),
        (
            """
schema_version: 1
required_labels:
  - incident
exempt_labels: []
strict: true
incident_file_globs:
  - incidents/**/*.md
allowed_services: []
""",
            ConfigError,
        ),
        (
            """
schema_version: 1
required_labels:
  - Incident
exempt_labels: []
strict: true
incident_file_globs:
  - incidents/**/*.md
allowed_services:
  - payment-api
""",
            ConfigError,
        ),
        (
            """
schema_version: 1
required_labels:
  - incident
exempt_labels: []
strict: true
incident_file_globs:
  - incidents/**/*.md
allowed_services:
  - PaymentApi
""",
            ConfigError,
        ),
    ],
)
def test_load_config_invalid_schema_raises_config_error(
    tmp_path: Path,
    config_text: str,
    expected_error: Type[ConfigError],
) -> None:
    # ARRANGE
    config_path = tmp_path / ".incident-ci.yaml"
    config_path.write_text(config_text, encoding="utf-8")

    # ACT / ASSERT
    with pytest.raises(expected_error):
        load_config(config_path=config_path)
