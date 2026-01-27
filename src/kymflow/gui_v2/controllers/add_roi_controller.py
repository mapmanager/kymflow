"""Controller for handling add ROI intent events from the UI."""

from __future__ import annotations

from kymflow.core.utils.logging import get_logger
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events import AddRoi, MetadataUpdate, SelectionOrigin
from kymflow.gui_v2.state import AppState

logger = get_logger(__name__)


class AddRoiController:
    """Apply add ROI intents to the underlying KymImage."""

    def __init__(self, app_state: AppState, bus: EventBus) -> None:
        self._app_state = app_state
        self._bus = bus
        bus.subscribe_intent(AddRoi, self._on_add_roi)

    def _on_add_roi(self, e: AddRoi) -> None:
        """Handle AddRoi intent event."""
        logger.debug("AddRoi intent path=%s", e.path)

        kym_file = None
        if e.path is not None:
            for f in self._app_state.files:
                if str(f.path) == e.path:
                    kym_file = f
                    break
        if kym_file is None:
            kym_file = self._app_state.selected_file
        if kym_file is None:
            logger.warning("AddRoi: no file available (path=%s)", e.path)
            return

        try:
            # Create ROI with default full-image bounds (bounds=None)
            roi = kym_file.rois.create_roi()
            logger.debug("AddRoi: created roi_id=%s", roi.id)

            # Select the newly created ROI
            self._app_state.select_roi(roi.id)

            self._bus.emit(
                AddRoi(
                    roi_id=roi.id,
                    path=e.path,
                    origin=e.origin,
                    phase="state",
                )
            )

            # Refresh file table metadata (ROI count changed)
            self._bus.emit(
                MetadataUpdate(
                    file=kym_file,
                    metadata_type="experimental",
                    fields={},
                    origin=SelectionOrigin.EXTERNAL,
                    phase="state",
                )
            )
        except ValueError as exc:
            logger.warning("AddRoi: failed to create ROI: %s", exc)
