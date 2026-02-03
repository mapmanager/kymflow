"""Event definitions for path selection (folder or file).

This module defines events emitted when users select or change paths
(folders or files) in the folder selector UI.
"""

from __future__ import annotations

from dataclasses import dataclass

from kymflow.gui_v2.events import EventPhase


@dataclass(frozen=True, slots=True)
class SelectPathEvent:
    """Path selection event (intent or state phase).

    Emitted when a user selects a path (folder or file) via the folder selector widget.
    This triggers path scanning and file list updates in AppState.

    For intent phase:
        - Emitted by FolderSelectorView when user selects a path
        - Handled by FolderController which validates and loads the path

    For state phase:
        - Emitted by FolderController after successful path load
        - Subscribed to by FolderSelectorView to sync UI

    Attributes:
        new_path: Selected path (folder or file) as string.
        depth: Optional folder depth. If provided, sets app_state.folder_depth
            before loading (for folders only). If None, uses current app_state.folder_depth.
        phase: Event phase - "intent" or "state".
    """

    new_path: str
    depth: int | None = None
    phase: EventPhase = "intent"


@dataclass(frozen=True, slots=True)
class CancelSelectPathEvent:
    """Path selection cancellation event.

    Emitted when a SelectPathEvent intent is cancelled (e.g., user cancels unsaved changes dialog
    or path does not exist). This allows the view to revert the UI dropdown to the previous selection.

    Attributes:
        previous_path: Path to revert to (the path before the cancelled selection).
    """

    previous_path: str