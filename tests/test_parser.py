from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from markdown_it.token import Token

from incident_ci.exceptions import InputError, ParseError
from incident_ci.parser import (
    _build_field_locations,
    _check_markdown_file,
    _read_markdown_file,
    _token_location,
    parse_incident_file,
)

FIXTURES_DIR = Path("tests/fixtures")


class _StatRaisesPath:
    def exists(self) -> bool:
        return True

    def is_file(self) -> bool:
        return True

    def stat(self) -> object:
        raise OSError("stat failed")

    def __str__(self) -> str:
        return "incidents/stat-raises.md"


class _ReadRaisesPath:
    def read_text(self, encoding: str) -> str:
        raise OSError(f"read failed with {encoding}")

    def __str__(self) -> str:
        return "incidents/read-raises.md"


def test_parse_incident_file_valid_yaml() -> None:
    # ARRANGE
    file_path = FIXTURES_DIR / "valid_detected.md"

    # ACT
    parsed_card = parse_incident_file(file_path=file_path)

    # ASSERT
    assert parsed_card.file_path == "tests/fixtures/valid_detected.md"
    assert parsed_card.payload["id"] == "INC-2026-101"
    assert parsed_card.field_locations["severity"].line_start == 9


def test_parse_incident_file_valid_yml() -> None:
    # ARRANGE
    file_path = FIXTURES_DIR / "yml_valid.md"

    # ACT
    parsed_card = parse_incident_file(file_path=file_path)

    # ASSERT
    assert parsed_card.payload["id"] == "INC-2026-109"


def test_parse_incident_file_without_yaml_block_raises_not_found(tmp_path: Path) -> None:
    # ARRANGE
    file_path = tmp_path / "missing.md"
    file_path.write_text("# Missing\nNo YAML block here.\n", encoding="utf-8")

    # ACT / ASSERT
    with pytest.raises(ParseError) as error_info:
        parse_incident_file(file_path=file_path)

    assert error_info.value.issue_code == "INCIDENT_CARD_NOT_FOUND"
    assert error_info.value.line_start == 1


def test_parse_incident_file_yaml_without_card_raises_not_found() -> None:
    # ARRANGE
    file_path = FIXTURES_DIR / "missing_card.md"

    # ACT / ASSERT
    with pytest.raises(ParseError) as error_info:
        parse_incident_file(file_path=file_path)

    assert error_info.value.issue_code == "INCIDENT_CARD_NOT_FOUND"


def test_parse_incident_file_multiple_cards_raises_multiple_cards() -> None:
    # ARRANGE
    file_path = FIXTURES_DIR / "multiple_cards.md"

    # ACT / ASSERT
    with pytest.raises(ParseError) as error_info:
        parse_incident_file(file_path=file_path)

    assert error_info.value.issue_code == "MULTIPLE_INCIDENT_CARDS"
    assert error_info.value.line_start == 16


def test_parse_incident_file_invalid_yaml_raises_yaml_invalid() -> None:
    # ARRANGE
    file_path = FIXTURES_DIR / "invalid_yaml.md"

    # ACT / ASSERT
    with pytest.raises(ParseError) as error_info:
        parse_incident_file(file_path=file_path)

    assert error_info.value.issue_code == "YAML_INVALID"
    assert "unterminated" not in error_info.value.message


def test_parse_incident_file_non_mapping_root_raises_yaml_root_invalid() -> None:
    # ARRANGE
    file_path = FIXTURES_DIR / "non_mapping_root.md"

    # ACT / ASSERT
    with pytest.raises(ParseError) as error_info:
        parse_incident_file(file_path=file_path)

    assert error_info.value.issue_code == "YAML_ROOT_INVALID"


def test_parse_incident_file_too_large_file_raises_file_too_large(tmp_path: Path) -> None:
    # ARRANGE
    file_path = tmp_path / "too-large.md"
    file_path.write_text("x" * 1_048_577, encoding="utf-8")

    # ACT / ASSERT
    with pytest.raises(ParseError) as error_info:
        parse_incident_file(file_path=file_path)

    assert error_info.value.issue_code == "FILE_TOO_LARGE"
    assert "limit=1048576" in error_info.value.message


