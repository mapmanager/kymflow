"""Event definitions for file selection.

This module defines events emitted by UI components when users interact
with file selection controls (e.g., clicking rows in the file table).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from kymflow.core.image_loaders.kym_image import KymImage

EventPhase = Literal["intent", "state"]


class SelectionOrigin(str, Enum):
    """Origin of a selection change (prevents feedback loops).

    Used to track where a selection change originated so that components
    can avoid creating feedback loops when updating UI in response to
    state changes.

    Values:
        FILE_TABLE: Selection originated from user clicking in the file table.
        IMAGE_VIEWER: Selection originated from image/line viewer (e.g., ROI dropdown).
        EXTERNAL: Selection originated from external source (e.g., programmatic update).
        RESTORE: Selection originated from restoring saved selection on page load.
    """

    FILE_TABLE = "file_table"
    IMAGE_VIEWER = "image_viewer"
    EXTERNAL = "external"
    RESTORE = "restore"


@dataclass(frozen=True, slots=True)
class FileSelection:
    """File selection event (intent or state phase).

    This event is used for both intent (user wants to select) and state
    (selection has changed) phases. The phase field determines which handlers
    receive the event.

    For intent phase:
        - path is set (file path as string)
        - file is None
        - Emitted by views when user selects a file

    For state phase:
        - file is set (KymImage instance)
        - path can be derived from file.path
        - Emitted by AppStateBridge when AppState changes

    Attributes:
        path: File path as string, or None. Set in intent phase.
        file: KymImage instance, or None. Set in state phase.
        origin: SelectionOrigin indicating where the selection came from.
        phase: Event phase - "intent" or "state".
    """

    path: str | None
    file: "KymImage | None"
    origin: SelectionOrigin
    phase: EventPhase


@dataclass(frozen=True, slots=True)
class ROISelection:
    """ROI selection event (intent or state phase).

    This event is used for both intent (user wants to select ROI) and state
    (ROI selection has changed) phases. The phase field determines which handlers
    receive the event.

    For intent phase:
        - roi_id is set (or None to clear)
        - Emitted by views when user selects an ROI (e.g., from dropdown)

    For state phase:
        - roi_id is set (or None if cleared)
        - Emitted by AppStateBridge when AppState changes

    Attributes:
        roi_id: ROI ID, or None if selection cleared.
        origin: SelectionOrigin indicating where the selection came from.
        phase: Event phase - "intent" or "state".
    """

    roi_id: int | None
    origin: SelectionOrigin
    phase: EventPhase
