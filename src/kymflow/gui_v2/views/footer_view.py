"""Footer view component for global status and selection summary.

This view is a thin NiceGUI wrapper that renders:
- current file / channel / ROI summary
- a "last event" status line
- a compact progress bar for long-running tasks

The view does not emit events; it is updated by FooterController.
"""

from __future__ import annotations

from typing import Optional

from nicegui import ui


class FooterView:
    """Compact one-line footer with selection, status, and progress."""

    def __init__(self) -> None:
        self._selection_label: Optional[ui.label] = None
        self._status_label: Optional[ui.label] = None
        self._progress_bar: Optional[ui.linear_progress] = None
        self._progress_label: Optional[ui.label] = None

    def render(self) -> None:
        """Create the footer UI inside a NiceGUI ui.footer container."""
        self._selection_label = None
        self._status_label = None
        self._progress_bar = None
        self._progress_label = None

        with ui.footer().classes(
            "w-full px-3 py-1 text-xs flex items-center justify-between bg-gray-900 text-gray-200"
        ):
            with ui.row().classes("items-center gap-2 min-w-0"):
                self._selection_label = ui.label("").classes(
                    "truncate max-w-[320px]"
                )

            with ui.row().classes("items-center gap-2 min-w-0"):
                self._status_label = ui.label("").classes(
                    "truncate max-w-[420px] text-gray-300"
                )

            with ui.row().classes("items-center gap-2"):
                self._progress_bar = ui.linear_progress(
                    value=0.0
                ).classes("w-32").props("rounded")
                self._progress_label = ui.label("").classes("text-gray-300")

        # Initial visibility/state
        self.set_selection_summary(None, None, None)
        self.set_last_event("")
        self.set_progress(running=False, progress=0.0, message="")

    def set_selection_summary(
        self,
        file_name: Optional[str],
        channel_label: Optional[str],
        roi_id: Optional[int],
    ) -> None:
        """Update left-hand selection summary."""
        if self._selection_label is None:
            return

        parts: list[str] = []
        if file_name:
            parts.append(file_name)
        if channel_label:
            parts.append(channel_label)
        if roi_id is not None:
            parts.append(f"ROI #{roi_id}")

        text = " · ".join(parts) if parts else ""
        self._selection_label.text = text

    def set_last_event(self, text: str) -> None:
        """Update center 'last event' label."""
        if self._status_label is None:
            return
        self._status_label.text = text or ""

    def set_progress(self, *, running: bool, progress: float, message: str) -> None:
        """Update right-hand progress bar and label from TaskState."""
        if self._progress_bar is None or self._progress_label is None:
            return

        # Clamp progress for safety
        clamped = max(0.0, min(1.0, float(progress)))
        self._progress_bar.value = clamped
        self._progress_label.text = message or ""

        # Show when running, or when there is a non-zero progress with a message
        if running or (clamped > 0.0 and bool(message)):
            self._progress_bar.visible = True
            self._progress_label.visible = True
        else:
            self._progress_bar.visible = False
            self._progress_label.visible = False
            self._progress_bar.value = 0.0

