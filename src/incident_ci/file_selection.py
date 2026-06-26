from fnmatch import fnmatchcase
from pathlib import Path
from typing import List, Sequence, Set

from incident_ci.config import IncidentCIConfig
from incident_ci.exceptions import InputError

MAX_CHANGED_FILES_SIZE_BYTES = 1_048_576


def read_changed_files(files_path: Path) -> List[Path]:
    """Read changed file paths from text file."""

    if not files_path.exists():
        raise InputError(f"Changed files list does not exist: {files_path}")

    if not files_path.is_file():
        raise InputError(f"Changed files path is not a file: {files_path}")

    try:
        file_stat = files_path.stat()
    except OSError as error:
        raise InputError(f"Cannot stat changed files list: {files_path}") from error

    if file_stat.st_size > MAX_CHANGED_FILES_SIZE_BYTES:
        raise InputError(f"Changed files list is too large: {files_path}")

    try:
        file_text = files_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise InputError(f"Cannot read changed files list: {files_path}") from error

    changed_files: List[Path] = []
    for line in file_text.splitlines():
        normalized_line = line.strip()
        if normalized_line != "":
            changed_files.append(Path(normalized_line))

    return changed_files


def require_incident_card(labels: Sequence[str], config: IncidentCIConfig) -> bool:
    """Return whether incident card is required for PR labels."""

    normalized_labels = _normalized_label_set(labels=labels)

    if _has_any_label(labels=normalized_labels, candidates=config.exempt_labels):
        return False

    return _has_any_label(labels=normalized_labels, candidates=config.required_labels)


def has_exempt_label(labels: Sequence[str], config: IncidentCIConfig) -> bool:
    """Return whether labels include an exemption label."""

    normalized_labels = _normalized_label_set(labels=labels)
    return _has_any_label(labels=normalized_labels, candidates=config.exempt_labels)


def select_incident_files(changed_files: Sequence[Path], config: IncidentCIConfig) -> List[Path]:
    """Select incident files by configured glob patterns."""

    selected_files: List[Path] = []
    seen_paths: Set[str] = set()

    for changed_file in changed_files:
        posix_path = _path_to_posix(changed_file)
        path_parts = _split_posix_path(posix_path)
        if _has_parent_reference(path_parts=path_parts):
            continue

        if posix_path in seen_paths:
            continue

        if _matches_any_pattern(posix_path=posix_path, patterns=config.incident_file_globs):
            selected_files.append(Path(posix_path))
            seen_paths.add(posix_path)

    return selected_files


def _normalized_label_set(labels: Sequence[str]) -> Set[str]:
    normalized_labels: Set[str] = set()
    for label in labels:
        normalized_label = label.strip().lower()
        if normalized_label != "":
            normalized_labels.add(normalized_label)

    return normalized_labels


def _has_any_label(labels: Set[str], candidates: Sequence[str]) -> bool:
    return any(candidate in labels for candidate in candidates)


def _matches_any_pattern(posix_path: str, patterns: Sequence[str]) -> bool:
    path_parts = _split_posix_path(posix_path)
    for pattern in patterns:
        pattern_parts = _split_posix_path(pattern.replace("\\", "/"))
        if _match_path_parts(path_parts=path_parts, pattern_parts=pattern_parts):
            return True

    return False


def _match_path_parts(path_parts: Sequence[str], pattern_parts: Sequence[str]) -> bool:
    current_indexes = _expand_double_star_indexes(indexes={0}, pattern_parts=pattern_parts)

    for path_part in path_parts:
        next_indexes: Set[int] = set()
        for pattern_index in current_indexes:
            if pattern_index >= len(pattern_parts):
                continue

            pattern_part = pattern_parts[pattern_index]
            if pattern_part == "**":
                next_indexes.add(pattern_index)
                continue

            if fnmatchcase(path_part, pattern_part):
                next_indexes.add(pattern_index + 1)

        current_indexes = _expand_double_star_indexes(indexes=next_indexes, pattern_parts=pattern_parts)

    pattern_end_index = len(pattern_parts)
    return pattern_end_index in current_indexes


def _expand_double_star_indexes(indexes: Set[int], pattern_parts: Sequence[str]) -> Set[int]:
    expanded_indexes = set(indexes)
    pending_indexes = list(indexes)

    while len(pending_indexes) > 0:
        pattern_index = pending_indexes.pop()
        if pattern_index >= len(pattern_parts):
            continue

        if pattern_parts[pattern_index] != "**":
            continue

        next_index = pattern_index + 1
        if next_index not in expanded_indexes:
            expanded_indexes.add(next_index)
            pending_indexes.append(next_index)

    return expanded_indexes


def _has_parent_reference(path_parts: Sequence[str]) -> bool:
    return "." in path_parts or ".." in path_parts


def _split_posix_path(path: str) -> List[str]:
    return [part for part in path.split("/") if part != ""]


def _path_to_posix(path: Path) -> str:
    if path.is_absolute():
        try:
            return path.relative_to(Path.cwd()).as_posix()
        except ValueError:
            return path.as_posix().lstrip("/")

    return str(path).replace("\\", "/")