def test_parse_incident_file_too_large_yaml_block_raises_yaml_block_too_large(tmp_path: Path) -> None:
    # ARRANGE
    file_path = tmp_path / "large-yaml.md"
    large_value = "x" * 262_145
    file_path.write_text(f"```yaml\nincident_card:\n  logs: {large_value}\n```\n", encoding="utf-8")

    # ACT / ASSERT
    with pytest.raises(ParseError) as error_info:
        parse_incident_file(file_path=file_path)

    assert error_info.value.issue_code == "YAML_BLOCK_TOO_LARGE"


def test_parse_incident_file_unknown_field_line_number() -> None:
    # ARRANGE
    file_path = FIXTURES_DIR / "unknown_field.md"

    # ACT
    parsed_card = parse_incident_file(file_path=file_path)

    # ASSERT
    assert parsed_card.field_locations["unexpected_field"].line_start == 22


def test_parse_incident_file_incident_card_not_mapping(tmp_path: Path) -> None:
    # ARRANGE
    file_path = tmp_path / "card-not-mapping.md"
    file_path.write_text("```yaml\nincident_card: invalid\n```\n", encoding="utf-8")

    # ACT / ASSERT
    with pytest.raises(ParseError) as error_info:
        parse_incident_file(file_path=file_path)

    assert error_info.value.issue_code == "YAML_ROOT_INVALID"


def test_parse_incident_file_missing_file_raises_input_error(tmp_path: Path) -> None:
    # ARRANGE
    file_path = tmp_path / "missing.md"

    # ACT / ASSERT
    with pytest.raises(InputError):
        parse_incident_file(file_path=file_path)


def test_parse_incident_file_directory_raises_input_error(tmp_path: Path) -> None:
    # ARRANGE
    file_path = tmp_path / "incident-dir"
    file_path.mkdir()

    # ACT / ASSERT
    with pytest.raises(InputError):
        parse_incident_file(file_path=file_path)


def test_check_markdown_file_stat_error_raises_input_error() -> None:
    # ARRANGE
    file_path = _StatRaisesPath()

    # ACT / ASSERT
    with pytest.raises(InputError):
        _check_markdown_file(file_path=file_path)  # type: ignore[arg-type]


def test_read_markdown_file_read_error_raises_input_error() -> None:
    # ARRANGE
    file_path = _ReadRaisesPath()

    # ACT / ASSERT
    with pytest.raises(InputError):
        _read_markdown_file(file_path=file_path)  # type: ignore[arg-type]


def test_read_markdown_file_invalid_utf8_raises_input_error(tmp_path: Path) -> None:
    # ARRANGE
    file_path = tmp_path / "invalid-utf8.md"
    file_path.write_bytes(b"\xff")

    # ACT / ASSERT
    with pytest.raises(InputError):
        _read_markdown_file(file_path=file_path)


def test_parse_incident_file_non_yaml_fence_is_ignored(tmp_path: Path) -> None:
    # ARRANGE
    file_path = tmp_path / "non-yaml.md"
    file_path.write_text(
        """```text
incident_card:
  id: INC-2026-999
```
```yaml
incident_card:
  schema_version: 1
  id: INC-2026-121
  status: detected
  title: Payment API latency spike
  severity: medium
  environment: production
  service: payment-api
  commander: null
  detected_at: "2026-01-15T08:10:00Z"
  description: "Payment API latency exceeded the SLO for checkout requests."
```
""",
        encoding="utf-8",
    )

    # ACT
    parsed_card = parse_incident_file(file_path=file_path)

    # ASSERT
    assert parsed_card.payload["id"] == "INC-2026-121"


