from pathlib import Path

import pytest

from incident_ci.config import IncidentCIConfig
from incident_ci.exceptions import InputError
from incident_ci.file_selection import (
    has_exempt_label,
    read_changed_files,
    require_incident_card,
    select_incident_files,
)


def _config() -> IncidentCIConfig:
    return IncidentCIConfig(
        schema_version=1,
        required_labels=["incident"],
        exempt_labels=["incident-card-exempt"],
        strict=True,
        incident_file_globs=["incidents/**/*.md"],
        allowed_services=["payment-api"],
    )


def test_require_incident_card_required_label() -> None:
    # ARRANGE
    config = _config()

    # ACT
    required = require_incident_card(labels=[" incident "], config=config)

    # ASSERT
    assert required is True


def test_require_incident_card_matches_label_case_insensitively() -> None:
    # ARRANGE
    config = _config()

    # ACT
    required = require_incident_card(labels=[" Incident "], config=config)

    # ASSERT
    assert required is True


def test_require_incident_card_exempt_label_has_priority() -> None:
    # ARRANGE
    config = _config()

    # ACT
    required = require_incident_card(labels=["incident", "incident-card-exempt"], config=config)

    # ASSERT
    assert required is False


def test_has_exempt_label_normalizes_labels() -> None:
    # ARRANGE
    config = _config()

    # ACT
    exempt = has_exempt_label(labels=[" incident-card-exempt "], config=config)

    # ASSERT
    assert exempt is True


def test_require_incident_card_no_labels() -> None:
    # ARRANGE
    config = _config()

    # ACT
    required = require_incident_card(labels=[], config=config)

    # ASSERT
    assert required is False


def test_select_incident_files_matches_direct_and_nested_paths() -> None:
    # ARRANGE
    config = _config()
    changed_files = [
        Path("docs/INC-2026-001.md"),
        Path("incidents/INC-2026-001.md"),
        Path("incidents/nested/INC-2026-002.md"),
    ]

    # ACT
    selected_files = select_incident_files(changed_files=changed_files, config=config)

    # ASSERT
    assert selected_files == [
        Path("incidents/INC-2026-001.md"),
        Path("incidents/nested/INC-2026-002.md"),
    ]


def test_select_incident_files_matches_deep_recursive_glob_paths() -> None:
    # ARRANGE
    config = _config()
    changed_files = [
        Path("incidents/a/b/c/INC-2026-003.md"),
    ]

    # ACT
    selected_files = select_incident_files(changed_files=changed_files, config=config)

    # ASSERT
    assert selected_files == [Path("incidents/a/b/c/INC-2026-003.md")]


def test_select_incident_files_matches_absolute_paths_inside_cwd() -> None:
    # ARRANGE
    config = _config()
    changed_files = [
        Path.cwd() / "incidents" / "INC-2026-001.md",
    ]

    # ACT
    selected_files = select_incident_files(changed_files=changed_files, config=config)

    # ASSERT
    assert selected_files == [Path("incidents/INC-2026-001.md")]


def test_select_incident_files_ignores_parent_references() -> None:
    # ARRANGE
    config = _config()
    changed_files = [
        Path("incidents/../README.md"),
        Path("incidents/INC-2026-001.md"),
    ]

    # ACT
    selected_files = select_incident_files(changed_files=changed_files, config=config)

    # ASSERT
    assert selected_files == [Path("incidents/INC-2026-001.md")]


def test_select_incident_files_handles_deep_recursive_glob_without_recursion_error() -> None:
    # ARRANGE
    config = _config()
    nested_path = "/".join(["nested"] * 1_050)
    file_path = Path(f"incidents/{nested_path}/INC-2026-001.md")
    changed_files = [file_path]

    # ACT
    selected_files = select_incident_files(changed_files=changed_files, config=config)

    # ASSERT
    assert selected_files == [file_path]


def test_select_incident_files_single_star_does_not_cross_directory_boundary() -> None:
    # ARRANGE
    config = IncidentCIConfig(
        schema_version=1,
        required_labels=["incident"],
        exempt_labels=[],
        strict=True,
        incident_file_globs=["incidents/*.md"],
        allowed_services=["payment-api"],
    )
    changed_files = [
        Path("incidents/INC-2026-001.md"),
        Path("incidents/nested/INC-2026-002.md"),
    ]

    # ACT
    selected_files = select_incident_files(changed_files=changed_files, config=config)

    # ASSERT
    assert selected_files == [Path("incidents/INC-2026-001.md")]


def test_select_incident_files_removes_duplicates_and_preserves_order() -> None:
    # ARRANGE
    config = _config()
    changed_files = [
        Path("incidents/INC-2026-002.md"),
        Path("incidents/INC-2026-001.md"),
        Path("incidents/INC-2026-002.md"),
    ]

    # ACT
    selected_files = select_incident_files(changed_files=changed_files, config=config)

    # ASSERT
    assert selected_files == [
        Path("incidents/INC-2026-002.md"),
        Path("incidents/INC-2026-001.md"),
    ]


def test_read_changed_files_ignores_empty_lines(tmp_path: Path) -> None:
    # ARRANGE
    changed_files_path = tmp_path / "changed-files.txt"
    changed_files_path.write_text("incidents/INC-2026-001.md\n\n docs/readme.md \n", encoding="utf-8")

    # ACT
    changed_files = read_changed_files(files_path=changed_files_path)

    # ASSERT
    assert changed_files == [Path("incidents/INC-2026-001.md"), Path("docs/readme.md")]


def test_read_changed_files_invalid_utf8_raises_input_error(tmp_path: Path) -> None:
    # ARRANGE
    changed_files_path = tmp_path / "changed-files.txt"
    changed_files_path.write_bytes(b"\xff")

    # ACT / ASSERT
    with pytest.raises(InputError):
        read_changed_files(files_path=changed_files_path)


def test_read_changed_files_too_large_raises_input_error(tmp_path: Path) -> None:
    # ARRANGE
    changed_files_path = tmp_path / "changed-files.txt"
    changed_files_path.write_text("x" * 1_048_577, encoding="utf-8")

    # ACT / ASSERT
    with pytest.raises(InputError):
        read_changed_files(files_path=changed_files_path)
