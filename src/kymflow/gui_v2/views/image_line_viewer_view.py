"""Image/line viewer view component using Plotly.

This module provides a view component that displays a combined kymograph image
and velocity plot using Plotly. The view emits ROISelection events when users
select ROIs from the dropdown, but does not subscribe to events (that's handled
by ImageLineViewerBindings).
"""

from __future__ import annotations

from typing import Callable, Optional

import numpy as np
import plotly.graph_objects as go
from nicegui import ui

from kymflow.core.analysis.stall_analysis import StallAnalysisParams
from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.plotting import (
    plot_image_line_plotly,
    update_colorscale,
    update_contrast,
    reset_image_zoom,
)
from kymflow.core.plotting.theme import ThemeMode
from kymflow.gui.state import ImageDisplayParams
from kymflow.gui_v2.client_utils import safe_call
from kymflow.gui_v2.events import ROISelection, SelectionOrigin
from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

OnROISelected = Callable[[ROISelection], None]


class ImageLineViewerView:
    """Image/line viewer view component using Plotly.

    This view displays a combined kymograph image and velocity plot with ROI
    selection, filter controls, and zoom controls. Users can select ROIs from
    the dropdown, which triggers ROISelection events.

    Lifecycle:
        - UI elements are created in render() (not __init__) to ensure correct
          DOM placement within NiceGUI's client context
        - Data updates via setter methods (called by bindings)
        - Events emitted via on_roi_selected callback

    Attributes:
        _on_roi_selected: Callback function that receives ROISelection events.
        _plot: Plotly plot component (created in render()).
        _roi_select: ROI selector dropdown (created in render()).
        _current_file: Currently selected file (for rendering).
        _current_roi_id: Currently selected ROI ID (for rendering).
        _theme: Current theme mode.
        _display_params: Current image display parameters.
        _current_figure: Current figure reference (for partial updates).
        _original_y_values: Original unfiltered y-values (for filter updates).
        _original_time_values: Original time values (for filter updates).
        _uirevision: Counter to control Plotly's uirevision for forced resets.
    """

    def __init__(self, *, on_roi_selected: OnROISelected) -> None:
        """Initialize image/line viewer view.

        Args:
            on_roi_selected: Callback function that receives ROISelection events.
        """
        self._on_roi_selected = on_roi_selected

        # UI components (created in render())
        self._plot: Optional[ui.plotly] = None
        self._roi_select: Optional[ui.select] = None
        self._stall_refactory_bins: Optional[ui.number] = None
        self._stall_min_duration: Optional[ui.number] = None
        self._stall_end_non_nan_bins: Optional[ui.number] = None
        self._stall_run_btn: Optional[ui.button] = None

        # State (theme will be set by bindings from AppState)
        self._current_file: Optional[KymImage] = None
        self._current_roi_id: Optional[int] = None
        self._theme: ThemeMode = ThemeMode.DARK  # Default, will be updated by set_theme()
        self._display_params: Optional[ImageDisplayParams] = None
        self._current_figure: Optional[go.Figure] = None
        self._original_y_values: Optional[np.ndarray] = None
        self._original_time_values: Optional[np.ndarray] = None
        self._uirevision: int = 0
        self._suppress_roi_emit: bool = False  # Suppress ROI dropdown on_change during programmatic updates
        
        # Filter state (stored instead of reading from checkboxes)
        self._remove_outliers: bool = False
        self._median_filter: bool = False

    def render(self) -> None:
        """Create the viewer UI inside the current container.

        Always creates fresh UI elements because NiceGUI creates a new container
        context on each page navigation. Old UI elements are automatically cleaned
        up by NiceGUI when navigating away.

        This method is called on every page navigation. We always recreate UI
        elements rather than trying to detect if they're still valid, which is
        simpler and more reliable.
        """
        # Always reset UI element references - NiceGUI will clean up old elements
        # This ensures we create fresh elements in the new container context
        self._plot = None
        self._roi_select = None
        self._stall_refactory_bins = None
        self._stall_min_duration = None
        self._stall_end_non_nan_bins = None
        self._stall_run_btn = None
        # Reset suppression flag to ensure clean state
        self._suppress_roi_emit = False

        # ROI selector dropdown
        # Use on_change callback (NiceGUI recommended API) instead of on("update:model-value")
        self._roi_select = ui.select(options={}, label="ROI", on_change=self._on_roi_dropdown_change).classes("min-w-32")

        # Stall analysis controls (per-ROI, on-demand)
        with ui.row().classes("w-full gap-2 items-center"):
            ui.label("Stall analysis").classes("text-sm font-semibold")
            self._stall_refactory_bins = ui.number(
                label="refactory_bins",
                value=20,
                min=0,
                step=1,
            ).classes("w-32")
            self._stall_min_duration = ui.number(
                label="min_stall_duration",
                value=2,
                min=1,
                step=1,
            ).classes("w-36")
            self._stall_end_non_nan_bins = ui.number(
                label="end_stall_non_nan_bins",
                value=2,
                min=1,
                step=1,
            ).classes("w-44")
            self._stall_run_btn = ui.button("Analyze stalls", on_click=self._on_analyze_stalls)

        # Plot with larger height to accommodate both subplots
        self._plot = ui.plotly(go.Figure()).classes("w-full")

    def _on_analyze_stalls(self) -> None:
        """Run stall analysis for the currently selected ROI, then re-render plot."""
        kf = self._current_file
        roi_id = self._current_roi_id
        if kf is None:
            ui.notify("Select a file first", color="warning")
            return
        if roi_id is None:
            ui.notify("Select an ROI first", color="warning")
            return
        if (
            self._stall_refactory_bins is None
            or self._stall_min_duration is None
            or self._stall_end_non_nan_bins is None
        ):
            return

        try:
            refactory_bins = int(self._stall_refactory_bins.value)
            min_stall_duration = int(self._stall_min_duration.value)
            end_stall_non_nan_bins = int(self._stall_end_non_nan_bins.value)
        except Exception:
            ui.notify("Invalid stall parameters", color="negative")
            return

        params = StallAnalysisParams(
            velocity_key="velocity",
            refactory_bins=refactory_bins,
            min_stall_duration=min_stall_duration,
            end_stall_non_nan_bins=end_stall_non_nan_bins,
        )

        try:
            analysis = kf.get_kym_analysis().run_stall_analysis(roi_id=roi_id, params=params)
        except Exception as e:
            ui.notify(f"Stall analysis failed: {e}", color="negative")
            return

        ui.notify(f"Detected {len(analysis.stalls)} stalls", color="positive")
        self._render_combined()

    def set_selected_file(self, file: Optional[KymImage]) -> None:
        """Update plot for new file.

        Called by bindings when FileSelection (phase="state") event is received.
        Updates dropdown options and clears current ROI (will be set by ROISelection event).
        Triggers full render and zoom reset.

        Args:
            file: Selected KymImage instance, or None if selection cleared.
        """
        safe_call(self._set_selected_file_impl, file)

    def _set_selected_file_impl(self, file: Optional[KymImage]) -> None:
        """Internal implementation of set_selected_file."""
        self._current_file = file
        # Update dropdown options (ROI selection will be updated by ROISelection(phase="state") event
        # that AppState.select_file() automatically triggers)
        self._update_roi_dropdown()
        # Clear current ROI - will be set when ROISelection(phase="state") event arrives
        self._current_roi_id = None
        self._render_combined()
        # Reset to full zoom when selection changes
        self._reset_zoom(force_new_uirevision=True)

    def set_selected_roi(self, roi_id: Optional[int]) -> None:
        """Update plot for new ROI.

        Called by bindings when ROISelection(phase="state") event is received.
        Updates dropdown and re-renders plot.

        Args:
            roi_id: Selected ROI ID, or None if selection cleared.
        """
        safe_call(self._set_selected_roi_impl, roi_id)

    def _set_selected_roi_impl(self, roi_id: Optional[int]) -> None:
        """Internal implementation of set_selected_roi."""
        self._current_roi_id = roi_id
        logger.info(f"set _current_roi_id to '{roi_id}' {type(roi_id)}")
        if self._roi_select is not None:
            # Ensure options are up to date before setting value
            if self._current_file is not None:
                roi_ids = self._current_file.rois.get_roi_ids()
                options = {rid: f"ROI {rid}" for rid in roi_ids}
                # Suppress on_change callback during programmatic update to prevent feedback loop
                self._suppress_roi_emit = True
                try:
                    # Only set value if ROI is valid and in options
                    if roi_id is not None and roi_id in roi_ids:
                        self._roi_select.set_options(options, value=roi_id)
                    else:
                        # Clear selection if ROI is invalid
                        self._roi_select.set_options(options, value=None)
                finally:
                    self._suppress_roi_emit = False
            else:
                # No file selected, clear options and value
                self._suppress_roi_emit = True
                try:
                    self._roi_select.set_options({}, value=None)
                finally:
                    self._suppress_roi_emit = False
        self._render_combined()

    def set_theme(self, theme: ThemeMode) -> None:
        """Update theme.

        Called by bindings when ThemeChanged event is received.
        Triggers full render.

        Args:
            theme: New theme mode (DARK or LIGHT).
        """
        safe_call(self._set_theme_impl, theme)

    def _set_theme_impl(self, theme: ThemeMode) -> None:
        """Internal implementation of set_theme."""
        self._theme = theme
        self._render_combined()

    def set_image_display(self, params: ImageDisplayParams) -> None:
        """Update contrast/colorscale.

        Called by bindings when ImageDisplayChanged event is received.
        Uses partial update to preserve zoom state.

        Args:
            params: ImageDisplayParams containing colorscale, zmin, zmax.
        """
        safe_call(self._set_image_display_impl, params)

    def _set_image_display_impl(self, params: ImageDisplayParams) -> None:
        """Internal implementation of set_image_display."""
        self._display_params = params
        self._update_contrast_partial()

    def set_metadata(self, file: KymImage) -> None:
        """Trigger refresh if file matches current.

        Called by bindings when MetadataChanged event is received.
        Only re-renders if the updated file is the currently selected file.

        Args:
            file: KymImage instance whose metadata was updated.
        """
        safe_call(self._set_metadata_impl, file)

    def _set_metadata_impl(self, file: KymImage) -> None:
        """Internal implementation of set_metadata."""
        if file == self._current_file:
            self._render_combined()

    def _update_roi_dropdown(self) -> None:
        """Update ROI dropdown options based on current file.

        Note: AppState.select_file() already automatically selects the first ROI
        if available, so we just sync the dropdown with the current ROI selection.
        """
        if self._roi_select is None:
            return

        kf = self._current_file
        if kf is None:
            # Use set_options() which handles both setting options and calling update()
            self._roi_select.set_options({}, value=None)
            return

        # Use RoiSet.get_roi_ids() public API instead of accessing ROI objects directly
        roi_ids = kf.rois.get_roi_ids()
        # NiceGUI select expects options as dict: {value: label} or list of values
        # Using dict format: {roi_id: f"ROI {roi_id}"}
        options = {roi_id: f"ROI {roi_id}" for roi_id in roi_ids}
        
        logger.info(f'roi options is:{options}')
        logger.info(f'self._current_roi_id is:{self._current_roi_id}')

        # Sync dropdown with current ROI (AppState.select_file() already handles first ROI selection)
        # Use set_options() which updates options and sets value atomically
        # Suppress on_change callback during programmatic update to prevent feedback loop
        self._suppress_roi_emit = True
        try:
            if self._current_roi_id is not None and self._current_roi_id in roi_ids:
                self._roi_select.set_options(options, value=self._current_roi_id)
            else:
                # Current ROI is invalid or None, set options without value
                # Dropdown will be synced when ROISelection(phase="state") event arrives
                self._roi_select.set_options(options, value=None)
        finally:
            self._suppress_roi_emit = False

    def _render_combined(self) -> None:
        """Render the combined image and line plot."""
        kf = self._current_file
        theme = self._theme
        display_params = self._display_params
        roi_id = self._current_roi_id

        if self._plot is None:
            return

        # Convert stored median_filter bool to int (0 = off, 5 = on with window size 5)
        median_filter_size = 5 if self._median_filter else 0

        # Get display parameters from stored params or use defaults
        colorscale = display_params.colorscale if display_params else "Gray"
        zmin = display_params.zmin if display_params else None
        zmax = display_params.zmax if display_params else None

        fig = plot_image_line_plotly(
            kf=kf,
            yStat="velocity",
            remove_outliers=self._remove_outliers,
            median_filter=median_filter_size,
            theme=theme,
            colorscale=colorscale,
            zmin=zmin,
            zmax=zmax,
            selected_roi_id=roi_id,
            transpose=True,
        )

        # Store original unfiltered y-values for partial updates
        if kf is not None and roi_id is not None:
            kym_analysis = kf.get_kym_analysis()
            if kym_analysis.has_analysis(roi_id):
                time_values = kym_analysis.get_analysis_value(roi_id, "time")
                y_values = kym_analysis.get_analysis_value(roi_id, "velocity")
            else:
                time_values = None
                y_values = None
            if time_values is not None and y_values is not None:
                self._original_time_values = np.array(time_values).copy()
                self._original_y_values = np.array(y_values).copy()
            else:
                self._original_time_values = None
                self._original_y_values = None

        # Store figure reference
        self._set_uirevision(fig)
        self._current_figure = fig
        try:
            self._plot.update_figure(fig)
        except RuntimeError as e:
            logger.error(f"Error updating figure: {e}")
            if "deleted" not in str(e).lower():
                raise
            # Client deleted, silently ignore

    def _set_uirevision(self, fig: go.Figure) -> None:
        """Apply the current uirevision to the figure."""
        fig.layout.uirevision = f"kymflow-plot-{self._uirevision}"

    def _reset_zoom(self, force_new_uirevision: bool = False) -> None:
        """Reset zoom while optionally forcing Plotly to drop preserved UI state."""
        fig = self._current_figure
        kf = self._current_file
        if fig is None or kf is None or self._plot is None:
            return

        if force_new_uirevision:
            self._uirevision += 1
            self._set_uirevision(fig)

        reset_image_zoom(fig, kf)
        try:
            self._plot.update_figure(fig)
        except RuntimeError as e:
            logger.error(f"Error updating figure: {e}")
            if "deleted" not in str(e).lower():
                raise
            # Client deleted, silently ignore

    def _on_roi_dropdown_change(self) -> None:
        """Handle ROI dropdown selection change."""
        if self._roi_select is None:
            return
        # Suppress events during programmatic updates to prevent feedback loop
        if self._suppress_roi_emit:
            return
        roi_id = self._roi_select.value
        # Emit intent event
        self._on_roi_selected(
            ROISelection(
                roi_id=roi_id,
                origin=SelectionOrigin.IMAGE_VIEWER,
                phase="intent",
            )
        )

    def _update_line_plot_partial(self) -> None:
        """Update only the Scatter trace y-values when filters change, preserving zoom."""
        fig = self._current_figure
        if fig is None:
            # No figure yet, do full render
            self._render_combined()
            return

        kf = self._current_file
        roi_id = self._current_roi_id

        if kf is None or roi_id is None:
            # No data available, do full render
            self._render_combined()
            return

        # Get current filter settings from stored state
        remove_outliers = self._remove_outliers
        median_filter_size = 5 if self._median_filter else 0

        # Re-compute filtered y-values using KymAnalysis API
        kym_analysis = kf.get_kym_analysis()
        if not kym_analysis.has_analysis(roi_id):
            # No analysis available, do full render
            self._render_combined()
            return

        filtered_y = kym_analysis.get_analysis_value(
            roi_id, "velocity", remove_outliers, median_filter_size
        )

        if filtered_y is None:
            # No data available, do full render
            self._render_combined()
            return

        # Find the Scatter trace and update its y-values
        for trace in fig.data:
            if isinstance(trace, go.Scatter):
                trace.y = filtered_y
                break
        else:
            # No Scatter trace found, do full render
            self._render_combined()
            return

        # Update the plot with modified figure (preserves zoom via uirevision)
        if self._plot is None:
            return
        try:
            self._plot.update_figure(fig)
        except RuntimeError as e:
            if "deleted" not in str(e).lower():
                raise
            # Client deleted, silently ignore

    def apply_filters(self, remove_outliers: bool, median_filter: bool) -> None:
        """Apply filter settings to the plot.

        Public method for external controls (e.g., drawer toolbar) to update
        filter state and trigger plot update.

        Args:
            remove_outliers: Whether to remove outliers from the line plot.
            median_filter: Whether to apply median filter to the line plot.
        """
        safe_call(self._apply_filters_impl, remove_outliers, median_filter)

    def _apply_filters_impl(self, remove_outliers: bool, median_filter: bool) -> None:
        """Internal implementation of apply_filters."""
        self._remove_outliers = remove_outliers
        self._median_filter = median_filter
        # Trigger plot update with new filter settings
        self._update_line_plot_partial()

    def reset_zoom(self) -> None:
        """Reset zoom to full scale.

        Public method for external controls (e.g., drawer toolbar) to reset
        the image zoom to full scale.
        """
        safe_call(self._reset_zoom, force_new_uirevision=True)

    def _update_contrast_partial(self) -> None:
        """Update only colorscale/zmin/zmax when contrast changes, preserving zoom."""
        fig = self._current_figure
        if fig is None or self._plot is None:
            # No figure yet, ignore contrast changes
            return

        display_params = self._display_params
        if display_params is None:
            return

        # Update colorscale
        update_colorscale(fig, display_params.colorscale)

        # Update contrast (zmin/zmax)
        update_contrast(fig, zmin=display_params.zmin, zmax=display_params.zmax)

        # Update the plot with modified figure (preserves zoom via uirevision)
        try:
            self._plot.update_figure(fig)
        except RuntimeError as e:
            if "deleted" not in str(e).lower():
                raise
            # Client deleted, silently ignore

