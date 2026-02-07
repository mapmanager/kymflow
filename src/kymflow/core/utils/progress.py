"""Core progress and cancellation primitives (UI-agnostic)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional


@dataclass(frozen=True)
class ProgressMessage:
    """Progress update emitted by core loaders.

    Args:
        phase: Logical phase name (e.g., "scan", "read_csv", "wrap", "done").
        done: Completed item count within the phase.
        total: Optional total item count; None when indeterminate.
        detail: Short, optional detail string.
        path: Optional path associated with the update.
    """

    phase: str
    done: int = 0
    total: Optional[int] = None
    detail: str = ""
    path: Optional[Path] = None


ProgressCallback = Callable[[ProgressMessage], None]


class CancelledError(Exception):
    """Raised when a core operation is cancelled."""
