"""Bindings for PlotPoolController: FileSelection (state) -> select_points_by_row_id.

20260213ppc: Plot pool integration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.events import FileSelection
from kymflow.gui_v2.events_state import (
    AnalysisCompleted,
    FileListChanged,
    RadonReportUpdated,
    VelocityEventDbUpdated,
)
from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from kymflow.gui_v2.state import AppState


class PlotPoolBindings:
    """Subscribe to FileSelection (state) and call PlotPoolController.select_points_by_row_id.

    20260213ppc: When a file is selected, highlights the corresponding row in the
    PlotPoolController. Uses roi_id from FileSelection; if roi_id is None, uses first ROI for that file.

    Also subscribes to FileListChanged and RadonReportUpdated: when radon data changes
    (folder load, Analyze Flow complete), calls refresh_callback to update the plot pool.
    """

    def __init__(
        self,
        bus: EventBus,
        controller_ref: dict[str, Any],
        *,
        app_state: AppState | None = None,
        refresh_callback: Callable[[], None] | None = None,
        plot_pool_velocity_controller_ref: dict[str, Any] | None = None,
        refresh_velocity_callback: Callable[[], None] | None = None,
    ) -> None:
        """Initialize bindings.

        Args:
            bus: Event bus to subscribe to.
            controller_ref: Dict with 'value' key holding PlotPoolController (Radon) or None.
            app_state: AppState for accessing files (needed for update_radon_report_cache_only
                on AnalysisCompleted). If None, AnalysisCompleted path is no-op.
            refresh_callback: Called when FileListChanged or RadonReportUpdated fires.
            plot_pool_velocity_controller_ref: Dict for velocity events PlotPoolController.
            refresh_velocity_callback: Called when VelocityEventDbUpdated or FileListChanged fires.
        """
        self._bus = bus
        self._controller_ref = controller_ref
        self._app_state = app_state
        self._refresh_callback = refresh_callback
        self._plot_pool_velocity_controller_ref = plot_pool_velocity_controller_ref
        self._refresh_velocity_callback = refresh_velocity_callback
        self._subscribed = False

        bus.subscribe_state(FileSelection, self._on_file_selection_changed)
        if refresh_callback is not None:
            bus.subscribe(FileListChanged, self._on_radon_data_changed)
            bus.subscribe(RadonReportUpdated, self._on_radon_data_changed)
        if refresh_velocity_callback is not None:
            bus.subscribe(VelocityEventDbUpdated, self._on_velocity_data_changed)
            bus.subscribe(FileListChanged, self._on_velocity_data_changed)
        if app_state is not None and refresh_callback is not None:
            bus.subscribe_state(AnalysisCompleted, self._on_analysis_completed)
        self._subscribed = True
        subs = ["FileSelection"]
        if refresh_callback:
            subs.extend(["FileListChanged", "RadonReportUpdated"])
        if refresh_velocity_callback:
            subs.extend(["VelocityEventDbUpdated", "FileListChanged"])
        if app_state and refresh_callback:
            subs.append("AnalysisCompleted")
        logger.info("20260213ppc PlotPoolBindings subscribed to %s", ", ".join(subs))

    def teardown(self) -> None:
        """Unsubscribe from events."""
        if not self._subscribed:
            return
        self._bus.unsubscribe_state(FileSelection, self._on_file_selection_changed)
        if self._refresh_callback is not None:
            self._bus.unsubscribe(FileListChanged, self._on_radon_data_changed)
            self._bus.unsubscribe(RadonReportUpdated, self._on_radon_data_changed)
        if self._refresh_velocity_callback is not None:
            self._bus.unsubscribe(VelocityEventDbUpdated, self._on_velocity_data_changed)
            self._bus.unsubscribe(FileListChanged, self._on_velocity_data_changed)
        if self._app_state is not None and self._refresh_callback is not None:
            self._bus.unsubscribe_state(AnalysisCompleted, self._on_analysis_completed)
        self._subscribed = False

    def _on_velocity_data_changed(self, _e: FileListChanged | VelocityEventDbUpdated) -> None:
        """On FileListChanged or VelocityEventDbUpdated: refresh velocity plot pool."""
        if self._refresh_velocity_callback is not None:
            try:
                self._refresh_velocity_callback()
            except Exception as ex:
                logger.warning("velocity plot pool refresh_callback failed: %s", ex)

    def _on_radon_data_changed(self, _e: FileListChanged | RadonReportUpdated) -> None:
        """On FileListChanged or RadonReportUpdated: refresh plot pool with radon data."""
        if self._refresh_callback is not None:
            try:
                self._refresh_callback()
            except Exception as ex:
                logger.warning("20260213ppc plot pool refresh_callback failed: %s", ex)

    def _on_analysis_completed(self, e: AnalysisCompleted) -> None:
        """On AnalysisCompleted: update radon cache in memory, emit RadonReportUpdated, refresh plot pool."""
        if not e.success or e.file is None:
            return
        if self._app_state is None or self._app_state.files is None:
            return
        if hasattr(self._app_state.files, "update_radon_report_cache_only"):
            try:
                self._app_state.files.update_radon_report_cache_only(e.file)
            except Exception as ex:
                logger.warning("20260213ppc update_radon_report_cache_only failed: %s", ex)
                return
        self._bus.emit(RadonReportUpdated())

    def _on_file_selection_changed(self, e: FileSelection) -> None:
        """On FileSelection (state): call select_points_by_row_id if controller exists."""
        # 20260213ppc
        ctrl = self._controller_ref.get("value")
        if ctrl is None:
            return
        if e.file is None or not hasattr(e.file, "path") or e.file.path is None:
            return
        path = str(e.file.path)
        roi_id = e.roi_id
        if roi_id is None:
            # Use first ROI for that file
            roi_ids = getattr(e.file, "rois", None)
            if roi_ids is not None and hasattr(roi_ids, "get_roi_ids"):
                ids = roi_ids.get_roi_ids()
                if ids:
                    roi_id = ids[0]
                else:
                    return
            else:
                return
        row_id = f"{path}|{roi_id}"
        try:
            ctrl.select_points_by_row_id(row_id)
            logger.debug("20260213ppc select_points_by_row_id(%s)", row_id)
        except Exception as ex:
            logger.warning("20260213ppc select_points_by_row_id failed: %s", ex)
