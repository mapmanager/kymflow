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
        depth: Optional folder depth. If provided, sets app_state.folder_depth
            before loading. If None, uses current app_state.folder_depth.
    """

    folder: str
    depth: int | None = None