"""Event definitions for folder selection.

This module defines events emitted when users select or change folders
in the folder selector UI.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FolderChosen:
    """Folder selection event.

    Emitted when a user selects a folder (e.g., via folder selector widget).
    This triggers folder scanning and file list updates in AppState.

    Attributes:
        folder: Selected folder path as string.
    """

    folder: str
