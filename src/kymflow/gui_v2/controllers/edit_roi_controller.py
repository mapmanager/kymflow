"""Controller for handling edit ROI intent events from the UI."""

from __future__ import annotations

from kymflow.core.image_loaders.roi import RoiBounds
from kymflow.core.utils.logging import get_logger
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events import EditRoi, FileChanged, SelectionOrigin
from kymflow.gui_v2.state import AppState

logger = get_logger(__name__)


class EditRoiController:
    """Apply edit ROI intents to the underlying KymImage."""

    def __init__(self, app_state: AppState, bus: EventBus) -> None:
        self._app_state = app_state
        self._bus = bus
        bus.subscribe_intent(EditRoi, self._on_edit_roi)

    def _on_edit_roi(self, e: EditRoi) -> None:
        """Handle EditRoi intent event."""
        logger.debug("EditRoi intent roi_id=%s bounds=%s", e.roi_id, e.bounds)

        kym_file = self._app_state.get_file_by_path_or_selected(e.path)
        if kym_file is None:
            logger.warning("EditRoi: no file available (path=%s)", e.path)
            return

        # Check if ROI exists
        roi = kym_file.rois.get(e.roi_id)
        if roi is None:
            logger.warning(
                "EditRoi: ROI not found (roi_id=%s, path=%s)",
                e.roi_id,
                e.path,
            )
            return

        try:
            # Edit ROI bounds if provided
            if e.bounds is not None:
                kym_file.rois.edit_roi(e.roi_id, bounds=e.bounds)
                logger.debug("EditRoi: updated roi_id=%s with bounds=%s", e.roi_id, e.bounds)

            # Emit EditRoi state event
            self._bus.emit(
                EditRoi(
                    roi_id=e.roi_id,
                    bounds=e.bounds,
                    path=e.path,
                    origin=e.origin,
                    phase="state",
                )
            )

            # Emit FileChanged to refresh views (ROI bounds changed)
            self._bus.emit(
                FileChanged(
                    file=kym_file,
                    change_type="roi",
                    origin=SelectionOrigin.EXTERNAL,
                    phase="state",
                )
            )
        except ValueError as exc:
            logger.warning("EditRoi: failed to edit ROI: %s", exc)
