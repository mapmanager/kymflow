"""Bindings for the always-visible main contrast widget."""

from __future__ import annotations

from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.client_utils import safe_call
from kymflow.gui_v2.events import FileSelection, ImageDisplayChange, ROISelection
from kymflow.gui_v2.events_state import ThemeChanged
from kymflow.gui_v2.views.main_contrast_widget_view import MainContrastWidgetView


class MainContrastWidgetBindings:
    """Bind state events to `MainContrastWidgetView`."""

    def __init__(self, bus: EventBus, view: MainContrastWidgetView) -> None:
        self._bus = bus
        self._view = view
        self._subscribed = False

        bus.subscribe_state(FileSelection, self._on_file_selection_changed)
        bus.subscribe_state(ROISelection, self._on_roi_selection_changed)
        bus.subscribe_state(ImageDisplayChange, self._on_image_display_changed)
        bus.subscribe(ThemeChanged, self._on_theme_changed)
        self._subscribed = True

    def teardown(self) -> None:
        if not self._subscribed:
            return
        self._bus.unsubscribe_state(FileSelection, self._on_file_selection_changed)
        self._bus.unsubscribe_state(ROISelection, self._on_roi_selection_changed)
        self._bus.unsubscribe_state(ImageDisplayChange, self._on_image_display_changed)
        self._bus.unsubscribe(ThemeChanged, self._on_theme_changed)
        self._subscribed = False

    def _on_file_selection_changed(self, e: FileSelection) -> None:
        safe_call(self._view.set_selected_file, e.file)

    def _on_roi_selection_changed(self, e: ROISelection) -> None:
        safe_call(self._view.set_selected_roi, e.roi_id)

    def _on_image_display_changed(self, e: ImageDisplayChange) -> None:
        safe_call(self._view.set_image_display, e.params)

    def _on_theme_changed(self, e: ThemeChanged) -> None:
        safe_call(self._view.set_theme, e.theme)