def test_parse_incident_file_invalid_yaml_without_incident_card_is_ignored(tmp_path: Path) -> None:
    # ARRANGE
    file_path = tmp_path / "invalid-unrelated-yaml.md"
    file_path.write_text(
        """```yaml
not_incident_card: [
```
```yaml
incident_card:
  schema_version: 1
  id: INC-2026-122
  status: detected
  title: Payment API latency spike
  severity: medium
  environment: production
  service: payment-api
  commander: null
  detected_at: "2026-01-15T08:10:00Z"
  description: "Payment API latency exceeded the SLO for checkout requests."
```
""",
        encoding="utf-8",
    )

    # ACT
    parsed_card = parse_incident_file(file_path=file_path)

    # ASSERT
    assert parsed_card.payload["id"] == "INC-2026-122"


def test_token_location_without_map_uses_line_one() -> None:
    # ARRANGE
    token = Token("fence", "code", 0)
    token.map = None

    # ACT
    location = _token_location(file_path=Path("incidents/example.md"), token=token)

    # ASSERT
    assert location.line_start == 1
    assert location.line_end == 1


def test_token_location_clamps_invalid_line_end() -> None:
    # ARRANGE
    token = Token("fence", "code", 0)
    token.map = [10, 5]

    # ACT
    location = _token_location(file_path=Path("incidents/example.md"), token=token)

    # ASSERT
    assert location.line_start == 11
    assert location.line_end == 11


def test_build_field_locations_without_incident_card_returns_empty() -> None:
    # ARRANGE
    token = Token("fence", "code", 0)
    token.map = None
    token.content = "not_incident_card:\n  id: INC-2026-001\n"

    # ACT
    field_locations = _build_field_locations(file_path=Path("incidents/example.md"), token=token)

    # ASSERT
    assert field_locations == {}


def test_build_field_locations_ignores_nested_keys() -> None:
    # ARRANGE
    token = Token("fence", "code", 0)
    token.map = [0, 5]
    token.content = "incident_card:\n  title: Valid title\n    nested: ignored\n"

    # ACT
    field_locations = _build_field_locations(file_path=Path("incidents/example.md"), token=token)

    # ASSERT
    assert sorted(field_locations) == ["title"]


@settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(markdown_text=st.text(alphabet=st.characters(blacklist_characters="`"), max_size=200))
def test_parse_incident_file_arbitrary_markdown_without_yaml_is_parse_error(
    tmp_path: Path,
    markdown_text: str,
) -> None:
    # ARRANGE
    file_path = tmp_path / "generated.md"
    file_path.write_text(markdown_text, encoding="utf-8")

    # ACT / ASSERT
    with pytest.raises(ParseError) as error_info:
        parse_incident_file(file_path=file_path)

    assert error_info.value.issue_code == "INCIDENT_CARD_NOT_FOUND"


@settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(value=st.text(alphabet=st.characters(blacklist_characters="`\n:"), max_size=50))
def test_parse_incident_file_yaml_without_incident_card_is_not_card(tmp_path: Path, value: str) -> None:
    # ARRANGE
    file_path = tmp_path / "generated.md"
    file_path.write_text(f"```yaml\nnot_incident_card: {value!r}\n```\n", encoding="utf-8")

    # ACT / ASSERT
    with pytest.raises(ParseError) as error_info:
        parse_incident_file(file_path=file_path)

    assert error_info.value.issue_code == "INCIDENT_CARD_NOT_FOUND"


@settings(max_examples=6, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(prefix_lines=st.integers(min_value=0, max_value=5))
def test_parse_incident_file_prefix_lines_shift_field_locations(tmp_path: Path, prefix_lines: int) -> None:
    # ARRANGE
    file_path = tmp_path / "shifted.md"
    prefix = "".join("prefix\n" for _ in range(prefix_lines))
    file_path.write_text(
        prefix
        + """```yaml
incident_card:
  schema_version: 1
  id: INC-2026-120
  status: detected
  title: Payment API latency spike
  severity: medium
  environment: production
  service: payment-api
  commander: null
  detected_at: "2026-01-15T08:10:00Z"
  description: "Payment API latency exceeded the SLO for checkout requests."
```
""",
        encoding="utf-8",
    )

    # ACT
    parsed_card = parse_incident_file(file_path=file_path)

    # ASSERT
    assert parsed_card.field_locations["severity"].line_start == prefix_lines + 7
