import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, TypeAlias, cast

import yaml
from markdown_it import MarkdownIt
from markdown_it.token import Token
from pydantic import BaseModel, ConfigDict, Field
from yaml import YAMLError

from incident_ci.constants import MAX_MARKDOWN_FILE_SIZE_BYTES, MAX_YAML_BLOCK_SIZE_BYTES
from incident_ci.exceptions import InputError, ParseError
from incident_ci.models import SourceLocation

FieldLineIndex: TypeAlias = Mapping[str, SourceLocation]

YAML_INFO_STRINGS = {"yaml", "yml"}
INCIDENT_CARD_KEY = "incident_card"
TOP_LEVEL_FIELD_RE = re.compile(r"^  ([A-Za-z_][A-Za-z0-9_]*):")


class ParsedIncidentCard(BaseModel):
    """Parsed incident card payload with source metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    file_path: str = Field(min_length=1)
    payload: Dict[str, object]
    card_location: SourceLocation
    field_locations: Dict[str, SourceLocation]


@dataclass(frozen=True)
class _IncidentYamlBlock:
    document: Mapping[str, Any]
    token: Token
    block_location: SourceLocation


def parse_incident_file(file_path: Path) -> ParsedIncidentCard:
    """Parse incident card from Markdown file."""

    _check_markdown_file(file_path=file_path)
    markdown_text = _read_markdown_file(file_path=file_path)
    tokens = MarkdownIt("commonmark").parse(markdown_text)
    incident_blocks = _find_incident_yaml_blocks(file_path=file_path, tokens=tokens)

    if len(incident_blocks) == 0:
        raise ParseError(
            message=f"Incident card not found in file: {file_path}",
            issue_code="INCIDENT_CARD_NOT_FOUND",
            file_path=str(file_path),
            line_start=1,
            line_end=1,
        )

    if len(incident_blocks) > 1:
        second_block = incident_blocks[1]
        raise ParseError(
            message=f"Multiple incident cards found in file: {file_path}",
            issue_code="MULTIPLE_INCIDENT_CARDS",
            file_path=str(file_path),
            line_start=second_block.block_location.line_start,
            line_end=second_block.block_location.line_end,
        )

    incident_block = incident_blocks[0]
    raw_payload = incident_block.document[INCIDENT_CARD_KEY]
    if not isinstance(raw_payload, dict):
        raise ParseError(
            message=f"incident_card must be a mapping: {file_path}",
            issue_code="YAML_ROOT_INVALID",
            file_path=str(file_path),
            line_start=incident_block.block_location.line_start,
            line_end=incident_block.block_location.line_end,
        )

    payload = cast(Dict[str, object], raw_payload)
    field_locations = _build_field_locations(file_path=file_path, token=incident_block.token)
    return ParsedIncidentCard(
        file_path=str(file_path),
        payload=payload,
        card_location=incident_block.block_location,
        field_locations=field_locations,
    )


def load_yaml_document(yaml_text: str, file_path: Path) -> Mapping[str, Any]:
    """Load YAML document safely."""

    try:
        loaded_data = yaml.safe_load(yaml_text)
    except YAMLError as error:
        raise ParseError(
            message=f"Invalid YAML in incident file: {file_path}",
            issue_code="YAML_INVALID",
            file_path=str(file_path),
            line_start=1,
            line_end=1,
        ) from error

    if not isinstance(loaded_data, dict):
        raise ParseError(
            message=f"YAML root must be a mapping: {file_path}",
            issue_code="YAML_ROOT_INVALID",
            file_path=str(file_path),
            line_start=1,
            line_end=1,
        )

    return cast(Mapping[str, Any], loaded_data)


def _check_markdown_file(file_path: Path) -> None:
    if not file_path.exists():
        raise InputError(f"Incident file does not exist: {file_path}")

    if not file_path.is_file():
        raise InputError(f"Incident path is not a file: {file_path}")

    try:
        file_stat = file_path.stat()
    except OSError as error:
        raise InputError(f"Cannot stat incident file: {file_path}") from error

    if file_stat.st_size > MAX_MARKDOWN_FILE_SIZE_BYTES:
        raise ParseError(
            message=(
                f"Incident file is too large: {file_path} size={file_stat.st_size} limit={MAX_MARKDOWN_FILE_SIZE_BYTES}"
            ),
            issue_code="FILE_TOO_LARGE",
            file_path=str(file_path),
            line_start=1,
            line_end=1,
        )


def _read_markdown_file(file_path: Path) -> str:
    try:
        return file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise InputError(f"Cannot read incident file: {file_path}") from error


def _find_incident_yaml_blocks(file_path: Path, tokens: Sequence[Token]) -> List[_IncidentYamlBlock]:
    incident_blocks: List[_IncidentYamlBlock] = []

    for token in tokens:
        if token.type != "fence":
            continue

        info = token.info.strip().lower()
        if info not in YAML_INFO_STRINGS:
            continue

        if not _has_top_level_incident_card_key(yaml_text=token.content):
            continue

        block_location = _token_location(file_path=file_path, token=token)
        yaml_size = len(token.content.encode("utf-8"))
        if yaml_size > MAX_YAML_BLOCK_SIZE_BYTES:
            raise ParseError(
                message=(
                    f"YAML block is too large in incident file: {file_path} "
                    f"size={yaml_size} limit={MAX_YAML_BLOCK_SIZE_BYTES}"
                ),
                issue_code="YAML_BLOCK_TOO_LARGE",
                file_path=str(file_path),
                line_start=block_location.line_start,
                line_end=block_location.line_end,
            )

        try:
            document = load_yaml_document(yaml_text=token.content, file_path=file_path)
        except ParseError as error:
            raise ParseError(
                message=error.message,
                issue_code=error.issue_code,
                file_path=str(file_path),
                line_start=block_location.line_start,
                line_end=block_location.line_end,
                field_path=error.field_path,
            ) from error

        if INCIDENT_CARD_KEY in document:
            incident_blocks.append(
                _IncidentYamlBlock(document=document, token=token, block_location=block_location),
            )

    return incident_blocks


def _has_top_level_incident_card_key(yaml_text: str) -> bool:
    key_prefix = f"{INCIDENT_CARD_KEY}:"
    for line in yaml_text.splitlines():
        if line.startswith(key_prefix):
            return True

    return False


def _token_location(file_path: Path, token: Token) -> SourceLocation:
    if token.map is None:
        return SourceLocation(file_path=str(file_path), line_start=1, line_end=1)

    line_start = token.map[0] + 1
    line_end = token.map[1]
    if line_end < line_start:
        line_end = line_start

    return SourceLocation(file_path=str(file_path), line_start=line_start, line_end=line_end)


def _build_field_locations(file_path: Path, token: Token) -> Dict[str, SourceLocation]:
    field_locations: Dict[str, SourceLocation] = {}
    content_start_line = 1 if token.map is None else token.map[0] + 2

    lines = token.content.splitlines()
    incident_card_line_index = _find_incident_card_line_index(lines=lines)
    if incident_card_line_index is None:
        return field_locations

    for local_line_number, line in enumerate(lines[incident_card_line_index + 1 :], start=incident_card_line_index + 1):
        match = TOP_LEVEL_FIELD_RE.match(line)
        if match is None:
            continue

        field_name = match.group(1)
        absolute_line = content_start_line + local_line_number
        field_locations[field_name] = SourceLocation(
            file_path=str(file_path),
            line_start=absolute_line,
            line_end=absolute_line,
        )

    return field_locations


def _find_incident_card_line_index(lines: Sequence[str]) -> Optional[int]:
    for local_line_number, line in enumerate(lines):
        if line.strip() == f"{INCIDENT_CARD_KEY}:":
            return local_line_number

    return None
