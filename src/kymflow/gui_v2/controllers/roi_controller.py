"""Unified controller for ROI CRUD and selection intents.

This controller consolidates the responsibilities of the legacy AddRoiController,
EditRoiController, DeleteRoiController, and ROISelectionController into a single
class while preserving the existing event contracts.

Event Flow:

* AddRoi (intent):
    - Emitted by views when the user requests a new ROI (e.g. toolbar Add) and the
      ROI is not already created on ``KymImage`` (see adapter path in docs).
    - RoiController resolves the target KymImage, applies constraints such as
      MAX_NUM_ROI, creates a new ROI on the model, selects it via AppState, and
      emits FileChanged (state, change_type="roi") so views can refresh.
      It does **not** emit AddRoi(state) on the bus (AppStateBridge emits ROISelection).

* EditRoi (intent):
    - Emitted when the user changes ROI bounds.
    - RoiController validates the target ROI, applies new bounds, and emits
      FileChanged (state, change_type="roi") only.

* DeleteRoi (intent):
    - Emitted when the user requests ROI deletion.
    - RoiController validates existence, deletes the ROI, updates AppState
      selection to a remaining ROI (or clears it), and emits
      FileChanged (state, change_type="roi") only.

* ROISelection (intent):
    - Emitted by views when the user selects a different ROI.
    - RoiController calls AppState.select_roi, which in turn notifies
      AppStateBridge so ROISelection (state) events flow to bindings.

By centralizing these flows, we reduce controller fragmentation while keeping
the external event surface unchanged.
"""

from __future__ import annotations

from typing import Optional

from kymflow.core.utils.logging import get_logger
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.config import MAX_NUM_ROI
from kymflow.gui_v2.events import (
    AddRoi,
    DeleteRoi,
    EditRoi,
    FileChanged,
    ROISelection,
    SelectionOrigin,
)
from kymflow.gui_v2.state import AppState


logger = get_logger(__name__)


