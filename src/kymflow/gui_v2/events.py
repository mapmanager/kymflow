"""Event definitions for file selection.

This module defines events emitted by UI components when users interact
with file selection controls (e.g., clicking rows in the file table).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SelectionOrigin(str, Enum):
    """Origin of a selection change (prevents feedback loops).

    Used to track where a selection change originated so that components
    can avoid creating feedback loops when updating UI in response to
    state changes.

    Values:
        FILE_TABLE: Selection originated from user clicking in the file table.
        EXTERNAL: Selection originated from external source (e.g., programmatic update).
        RESTORE: Selection originated from restoring saved selection on page load.
    """

    FILE_TABLE = "file_table"
    EXTERNAL = "external"
    RESTORE = "restore"


@dataclass(frozen=True, slots=True)
class FileSelected:
    """Single file selection event.

    Emitted when a user selects a single file (typically from the file table).
    The origin indicates where the selection came from, allowing handlers
    to prevent feedback loops.

    Attributes:
        path: Selected file path as string, or None if selection cleared.
        origin: SelectionOrigin indicating where this selection came from.
    """

    path: str | None
    origin: SelectionOrigin


@dataclass(frozen=True, slots=True)
class FilesSelected:
    """Multi-file selection event.

    Emitted when a user selects multiple files (typically from the file table
    in multi-select mode). Currently, AppState only supports single selection,
    so this is converted to FileSelected with the first path.

    Attributes:
        paths: List of selected file paths.
        origin: SelectionOrigin indicating where this selection came from.
    """

    paths: list[str]
    origin: SelectionOrigin
