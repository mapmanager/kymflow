"""Image/line viewer view component using Plotly.

This module provides a view component that displays a combined kymograph image
and velocity plot using Plotly. The view emits ROISelection events when users
select ROIs from the dropdown, but does not subscribe to events (that's handled
by ImageLineViewerBindings).
"""

from __future__ import annotations

from typing import Callable, Optional, Dict, Any

import numpy as np
import plotly.graph_objects as go
from nicegui import ui
from nicegui.events import GenericEventArguments  # for _on_relayout()

from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.plotting import (
    # plot_image_line_plotly,
    plot_image_line_plotly_v3,
    update_colorscale,
    update_contrast,
    reset_image_zoom,
    update_xaxis_range,
)
from kymflow.core.plotting.theme import ThemeMode
from kymflow.gui_v2.state import ImageDisplayParams
from kymflow.gui_v2.client_utils import safe_call
from kymflow.gui_v2.events import (
    EventSelection,
    SelectionOrigin,
    SetKymEventXRange,
    SetRoiBounds,
)
from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

OnKymEventXRange = Callable[[SetKymEventXRange], None]
OnSetRoiBounds = Callable[[SetRoiBounds], None]


class ImageLineViewerView:
    """Image/line viewer view component using Plotly.

    This view displays a combined kymograph image and velocity plot with filter
    controls and zoom controls.

    Lifecycle:
        - UI elements are created in render() (not __init__) to ensure correct
          DOM placement within NiceGUI's client context
        - Data updates via setter methods (called by bindings)

    Attributes:
        _plot: Plotly plot component (created in render()).
        _current_file: Currently selected file (for rendering).
        _current_roi_id: Currently selected ROI ID (for rendering).
        _theme: Current theme mode.
        _display_params: Current image display parameters.
        _current_figure: Current figure reference (for partial updates).
        _original_y_values: Original unfiltered y-values (for filter updates).
        _original_time_values: Original time values (for filter updates).
        _uirevision: Counter to control Plotly's uirevision for forced resets.
    """

    def __init__(
        self,
        *,
        on_kym_event_x_range: OnKymEventXRange | None = None,
        on_set_roi_bounds: OnSetRoiBounds | None = None,
    ) -> None:
        """Initialize image/line viewer view.

        Args:
            on_kym_event_x_range: Callback function that receives SetKymEventXRange events.
            on_set_roi_bounds: Callback function that receives SetRoiBounds events.
        """
        self._on_kym_event_x_range = on_kym_event_x_range
        self._on_set_roi_bounds = on_set_roi_bounds

        # UI components (created in render())
        self._plot: Optional[ui.plotly] = None
        self._plot_container: Optional[ui.element] = None
        self._plot_div_id: str = "kymflow_image_line_plot"
        self._last_num_rows: int | None = None

        # State (theme will be set by bindings from AppState)
        self._current_file: Optional[KymImage] = None
        self._current_roi_id: Optional[int] = None
        self._theme: ThemeMode = ThemeMode.DARK  # Default, will be updated by set_theme()
        self._display_params: Optional[ImageDisplayParams] = None
        self._current_figure: Optional[go.Figure] = None
        self._original_y_values: Optional[np.ndarray] = None
        self._original_time_values: Optional[np.ndarray] = None
        self._uirevision: int = 0
        
        # Filter state (stored instead of reading from checkboxes)
        self._remove_outliers: bool = False
        self._median_filter: bool = False
        self._awaiting_kym_event_range: bool = False
        self._range_event_id: Optional[str] = None
        self._range_roi_id: Optional[int] = None
        self._range_path: Optional[str] = None
        self._pending_range_zoom: Optional[tuple[float, float]] = None
        self._selected_event_id: str | None = None  # Track selected event for visual highlighting
        
        # ROI edit selection state
        self._awaiting_roi_edit: bool = False
        self._edit_roi_id: Optional[int] = None
        self._edit_roi_path: Optional[str] = None

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
        self._plot_container = None

        # Plot container fills available height so nested splitters can resize vertically.
        self._plot_container = ui.column().classes("w-full h-full")
        with self._plot_container:
            self._create_plot(go.Figure())

    def _create_plot(self, fig: go.Figure) -> None:
        """Create a fresh plot element inside the current container."""
        logger.debug(f'=== this may be overkill')
        # Plotly element stretches to container height for splitter resize support.
        self._plot = ui.plotly(fig).classes("w-full h-full")
        # Stable DOM id for JS access (dragmode toggling).
        self._plot.props(f"id={self._plot_div_id}")
        # abb when implementing getting user drawrect/rect selection
        # and setting start/stop of a single velocity event.
        self._plot.on("plotly_relayout", self._on_plotly_relayout)

    def _on_plotly_relayout(self, e: GenericEventArguments) -> None:
        """
        Handle Plotly relayout events.
        
        Use this to handle setting start/stop of a single velocity event.


        This is the only way to get the selection x-range when the user is dragging a box.
        The payload is a dictionary with the following keys:
        - selections: list of selection dictionaries
        - selections[0].x0: x-coordinate of the left edge of the selection
        - selections[0].x1: x-coordinate of the right edge of the selection
        - selections[0].y0: y-coordinate of the top edge of the selection
        - selections[0].y1: y-coordinate of the bottom edge of the selection
        - selections[0].type: type of the selection

        If toolbar is in rect mode and user shift+click+drag,
        then a new selection is created like [1], [2], [3], ... etc.
        """

        payload: Dict[str, Any] = e.args  # <-- dict

        logger.debug("plotly_relayout received (awaiting_range=%s, awaiting_roi_edit=%s)", 
                     self._awaiting_kym_event_range, self._awaiting_roi_edit)
        logger.info('=== in on_relayout() payload is:')
        from pprint import pprint
        pprint(payload)

        x0, x1, y0, y1 = None, None, None, None  # default to no selection
        if 'selections[0].x0' in payload.keys():
            logger.info('  update "selections[0].x0" found')
            x0  = payload['selections[0].x0']
            x1  = payload['selections[0].x1']
            y0  = payload.get('selections[0].y0')
            y1  = payload.get('selections[0].y1')
            logger.info(f"  -> update Selection: x-range = [{x0}, {x1}], y-range = [{y0}, {y1}]")
        elif 'selections' not in payload.keys():
            # print('  no selection found')
            return

        # on new selection ?
        if x0 is None and x1 is None:
            selections = payload['selections'] 
            if selections:
                for _idx, selection in enumerate(selections):
                    _type = selection['type']
                    if _type != 'rect':
                        # print(f'  -> ignoring selection type: {_type} (idx={_idx})')
                        continue
                    x0 = selection['x0']
                    x1 = selection['x1']
                    y0 = selection.get('y0')
                    y1 = selection.get('y1')
                    logger.info(f"  --> new Selection: {_type} x-range = [{x0}, {x1}], y-range = [{y0}, {y1}] (idx={_idx})")

        # Handle ROI edit rectangle selection (requires both x and y coordinates)
        if self._awaiting_roi_edit:
            if x0 is None or x1 is None or y0 is None or y1 is None:
                return
            if not all(isinstance(v, (int, float)) for v in [x0, x1, y0, y1]):
                return
            if self._on_set_roi_bounds is None:
                return
            
            x_min = float(min(x0, x1))
            x_max = float(max(x0, x1))
            y_min = float(min(y0, y1))
            y_max = float(max(y0, y1))
            
            # Convert to RoiBounds with logging
            dim0_start = int(y_min)
            dim0_stop = int(y_max)
            dim1_start = int(x_min)
            dim1_stop = int(x_max)
            
            logger.debug(
                "ROI edit selection: Plotly coords x=[%s, %s], y=[%s, %s] -> "
                "RoiBounds dim0=[%s, %s], dim1=[%s, %s]",
                x_min, x_max, y_min, y_max,
                dim0_start, dim0_stop, dim1_start, dim1_stop
            )
            
            self._awaiting_roi_edit = False
            self._on_set_roi_bounds(
                SetRoiBounds(
                    roi_id=self._edit_roi_id,
                    path=self._edit_roi_path,
                    x0=x_min,
                    x1=x_max,
                    y0=y_min,
                    y1=y_max,
                    origin=SelectionOrigin.IMAGE_VIEWER,
                    phase="intent",
                )
            )
            # Clear drawn rectangle/selected points after accepting selection.
            self._clear_plot_selections()
            return

        # Handle kym event range selection (x-range only)
        if not self._awaiting_kym_event_range:
            return
        if x0 is None or x1 is None:
            return
        if not isinstance(x0, (int, float)) or not isinstance(x1, (int, float)):
            return
        if self._on_kym_event_x_range is None:
            return

        x_min = float(min(x0, x1))
        x_max = float(max(x0, x1))
        self._awaiting_kym_event_range = False
        self._pending_range_zoom = None
        fig = self._current_figure
        if fig is not None:
            x_range = fig.layout.xaxis.range
            if isinstance(x_range, (list, tuple)) and len(x_range) == 2:
                try:
                    self._pending_range_zoom = (float(x_range[0]), float(x_range[1]))
                except (TypeError, ValueError):
                    logger.debug("invalid xaxis range; skipping pending zoom")
        logger.debug("emitting SetKymEventXRange x0=%s x1=%s", x_min, x_max)
        logger.debug(f'  self._pending_range_zoom:{self._pending_range_zoom}')
        self._on_kym_event_x_range(
            SetKymEventXRange(
                event_id=self._range_event_id,
                roi_id=self._range_roi_id,
                path=self._range_path,
                x0=x_min,
                x1=x_max,
                origin=SelectionOrigin.IMAGE_VIEWER,
                phase="intent",
            )
        )
        # Clear drawn rectangle/selected points after accepting selection.
        self._clear_plot_selections()

    def set_kym_event_range_enabled(
        self,
        enabled: bool,
        *,
        event_id: Optional[str],
        roi_id: Optional[int],
        path: Optional[str],
    ) -> None:
        """Toggle Plotly dragmode and arm the next x-range selection."""
        logger.debug(
            "set_kym_event_range_enabled(enabled=%s, event_id=%s, roi_id=%s)",
            enabled,
            event_id,
            roi_id,
        )
        self._awaiting_kym_event_range = enabled
        self._range_event_id = event_id
        self._range_roi_id = roi_id
        self._range_path = path
        dragmode = "select" if enabled else "zoom"
        self._set_dragmode(dragmode)
        if not enabled:
            self._clear_plot_selections()

    def set_roi_edit_enabled(
        self,
        enabled: bool,
        *,
        roi_id: Optional[int],
        path: Optional[str],
    ) -> None:
        """Toggle Plotly dragmode and arm the next rectangle selection for ROI editing.
        
        This operates on the kym image/heatmap Plotly plot (NOT the 1D velocity plot).
        
        Args:
            enabled: Whether to enable ROI edit mode.
            roi_id: ROI ID to edit (required when enabled=True).
            path: File path (optional, for validation).
        """
        logger.debug(
            "set_roi_edit_enabled(enabled=%s, roi_id=%s, path=%s)",
            enabled,
            roi_id,
            path,
        )
        self._awaiting_roi_edit = enabled
        self._edit_roi_id = roi_id
        self._edit_roi_path = path
        dragmode = "select" if enabled else "zoom"
        self._set_dragmode(dragmode)
        if not enabled:
            self._clear_plot_selections()

    def _set_dragmode(self, dragmode: Optional[str]) -> None:
        """Set Plotly dragmode on the current plot."""
        js = f"""
        (() => {{
          const gd = document.getElementById({self._plot_div_id!r});
          if (!gd) return;
          Plotly.relayout(gd, {{ dragmode: {repr(dragmode)} }});
        }})()
        """
        ui.run_javascript(js)

    def _clear_plot_selections(self) -> None:
        """Clear Plotly layout selections and selected points."""
        js = f"""
        (() => {{
          const gd = document.getElementById({self._plot_div_id!r});
          if (!gd) return;

          // (1) Clear ROI rectangles (layout.selections)
          Plotly.relayout(gd, {{ selections: [] }});

          // (2) Clear selected points styling/state
          if (gd.data && gd.data.length) {{
            const idx = Array.from({{length: gd.data.length}}, (_, i) => i);
            Plotly.restyle(gd, {{ selectedpoints: [null] }}, idx);
          }}
        }})()
        """
        ui.run_javascript(js)

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
        if file is not None:
            try:
                file.load_channel(1)
            except Exception as exc:
                logger.warning(
                    "ImageLineViewerView failed to load channel=1 for file=%s: %s",
                    str(file.path) if hasattr(file, "path") else None,
                    exc,
                )
        self._current_file = file
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

    def zoom_to_event(self, e: EventSelection) -> None:
        """Zoom the x-axis to an event if options request it."""
        safe_call(self._zoom_to_event_impl, e)

    def _zoom_to_event_impl(self, e: EventSelection) -> None:
        # Store selected event_id for visual highlighting (None clears selection)
        old_selected = self._selected_event_id
        self._selected_event_id = e.event_id
        
        # Early returns for invalid cases
        if e.event is None or e.options is None:
            # Update highlight if selection changed
            if old_selected != e.event_id:
                self._render_combined()
            return
        if self._current_roi_id is None or e.roi_id != self._current_roi_id:
            # ROI mismatch - update highlight if selection changed
            if old_selected != e.event_id:
                self._render_combined()
            return
        if self._current_figure is None or self._plot is None:
            return
        
        # Always re-render to show highlight (if selection changed)
        needs_render = (old_selected != e.event_id)
        if needs_render:
            # Preserve x-axis range if zoom is disabled (e.g., after adding event)
            preserved_range = None
            if not e.options.zoom:
                x_range = self._current_figure.layout.xaxis.range
                if isinstance(x_range, (list, tuple)) and len(x_range) == 2:
                    try:
                        preserved_range = (float(x_range[0]), float(x_range[1]))
                    except (TypeError, ValueError):
                        pass
            
            self._render_combined()
            
            # Restore preserved x-axis range if we captured it
            if preserved_range is not None:
                fig = self._current_figure
                if fig is not None and self._plot is not None:
                    update_xaxis_range(fig, list(preserved_range))
                    try:
                        self._plot.update_figure(fig)
                    except RuntimeError as ex:
                        if "deleted" not in str(ex).lower():
                            logger.error(f"Error restoring zoom: {ex}")
                            raise
        
        # If zoom is enabled, apply it as a fast partial update (axis range only)
        # This is very fast and doesn't cause a full re-render
        if e.options.zoom and e.event is not None:
            t_start = e.event.t_start
            pad = float(e.options.zoom_pad_sec)
            x_min = t_start - pad
            x_max = t_start + pad
            if self._original_time_values is not None and len(self._original_time_values) > 0:
                x_min = max(x_min, float(self._original_time_values[0]))
                x_max = min(x_max, float(self._original_time_values[-1]))
            elif self._current_file is not None:
                duration = self._current_file.image_dur
                if duration is not None:
                    x_min = max(x_min, 0.0)
                    x_max = min(x_max, float(duration))
            
            fig = self._current_figure
            if fig is not None:
                update_xaxis_range(fig, [x_min, x_max])
                try:
                    self._plot.update_figure(fig)
                except RuntimeError as ex:
                    logger.error(f"Error updating zoom: {ex}")
                    if "deleted" not in str(ex).lower():
                        raise

    def _set_metadata_impl(self, file: KymImage) -> None:
        """Internal implementation of set_metadata."""
        if file == self._current_file:
            self._render_combined()


    def _render_combined(self) -> None:
        """Render the combined image and line plot."""
        
        kf = self._current_file
        theme = self._theme
        display_params = self._display_params
        roi_id = self._current_roi_id

        if self._plot is None:
            return

        # Convert stored median_filter bool to int (0 = off, 5 = on with window size 5)
        median_filter_size = 3 if self._median_filter else 0
        if self._median_filter:
            logger.warning('HARD CODING median_filter_size: 3')

        # Get display parameters from stored params or use defaults
        colorscale = display_params.colorscale if display_params else "Gray"
        zmin = display_params.zmin if display_params else None
        zmax = display_params.zmax if display_params else None

        # Determine if ROI overlay should be shown (only if > 1 ROI)
        num_rois = kf.rois.numRois() if kf is not None else 0
        plot_rois = (num_rois > 1)

        logger.debug(f'=== pyinstaller calling plot_image_line_plotly_v3()')
        # logger.debug(f'  kf={kf}')
        # logger.debug(f'  selected_roi_id roi_id={roi_id}')
        # logger.debug(f'  plot_rois plot_rois={plot_rois}')
        # logger.debug(f'  selected_event_id self.selected_event_id={self._selected_event_id}')
        
        fig = plot_image_line_plotly_v3(
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
            plot_rois=plot_rois,
            selected_event_id=self._selected_event_id,
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
        # Detect grid changes (1 row vs 2 rows) and rebuild plot if needed
        num_rows = 2 if getattr(fig.layout, "yaxis2", None) is not None else 1
        if self._last_num_rows is None:
            self._last_num_rows = num_rows

        # elif num_rows != self._last_num_rows and self._plot_container is not None:
        #     logger.debug(
        #         "pyinstaller bug fix rebuild plot on grid change %s -> %s",
        #         self._last_num_rows,
        #         num_rows,
        #     )
        #     self._last_num_rows = num_rows
        #     self._plot_container.clear()
        #     with self._plot_container:
        #         self._create_plot(fig)
        #     return

        try:
            # abb this is a core plot function !!!
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
            logger.debug(f'pyinstaller calling _plot.update_figure(fig)')
            self._plot.update_figure(fig)
        except RuntimeError as e:
            if "deleted" not in str(e).lower():
                raise
            else:
                logger.debug(f'pyinstaller swallowed/skipped Client deleted RuntimeError: {e}')
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

    def refresh_velocity_events(self) -> None:
        """Re-render the plot to refresh velocity event overlays."""
        safe_call(self._refresh_velocity_events_impl)

    def _refresh_velocity_events_impl(self) -> None:
        """Refresh velocity event overlays while preserving current zoom."""
        # Capture current x-axis range before re-rendering
        fig = self._current_figure
        preserved_range = None
        if fig is not None and self._plot is not None:
            x_range = fig.layout.xaxis.range
            if isinstance(x_range, (list, tuple)) and len(x_range) == 2:
                try:
                    preserved_range = (float(x_range[0]), float(x_range[1]))
                except (TypeError, ValueError):
                    # Invalid range, will not preserve zoom
                    pass
        
        self._render_combined()
        
        # Restore preserved zoom if we captured it
        if preserved_range is not None:
            fig = self._current_figure
            if fig is not None and self._plot is not None:
                update_xaxis_range(fig, list(preserved_range))
                try:
                    self._plot.update_figure(fig)
                except RuntimeError as e:
                    if "deleted" not in str(e).lower():
                        raise
        else:
            # No preserved range, apply pending range zoom if any
            self._apply_pending_range_zoom()

    def _apply_pending_range_zoom(self) -> None:
        if self._pending_range_zoom is None:
            return
        fig = self._current_figure
        if fig is None or self._plot is None:
            return
        x_min, x_max = self._pending_range_zoom
        self._pending_range_zoom = None
        update_xaxis_range(fig, [x_min, x_max])
        try:
            self._plot.update_figure(fig)
        except RuntimeError as e:
            if "deleted" not in str(e).lower():
                raise

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