class RoiController:
    """Controller that handles ROI CRUD and selection intents.

    This controller subscribes to AddRoi, EditRoi, DeleteRoi, and ROISelection
    events with phase="intent" and applies those operations to the underlying
    KymImage model and AppState. It then emits the same event types with
    phase="state" (for CRUD) and FileChanged events so that views can respond
    using state-phase subscriptions.

    Attributes:
        _app_state: Shared AppState instance for file/ROI selection.
        _bus: EventBus instance used to subscribe to intent events and emit
            corresponding state events.
    """

    def __init__(self, app_state: AppState, bus: EventBus) -> None:
        """Initialize the unified ROI controller.

        Subscribes to ROI CRUD and selection intent events.

        Args:
            app_state: Application state containing the current file and
                selected ROI.
            bus: EventBus for subscribing to intent events and emitting state
                events.
        """
        self._app_state = app_state
        self._bus = bus

        bus.subscribe_intent(AddRoi, self._on_add_roi)
        bus.subscribe_intent(EditRoi, self._on_edit_roi)
        bus.subscribe_intent(DeleteRoi, self._on_delete_roi)
        bus.subscribe_intent(ROISelection, self._on_roi_selected)

    # ---------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------

    def _resolve_file(self, path: Optional[str]):
        """Resolve a KymImage from an event path or the selected file.

        Args:
            path: Optional file path from the event. If None, falls back to
                the currently selected file in AppState.

        Returns:
            The resolved KymImage instance, or None if no matching file is
            available.
        """
        return self._app_state.get_file_by_path_or_selected(path)

    def _emit_file_changed(self, kym_file, origin: SelectionOrigin) -> None:
        """Emit a FileChanged(state) event for ROI-related changes.

        Args:
            kym_file: The KymImage instance whose ROIs changed.
            origin: SelectionOrigin describing where the change came from.
        """
        self._bus.emit(
            FileChanged(
                file=kym_file,
                change_type="roi",
                origin=origin,
                phase="state",
            )
        )

    # ---------------------------------------------------------------------
    # Intent handlers
    # ---------------------------------------------------------------------

    def _on_add_roi(self, e: AddRoi) -> None:
        """Handle AddRoi intent events.

        Creates a new ROI on the resolved KymImage, selects it via AppState,
        and emits FileChanged(state, change_type="roi").

        Args:
            e: AddRoi intent event including path, origin, and phase.
        """
        logger.debug("AddRoi intent path=%s", e.path)

        kym_file = self._resolve_file(e.path)
        if kym_file is None:
            logger.warning("AddRoi: no file available (path=%s)", e.path)
            return

        # Enforce maximum number of ROIs when configured.
        if MAX_NUM_ROI is not None:
            num_rois = kym_file.rois.numRois()
            if num_rois >= MAX_NUM_ROI:
                logger.warning(
                    "AddRoi: maximum number of ROIs reached (current=%d, max=%d, path=%s)",
                    num_rois,
                    MAX_NUM_ROI,
                    e.path,
                )
                return

        try:
            # Create ROI with default full-image bounds (bounds=None).
            logger.debug("AddRoi: creating ROI on %s", kym_file.path)
            roi = kym_file.rois.create_roi()
            logger.debug("AddRoi: created roi_id=%s", roi.id)

            # Select the newly created ROI so AppState/AppStateBridge emit
            # ROISelection(state) events to listeners.
            self._app_state.select_roi(roi.id)

            # Notify all views that the file's ROI structure has changed.
            self._emit_file_changed(kym_file, SelectionOrigin.EXTERNAL)
        except ValueError as exc:
            logger.error("AddRoi: failed to create ROI: %s", exc)

    def _on_edit_roi(self, e: EditRoi) -> None:
        """Handle EditRoi intent events.

        Validates the target ROI, applies new bounds, and emits
        FileChanged(state, change_type="roi") so views can refresh.

        Args:
            e: EditRoi intent event including roi_id, bounds, path, and origin.
        """
        logger.debug("EditRoi intent roi_id=%s bounds=%s", e.roi_id, e.bounds)

        kym_file = self._resolve_file(e.path)
        if kym_file is None:
            logger.warning("EditRoi: no file available (path=%s)", e.path)
            return

        # Ensure the ROI exists before editing.
        roi = kym_file.rois.get(e.roi_id)
        if roi is None:
            logger.warning(
                "EditRoi: ROI not found (roi_id=%s, path=%s)",
                e.roi_id,
                e.path,
            )
            return

        try:
            # Apply new bounds if provided.
            if e.bounds is not None:
                kym_file.rois.edit_roi(e.roi_id, bounds=e.bounds)
                logger.debug(
                    "EditRoi: updated roi_id=%s with bounds=%s",
                    e.roi_id,
                    e.bounds,
                )

            # Notify views that ROI geometry changed for this file.
            self._emit_file_changed(kym_file, SelectionOrigin.EXTERNAL)
        except ValueError as exc:
            logger.error("EditRoi: failed to edit ROI: %s", exc)

    def _on_delete_roi(self, e: DeleteRoi) -> None:
        """Handle DeleteRoi intent events.

        Deletes the specified ROI if it exists, updates AppState selection to a
        remaining ROI (or clears it), and emits FileChanged(state, change_type="roi").

        Args:
            e: DeleteRoi intent event including roi_id, path, and origin.
        """
        logger.debug("DeleteRoi intent roi_id=%s", e.roi_id)

        kym_file = self._resolve_file(e.path)
        if kym_file is None:
            logger.warning("DeleteRoi: no file available (path=%s)", e.path)
            return

        # Check if ROI exists before deleting.
        roi = kym_file.rois.get(e.roi_id)
        if roi is None:
            logger.warning(
                "DeleteRoi: ROI not found (roi_id=%s, path=%s)",
                e.roi_id,
                e.path,
            )
            return

        # Delete the ROI from the model.
        kym_file.rois.delete(e.roi_id)
        logger.debug("DeleteRoi: deleted roi_id=%s", e.roi_id)

        # If the deleted ROI was selected, update AppState selection to a
        # remaining ROI or clear it when none remain. This will cause
        # ROISelection(state) to flow via AppStateBridge.
        if self._app_state.selected_roi_id == e.roi_id:
            remaining_roi_ids = kym_file.rois.get_roi_ids()
            if remaining_roi_ids:
                self._app_state.select_roi(remaining_roi_ids[0])
            else:
                self._app_state.select_roi(None)

        # Notify views that the file's ROI set changed.
        self._emit_file_changed(kym_file, SelectionOrigin.EXTERNAL)

    def _on_roi_selected(self, e: ROISelection) -> None:
        """Handle ROISelection intent events.

        Updates AppState with the new ROI selection. AppStateBridge will emit
        ROISelection(state) events to listeners once the selection is applied.

        Args:
            e: ROISelection intent event including roi_id and origin.
        """
        self._app_state.select_roi(e.roi_id)

