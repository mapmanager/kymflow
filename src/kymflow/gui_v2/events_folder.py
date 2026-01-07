# src/kymflow/gui_v2/events_folder.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FolderChosen:
    """User chose a folder path (rescan occurs when user presses Reload/Choose)."""

    folder: str
