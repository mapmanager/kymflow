"""Event definitions for AppState change notifications.

This module defines events emitted by AppStateBridgeController when AppState
changes. These are state change notifications (not user intents), and are
used to update UI components when the underlying state changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kymflow.core.image_loaders.kym_image import KymImage
    from kymflow.gui.events import SelectionOrigin
else:
    from kymflow.core.image_loaders.kym_image import KymImage


@dataclass(frozen=True, slots=True)
class FileListChanged:
    """AppState file list change notification.

    Emitted by AppStateBridgeController when AppState.load_folder() completes
    and the file list is updated. Views (e.g., FileTableBindings) subscribe
    to this to update their UI when files are loaded.

    Attributes:
        files: Updated list of KymImage instances from AppState.
    """

    files: list[KymImage]


@dataclass(frozen=True, slots=True)
class SelectedFileChanged:
    """AppState selection change notification.

    Emitted by AppStateBridgeController when AppState.select_file() is called
    and the selected file changes. Views subscribe to this to update their
    UI when the selection changes.

    The origin is preserved from the AppState.select_file() call, allowing
    bindings to prevent feedback loops (e.g., ignoring FILE_TABLE origin
    to avoid re-selecting the table when selection came from the table).

    Attributes:
        file: Selected KymImage instance, or None if selection cleared.
        origin: SelectionOrigin indicating where the selection came from,
            or None if not specified.
    """

    file: KymImage | None
    origin: object | None  # SelectionOrigin | None, but using object to avoid circular import
