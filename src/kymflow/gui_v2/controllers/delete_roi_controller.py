"""Controller for handling delete ROI intent events from the UI."""

from __future__ import annotations

from kymflow.core.utils.logging import get_logger
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events import DeleteRoi, MetadataUpdate, SelectionOrigin
from kymflow.gui_v2.state import AppState

logger = get_logger(__name__)


class DeleteRoiController:
    """Apply delete ROI intents to the underlying KymImage."""

    def __init__(self, app_state: AppState, bus: EventBus) -> None:
        self._app_state = app_state
        self._bus = bus
        bus.subscribe_intent(DeleteRoi, self._on_delete_roi)

    def _on_delete_roi(self, e: DeleteRoi) -> None:
        """Handle DeleteRoi intent event."""
        logger.debug("DeleteRoi intent roi_id=%s", e.roi_id)

        kym_file = None
        if e.path is not None:
            for f in self._app_state.files:
                if str(f.path) == e.path:
                    kym_file = f
                    break
        if kym_file is None:
            kym_file = self._app_state.selected_file
        if kym_file is None:
            logger.warning("DeleteRoi: no file available (path=%s)", e.path)
            return

        # Check if ROI exists before deleting
        roi = kym_file.rois.get(e.roi_id)
        if roi is None:
            logger.warning(
                "DeleteRoi: ROI not found (roi_id=%s, path=%s)",
                e.roi_id,
                e.path,
            )
            return

        # Delete the ROI
        kym_file.rois.delete(e.roi_id)
        logger.debug("DeleteRoi: deleted roi_id=%s", e.roi_id)

        # Update selection if deleted ROI was selected
        if self._app_state.selected_roi_id == e.roi_id:
            remaining_roi_ids = kym_file.rois.get_roi_ids()
            if remaining_roi_ids:
                # Select first remaining ROI
                self._app_state.select_roi(remaining_roi_ids[0])
            else:
                # No ROIs left, clear selection
                self._app_state.select_roi(None)

        self._bus.emit(
            DeleteRoi(
                roi_id=e.roi_id,
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
