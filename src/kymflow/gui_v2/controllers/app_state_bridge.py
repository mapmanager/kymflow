"""Bridge between AppState callbacks and EventBus.

This module provides a controller that connects the legacy AppState callback
system to the new v2 EventBus, allowing v2 components to react to AppState
changes while maintaining AppState as the single source of truth.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kymflow.core.utils.logging import get_logger
from kymflow.gui_v2.state import AppState
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.client_utils import is_client_alive
from kymflow.gui_v2.events import (
    EventSelection,
    FileSelection,
    ROISelection,
    SelectionOrigin,
    ImageDisplayChange,
    MetadataUpdate,
)
from kymflow.gui_v2.events_state import (
    FileListChanged,
    ThemeChanged,
)

if TYPE_CHECKING:
    from kymflow.core.image_loaders.kym_image import KymImage

logger = get_logger(__name__)


class AppStateBridgeController:
    """Bridge AppState callbacks into the v2 EventBus.

    This controller subscribes to AppState callback registries and emits
    corresponding events on the EventBus. It checks client validity before
    emitting to prevent errors from stale callbacks.

    Flow:
        AppState.load_folder() → callback → emit FileListChanged
        AppState.select_file() → callback → emit FileSelection(phase="state")

    Attributes:
        _app_state: AppState instance (shared, process-level).
        _bus: EventBus instance (per-client).
    """

    def __init__(self, app_state: AppState, bus: EventBus) -> None:
        """Initialize the bridge controller.

        Subscribes to AppState callbacks. The callbacks remain registered
        for the lifetime of the AppState instance, but they check client
        validity before emitting events.

        Args:
            app_state: Shared AppState instance.
            bus: Per-client EventBus instance.
        """
        self._app_state: AppState = app_state
        self._bus: EventBus = bus

        # Register callbacks that will emit bus events
        self._app_state.on_file_list_changed(self._on_file_list_changed)
        self._app_state.on_selection_changed(self._on_selection_changed)
        self._app_state.on_roi_selection_changed(self._on_roi_selection_changed)
        self._app_state.on_event_selection_changed(self._on_event_selection_changed)
        self._app_state.on_theme_changed(self._on_theme_changed)
        self._app_state.on_image_display_changed(self._on_image_display_changed)
        self._app_state.on_metadata_changed(self._on_metadata_changed)

    def _on_file_list_changed(self) -> None:
        """Handle AppState file list change callback.

        Emits FileListChanged event with the current file list from AppState.
        Checks client validity before emitting to prevent errors from stale callbacks.
        """
        # Only emit if client is still alive
        if not is_client_alive():
            logger.debug(
                f"[bridge] Skipping FileListChanged emit - client deleted (bus={self._bus._client_id[:8]}...)"
            )
            return
        self._bus.emit(FileListChanged(files=list(self._app_state.files)))

    def _on_selection_changed(
        self, kym_file: KymImage | None, origin: SelectionOrigin | None
    ) -> None:
        """Handle AppState selection change callback.

        Emits FileSelection (phase="state") event with the current selection and origin.
        The origin is preserved through AppState so bindings can prevent
        feedback loops. Checks client validity before emitting.

        Args:
            kym_file: Selected KymImage instance, or None if nothing selected.
            origin: SelectionOrigin indicating where the selection came from, or None.
        """
        # Only emit if client is still alive
        if not is_client_alive():
            logger.debug(
                f"[bridge] Skipping FileSelection emit - client deleted (bus={self._bus._client_id[:8]}...)"
            )
            return

        # Convert origin to SelectionOrigin enum (None is valid)
        selection_origin = (
            origin if isinstance(origin, SelectionOrigin) else SelectionOrigin.EXTERNAL
        )

        # Derive path from file if available
        path = str(kym_file.path) if kym_file and hasattr(kym_file, "path") else None

        self._bus.emit(
            FileSelection(
                path=path,
                file=kym_file,
                origin=selection_origin,
                phase="state",
            )
        )

        # When select_file() is called, it automatically sets selected_roi_id
        # (first ROI if available, None otherwise). This doesn't trigger the
        # roi_selection_changed callback, so we need to emit ROISelection(phase="state")
        # here to notify viewers of the ROI change.
        if not is_client_alive():
            return
        self._bus.emit(
            ROISelection(
                roi_id=self._app_state.selected_roi_id,
                origin=SelectionOrigin.EXTERNAL,
                phase="state",
            )
        )

    def _on_roi_selection_changed(self, roi_id: int | None) -> None:
        """Handle AppState ROI selection change callback.

        Emits ROISelection(phase="state") event with the current ROI selection.
        Checks client validity before emitting.

        Args:
            roi_id: Selected ROI ID, or None if selection cleared.
        """
        # Only emit if client is still alive
        if not is_client_alive():
            logger.debug(
                f"[bridge] Skipping ROISelection emit - client deleted (bus={self._bus._client_id[:8]}...)"
            )
            return
        self._bus.emit(
            ROISelection(
                roi_id=roi_id,
                origin=SelectionOrigin.EXTERNAL,
                phase="state",
            )
        )

    def _on_event_selection_changed(
        self,
        event_id: str | None,
        roi_id: int | None,
        path: str | None,
        event,
        options,
        origin,
    ) -> None:
        """Handle AppState event selection change callback.

        Emits EventSelection(phase="state") event with the current selection.
        Checks client validity before emitting.
        """
        if not is_client_alive():
            logger.debug(
                f"[bridge] Skipping EventSelection emit - client deleted (bus={self._bus._client_id[:8]}...)"
            )
            return

        selection_origin = origin if origin is not None else SelectionOrigin.EXTERNAL
        self._bus.emit(
            EventSelection(
                event_id=event_id,
                roi_id=roi_id,
                path=path,
                event=event,
                options=options,
                origin=selection_origin,
                phase="state",
            )
        )

    def _on_theme_changed(self, theme) -> None:
        """Handle AppState theme change callback.

        Emits ThemeChanged event with the current theme mode.
        Checks client validity before emitting.

        Args:
            theme: ThemeMode (DARK or LIGHT).
        """
        # Only emit if client is still alive
        if not is_client_alive():
            logger.debug(
                f"[bridge] Skipping ThemeChanged emit - client deleted (bus={self._bus._client_id[:8]}...)"
            )
            return
        self._bus.emit(ThemeChanged(theme=theme))

    def _on_image_display_changed(self, params) -> None:
        """Handle AppState image display parameter change callback.

        Emits ImageDisplayChange(phase="state") event with the current display parameters.
        Checks client validity before emitting.

        Args:
            params: ImageDisplayParams containing colorscale, zmin, zmax, and origin.
        """
        # Only emit if client is still alive
        if not is_client_alive():
            logger.debug(
                f"[bridge] Skipping ImageDisplayChange emit - client deleted (bus={self._bus._client_id[:8]}...)"
            )
            return
        # State events always use EXTERNAL origin (they come from AppState, not UI)
        self._bus.emit(
            ImageDisplayChange(
                params=params,
                origin=SelectionOrigin.EXTERNAL,
                phase="state",
            )
        )

    def _on_metadata_changed(self, kym_file: KymImage) -> None:
        """Handle AppState metadata change callback.

        Emits MetadataUpdate(phase="state") event with the file whose metadata was updated.
        Note: We don't know which metadata type was updated, so we emit with empty fields.
        Views will refresh based on file selection.

        Args:
            kym_file: KymImage instance whose metadata was updated.
        """
        # Only emit if client is still alive
        if not is_client_alive():
            logger.debug(
                f"[bridge] Skipping MetadataUpdate emit - client deleted (bus={self._bus._client_id[:8]}...)"
            )
            return
        # Emit with empty fields - views will refresh from file
        self._bus.emit(
            MetadataUpdate(
                file=kym_file,
                metadata_type="experimental",  # Default, views will refresh both types
                fields={},
                origin=SelectionOrigin.EXTERNAL,
                phase="state",
            )
        )
