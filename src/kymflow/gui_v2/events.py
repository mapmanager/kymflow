# src/kymflow/gui_v2/events.py
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SelectionOrigin(str, Enum):
    """Where a selection change originated (prevents feedback loops)."""

    FILE_TABLE = "file_table"
    EXTERNAL = "external"
    RESTORE = "restore"


@dataclass(frozen=True, slots=True)
class FileSelected:
    """Single row selection from the file table."""

    path: str | None
    origin: SelectionOrigin


@dataclass(frozen=True, slots=True)
class FilesSelected:
    """Multi-row selection from the file table."""

    paths: list[str]
    origin: SelectionOrigin
