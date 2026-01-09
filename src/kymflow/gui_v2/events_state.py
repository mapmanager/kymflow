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
    from kymflow.core.plotting.theme import ThemeMode
    from kymflow.gui.state import ImageDisplayParams
else:
    from kymflow.core.image_loaders.kym_image import KymImage
    from kymflow.core.plotting.theme import ThemeMode
    from kymflow.gui.state import ImageDisplayParams


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
class ThemeChanged:
    """AppState theme change notification.

    Emitted by AppStateBridgeController when AppState.set_theme() is called
    and the theme mode changes. Views subscribe to this to update their
    UI when the theme changes.

    Attributes:
        theme: New theme mode (DARK or LIGHT).
    """

    theme: ThemeMode


@dataclass(frozen=True, slots=True)
class ImageDisplayChanged:
    """AppState image display parameter change notification.

    Emitted by AppStateBridgeController when AppState.set_image_display() is called
    and image display parameters (colorscale, contrast) change. Views subscribe
    to this to update their UI when display parameters change.

    Attributes:
        params: ImageDisplayParams containing colorscale, zmin, zmax, and origin.
    """

    params: ImageDisplayParams


@dataclass(frozen=True, slots=True)
class MetadataChanged:
    """AppState metadata change notification.

    Emitted by AppStateBridgeController when AppState.update_metadata() is called
    and metadata for a file is updated. Views subscribe to this to refresh
    their UI when file metadata changes.

    Attributes:
        file: KymImage instance whose metadata was updated.
    """

    file: KymImage
