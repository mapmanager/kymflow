"""Image/line viewer view component using Plotly.

This module provides a view component that displays a combined kymograph image
and velocity plot using Plotly. The view emits ROISelection events when users
select ROIs from the dropdown, but does not subscribe to events (that's handled
by ImageLineViewerBindings).
"""

from __future__ import annotations

from typing import Callable, Dict, Any, Literal, Optional

import plotly.graph_objects as go
from nicegui import ui
from nicegui.events import GenericEventArguments  # for _on_relayout()

from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.plotting import (
    # plot_image_line_plotly,
    plot_image_line_plotly_v3,
    update_colorscale,
    update_contrast,
    # reset_image_zoom,  # DEPRECATED: Use dict-based updates instead (update_xaxis_range_v2, update_yaxis_range_v2)
    # update_xaxis_range,  # OLD: kept for reference during transition (replaced by update_xaxis_range_v2)
    update_xaxis_range_v2,
    update_yaxis_range_v2,
    select_kym_event_rect,
)
from kymflow.core.plotting.line_plots import refresh_kym_event_rects
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
        self._current_figure_dict: Optional[dict] = None
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
        # Event type filter state: dict mapping event_type (str) to bool (True = show, False = hide)
        # Initialize with same defaults as KymEventView to keep them in sync
        self._event_filter: Optional[dict[str, bool]] = {
            "baseline_drop": True,
            "baseline_rise": True,
            "nan_gap": False,
            "zero_gap": True,
            "User Added": True,
        }
        
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
            # self._create_plot(go.Figure())

            _emptyFigDict = {}
            self._plot = ui.plotly(_emptyFigDict).classes("w-full h-full")
            # Stable DOM id for JS access (dragmode toggling).
            self._plot.props(f"id={self._plot_div_id}")
            # abb when implementing getting user drawrect/rect selection
            # and setting start/stop of a single velocity event.
            self._plot.on("plotly_relayout", self._on_plotly_relayout)

    def ui_plotly_update_figure(self, fig: go.Figure | None = None) -> None:
        """Update the plotly plot with a new figure."""
        
        # logger.info('XXX DO NOT CALL THIS A LOT -->> SLOW')


        self._plot.update_figure(self._current_figure_dict)
        # self._plot.update()

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

        # logger.info(f'  e:{e}')

        payload: Dict[str, Any] = e.args  # <-- dict

        # logger.debug('=== in on_relayout() plotly_relayout received:')
        # logger.debug(f"  awaiting_range={self._awaiting_kym_event_range}, awaiting_roi_edit={self._awaiting_roi_edit}") 
        # logger.debug('  payload:')
        # from pprint import pprint
        # pprint(payload)

        # abb, check if payload has 'xaxis2' and 'xaxis'
        if 'xaxis2.range[0]' in payload.keys() and 'xaxis2.range[1]' in payload.keys():
            # set the x range for prev/next window
            x0 = payload['xaxis2.range[0]']
            x1 = payload['xaxis2.range[1]']
            logger.warning(f'setting x range for _scroll_x_impl() prev/next window: [{x0}, {x1}]')
            # needed for _scroll_x_impl()
            update_xaxis_range_v2(self._current_figure_dict, [x0, x1])
            # be careful here, this should be ok but leave out in case we need 
            # user set xaxis range for kym event
            # return


        x0, x1, y0, y1 = None, None, None, None  # default to no selection
        if 'selections[0].x0' in payload.keys():
            logger.info('  update "selections[0].x0" found')
            x0  = payload['selections[0].x0']
            x1  = payload['selections[0].x1']
            y0  = payload.get('selections[0].y0')
            y1  = payload.get('selections[0].y1')
            logger.info(f"  -> update Selection: x-range = [{x0}, {x1}], y-range = [{y0}, {y1}]")
        elif 'selections' not in payload.keys():
            print('  no selection found')
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
        # logger.debug(f'  self._pending_range_zoom:{self._pending_range_zoom}')
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
        # logger.warning('qqq turned off reset zoom')
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
        # logger.info(f"set _current_roi_id to '{roi_id}' {type(roi_id)}")
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

    def zoom_to_event(self, e: EventSelection) -> None:
        """Zoom the x-axis to an event if options request it."""
        safe_call(self._zoom_to_event_impl, e)

    def _zoom_to_event_impl(self, e: EventSelection) -> None:
        # Store selected event_id for visual highlighting (None clears selection)
        old_selected = self._selected_event_id
        self._selected_event_id = e.event_id
        
        # Early returns for invalid cases
        if e.event is None or e.options is None:
            # Update highlight if selection changed - use dict-based update
            if old_selected != e.event_id:
                # OLD: self._render_combined()  # Removed during refactor - now using dict-based updates
                if self._current_figure_dict is not None and self._plot is not None:
                    select_kym_event_rect(self._current_figure_dict, None, row=2)  # Deselect all
                    try:
                        self.ui_plotly_update_figure()
                    except RuntimeError as ex:
                        logger.error(f"Error updating selection: {ex}")
                        if "deleted" not in str(ex).lower():
                            raise
            return
        if self._current_roi_id is None or e.roi_id != self._current_roi_id:
            # ROI mismatch - update highlight if selection changed
            if old_selected != e.event_id:
                # OLD: self._render_combined()  # Removed during refactor - now using dict-based updates
                if self._current_figure_dict is not None and self._plot is not None:
                    select_kym_event_rect(self._current_figure_dict, None, row=2)  # Deselect all
                    try:
                        self.ui_plotly_update_figure()
                    except RuntimeError as ex:
                        logger.error(f"Error updating selection: {ex}")
                        if "deleted" not in str(ex).lower():
                            raise
            return
        if self._current_figure_dict is None or self._plot is None:
            return
        
        # Determine what needs updating
        needs_highlight = (old_selected != e.event_id)
        needs_zoom = (e.options.zoom and e.event is not None)
        
        # Update highlight using dict-based update (no render)
        if needs_highlight:
            # OLD: self._render_combined()  # Removed during refactor - now using dict-based updates
            select_kym_event_rect(self._current_figure_dict, e.event, row=2)
            try:
                self.ui_plotly_update_figure()
            except RuntimeError as ex:
                logger.error(f"Error updating selection: {ex}")
                if "deleted" not in str(ex).lower():
                    raise
        
        # If zoom is enabled, apply it as a fast partial update (axis range only)
        # This is very fast and doesn't cause a full re-render
        if needs_zoom:
            t_start = e.event.t_start
            pad = float(e.options.zoom_pad_sec)
            x_min = t_start - pad
            x_max = t_start + pad
            # Clamp zoom bounds to ROI time range using get_time_bounds()
            if self._current_file is not None and self._current_roi_id is not None:
                kym_analysis = self._current_file.get_kym_analysis()
                time_bounds = kym_analysis.get_time_bounds(self._current_roi_id)
                if time_bounds is not None:
                    time_min, time_max = time_bounds
                    x_min = max(x_min, time_min)
                    x_max = min(x_max, time_max)
                else:
                    # Fallback to image duration if time bounds not available
                    duration = self._current_file.image_dur
                    if duration is not None:
                        x_min = max(x_min, 0.0)
                        x_max = min(x_max, float(duration))
            elif self._current_file is not None:
                duration = self._current_file.image_dur
                if duration is not None:
                    x_min = max(x_min, 0.0)
                    x_max = min(x_max, float(duration))
            
            # Use dict-based update
            update_xaxis_range_v2(self._current_figure_dict, [x_min, x_max])
            try:
                self.ui_plotly_update_figure()
            except RuntimeError as ex:
                logger.error(f"Error updating zoom: {ex}")
                if "deleted" not in str(ex).lower():
                    raise
        
        # TODO: In next round, refactor filter changes and event data changes to use CRUD instead of full render

    def set_event_filter(self, event_filter: dict[str, bool] | None) -> None:
        """Set event type filter using CRUD operations (no full render).
        
        Args:
            event_filter: Dict mapping event_type (str) to bool (True = include, False = exclude),
                         or None to clear filter.
        """
        self._event_filter = event_filter
        
        # Check if we can use CRUD (dict-based update)
        if self._current_figure_dict is None:
            logger.warning(
                "set_event_filter: _current_figure_dict is None, falling back to full render"
            )
            self._render_combined()
            return
        
        # Validate we have required state
        if self._current_file is None:
            logger.warning("set_event_filter: _current_file is None, skipping")
            return
        
        if self._current_roi_id is None:
            logger.warning("set_event_filter: _current_roi_id is None, skipping")
            return
        
        # Get KymAnalysis and time_range
        kym_analysis = self._current_file.get_kym_analysis()
        if not kym_analysis.has_analysis(self._current_roi_id):
            logger.warning(
                "set_event_filter: no analysis for roi_id=%s, skipping", self._current_roi_id
            )
            return
        
        time_range = kym_analysis.get_time_bounds(self._current_roi_id)
        if time_range is None:
            logger.warning(
                "set_event_filter: no time bounds for roi_id=%s, skipping", self._current_roi_id
            )
            return
        
        # Use shared helper to clear and re-add event rects, restoring selection where possible
        refresh_kym_event_rects(
            self._current_figure_dict,
            kym_analysis,
            self._current_roi_id,
            time_range,
            row=2,
            event_filter=event_filter,
            selected_event_id=self._selected_event_id,
        )
        # Update the plot
        try:
            self.ui_plotly_update_figure()
        except RuntimeError as ex:
            logger.error(f"Error updating figure: {ex}")
            if "deleted" not in str(ex).lower():
                raise

    def _render_combined(self) -> None:
        """Render the combined image and line plot.
        
        This recreated fig from scratch with plot_image_line_plotly_v3()
        """
        
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
        # num_rois = kf.rois.numRois() if kf is not None else 0
        # plot_rois = (num_rois > 1)
        plot_rois = False

        # logger.debug(f'=== pyinstaller calling plot_image_line_plotly_v3()')
        
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
            event_filter=self._event_filter,
        )

        # Store figure reference
        self._set_uirevision(fig)
        self._current_figure = fig
        self._current_figure_dict = fig.to_dict()  # abb 20260209

        # Detect grid changes (1 row vs 2 rows) and rebuild plot if needed
        num_rows = 2 if getattr(fig.layout, "yaxis2", None) is not None else 1
        if self._last_num_rows is None:
            self._last_num_rows = num_rows

        try:
            # abb this is a core plot function !!!
            # self._plot.update_figure(fig)
            self.ui_plotly_update_figure()
        except RuntimeError as e:
            logger.error(f"Error updating figure: {e}")
            if "deleted" not in str(e).lower():
                raise
            # Client deleted, silently ignore

    def _set_uirevision(self, fig: go.Figure) -> None:
        """Apply the current uirevision to the figure."""
        fig.layout.uirevision = f"kymflow-plot-{self._uirevision}"

    def _reset_zoom(self, force_new_uirevision: bool = False) -> None:
        """Reset zoom while optionally forcing Plotly to drop preserved UI state.
        
        Uses dict-based updates for consistency with other partial updates.
        """
        kf = self._current_file
        if kf is None or self._plot is None or self._current_figure_dict is None:
            return

        # Calculate ranges from KymImage properties
        duration_seconds = kf.image_dur
        if duration_seconds is None:
            return

        space_um = kf.image_space
        if space_um is None:
            return
        # pixels_per_line = kf.pixels_per_line
        # if pixels_per_line is None:
        #     return

        # Update uirevision in dict if requested (forces Plotly to accept new ranges)
        if force_new_uirevision:
            self._uirevision += 1
            if 'layout' in self._current_figure_dict:
                self._current_figure_dict['layout']['uirevision'] = f"kymflow-plot-{self._uirevision}"

        # Reset x-axis (time) for both subplots (they're shared)
        x_range = [0.0, float(duration_seconds)]
        update_xaxis_range_v2(self._current_figure_dict, x_range)

        # Reset y-axis (position) for image subplot only (row 1)
        y_range = [0.0, space_um]
        update_yaxis_range_v2(self._current_figure_dict, y_range, row=1)

        try:
            self.ui_plotly_update_figure()
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
        median_filter_size = 3 if self._median_filter else 0

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
                logger.warning(f'successfully Updating Scatter trace y-values')
                trace.y = filtered_y
                break
        else:
            # No Scatter trace found, do full render
            logger.warning(f'No Scatter trace found, do full render -> _render_combined()')
            self._render_combined()
            return

        # Update the plot with modified figure (preserves zoom via uirevision)
        if self._plot is None:
            return
        try:
            # logger.debug(f'pyinstaller calling _plot.update_figure(fig)')
            # self._plot.update_figure(fig)
            self.ui_plotly_update_figure(fig)
        except RuntimeError as e:
            if "deleted" not in str(e).lower():
                raise
            # else:
            #     # logger.debug(f'pyinstaller swallowed/skipped Client deleted RuntimeError: {e}')
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
            # OLD: update_xaxis_range(fig, list(preserved_range))
            # NEW: Use dict-based update
            if self._current_figure_dict is not None and self._plot is not None:
                update_xaxis_range_v2(self._current_figure_dict, list(preserved_range))
                try:
                    self.ui_plotly_update_figure()
                except RuntimeError as e:
                    if "deleted" not in str(e).lower():
                        raise
            else:
                logger.warning("Cannot update x-axis range: _current_figure_dict is None")
        else:
            # No preserved range, apply pending range zoom if any
            self._apply_pending_range_zoom()

    def _apply_pending_range_zoom(self) -> None:
        if self._pending_range_zoom is None:
            return
        if self._current_figure_dict is None or self._plot is None:
            return
        x_min, x_max = self._pending_range_zoom
        self._pending_range_zoom = None
        # OLD: update_xaxis_range(fig, [x_min, x_max])
        # NEW: Use dict-based update
        update_xaxis_range_v2(self._current_figure_dict, [x_min, x_max])
        try:
            self.ui_plotly_update_figure()
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

    def scroll_x(self, direction: Literal["prev", "next"]) -> None:
        """Scroll the x-axis view to the previous or next window.

        Shifts the current x-axis range left (prev) or right (next) by one
        window width. Clamps to data time bounds so the view never goes
        out of range.

        Args:
            direction: "prev" to shift left, "next" to shift right.
        """
        safe_call(self._scroll_x_impl, direction)

    def _get_scroll_x_time_bounds(self) -> Optional[tuple[float, float]]:
        """Return (time_min, time_max) for the current file/ROI, or None if unavailable."""
        if self._current_file is None:
            return None
        if self._current_roi_id is not None:
            time_bounds = self._current_file.get_kym_analysis().get_time_bounds(
                self._current_roi_id
            )
            if time_bounds is not None:
                return time_bounds
        duration = self._current_file.image_dur
        if duration is not None:
            return (0.0, float(duration))
        return None

    def _scroll_x_impl(self, direction: Literal["prev", "next"]) -> None:
        """Internal implementation of scroll_x. Early returns log a reason for debugging."""
        # 1. Require figure and plot
        if self._current_figure_dict is None or self._plot is None:
            # logger.debug("scroll_x: no figure dict or plot, skipping")
            return
        # 2. Read current x range from layout
        layout = self._current_figure_dict.get("layout") or {}
        
        # logger.debug(f'_current_figure_dict:{self._current_figure_dict.keys()}')
        # logger.debug(f'layout.keys():{layout.keys()}')

        # if empty, force full range and try again
        # self._reset_zoom(force_new_uirevision=False)

        _x_axis_name = 'xaxis2'
        xaxis = layout.get(_x_axis_name) or {}  # abb in (2,1) subplot, we need xaxis2
        range_ = xaxis.get("range")
        # logger.debug(f'xaxis:{xaxis}')
        # logger.debug(f'range_:{range_}')

        # # if empty, force full range and try again
        # self._reset_zoom(force_new_uirevision=False)

        if not isinstance(range_, (list, tuple)) or len(range_) != 2:
            # logger.debug("scroll_x: invalid or missing xaxis range, skipping")
            return
        try:
            x_min = float(range_[0])
            x_max = float(range_[1])
        except (TypeError, ValueError):
            # logger.debug("scroll_x: xaxis range values not convertible to float, skipping")
            return
        width = x_max - x_min
        if width <= 0:
            # logger.debug("scroll_x: non-positive window width, skipping")
            return
        # 3. Get time bounds for clamping
        time_bounds = self._get_scroll_x_time_bounds()
        if time_bounds is None:
            # logger.debug("scroll_x: no time bounds (file/roi/duration), skipping")
            return
        time_min, time_max = time_bounds

        # 4. Compute new window (prev = shift left, next = shift right) and clamp
        if direction == "prev":
            new_min = x_min - width
            new_max = x_min
            if new_min < time_min:
                new_min = time_min
                new_max = min(new_min + width, time_max)
        else:
            new_min = x_max
            new_max = x_max + width
            if new_max > time_max:
                new_max = time_max
                new_min = max(new_max - width, time_min)

        # 5. Apply and push to client
        update_xaxis_range_v2(self._current_figure_dict, [new_min, new_max])
        try:
            self.ui_plotly_update_figure()
        except RuntimeError as e:
            if "deleted" not in str(e).lower():
                raise

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
            # self._plot.update_figure(fig)
            self.ui_plotly_update_figure(fig)
        except RuntimeError as e:
            if "deleted" not in str(e).lower():
                raise
            # Client deleted, silently ignore

