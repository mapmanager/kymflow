"""Bindings between KymEventView and event bus (state → view updates)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.client_utils import safe_call
from kymflow.gui_v2.events import EventSelection, FileSelection, ROISelection, SelectionOrigin
from kymflow.gui_v2.views.kym_event_view import KymEventView

if TYPE_CHECKING:
    from kymflow.core.image_loaders.kym_image import KymImage


class KymEventBindings:
    """Bind KymEventView to event bus for state → view updates."""

    def __init__(self, bus: EventBus, view: KymEventView) -> None:
        self._bus: EventBus = bus
        self._view: KymEventView = view
        self._subscribed: bool = False
        self._current_file: KymImage | None = None

        bus.subscribe_state(FileSelection, self._on_file_selection_changed)
        bus.subscribe_state(ROISelection, self._on_roi_selection_changed)
        bus.subscribe_state(EventSelection, self._on_event_selection_changed)
        self._subscribed = True

    def teardown(self) -> None:
        if not self._subscribed:
            return
        self._bus.unsubscribe_state(FileSelection, self._on_file_selection_changed)
        self._bus.unsubscribe_state(ROISelection, self._on_roi_selection_changed)
        self._bus.unsubscribe_state(EventSelection, self._on_event_selection_changed)
        self._subscribed = False

    def _on_file_selection_changed(self, e: FileSelection) -> None:
        self._current_file = e.file
        if e.file is None:
            safe_call(self._view.set_events, [])
            safe_call(self._view.set_selected_event_ids, [], origin=SelectionOrigin.EXTERNAL)
            return
        report = e.file.get_kym_analysis().get_velocity_report()
        safe_call(self._view.set_events, report)

    def _on_roi_selection_changed(self, e: ROISelection) -> None:
        safe_call(self._view.set_selected_roi, e.roi_id)

    def _on_event_selection_changed(self, e: EventSelection) -> None:
        if e.origin == SelectionOrigin.EVENT_TABLE:
            return
        if e.event_id is None:
            safe_call(self._view.set_selected_event_ids, [], origin=SelectionOrigin.EXTERNAL)
        else:
            safe_call(
                self._view.set_selected_event_ids,
                [e.event_id],
                origin=SelectionOrigin.EXTERNAL,
            )
