"""Drawer view component.

This module provides a view component that displays the left splitter pane with tabs
for Analysis, Plotting, Metadata, and About. This component encapsulates the splitter pane layout and
organization of toolbar widgets.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Optional

from nicegui import ui

from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.utils.logging import get_logger
from kymflow.gui_v2.views.about_tab_view import AboutTabView
from kymflow.gui_v2.views.analysis_toolbar_view import AnalysisToolbarView
from kymflow.gui_v2.views.contrast_view import ContrastView
from kymflow.gui_v2.views.line_plot_controls_view import LinePlotControlsView
from kymflow.gui_v2.views.metadata_tab_view import MetadataTabView
from kymflow.gui_v2.views.save_buttons_view import SaveButtonsView
# DEPRECATED: Stall analysis is deprecated
# from kymflow.gui_v2.views.stall_analysis_toolbar_view import StallAnalysisToolbarView

logger = get_logger(__name__)


class DrawerView:
    """Drawer view component.

    This view displays the left splitter pane with tabs for organizing analysis tools,
    plotting controls, and metadata editing. It acts as a container that organizes multiple toolbar
    views and delegates operations to them.

    Lifecycle:
        - UI elements are created in render() (not __init__) to ensure correct
          DOM placement within NiceGUI's client context
        - Data updates via setter methods (called by parent)
        - Child views handle their own event emission

    Attributes:
        _save_buttons_view: Save buttons view instance.
        _analysis_toolbar_view: Analysis toolbar view instance.
        _stall_analysis_toolbar_view: Stall analysis toolbar view instance.
        _contrast_view: Contrast view instance.
        _line_plot_controls_view: Line plot controls view instance.
        _metadata_tab_view: Metadata tab view instance.
    """

    def __init__(
        self,
        save_buttons_view: SaveButtonsView,
        analysis_toolbar_view: AnalysisToolbarView,
        stall_analysis_toolbar_view: Optional[Any],  # DEPRECATED: StallAnalysisToolbarView | None
        contrast_view: ContrastView,
        line_plot_controls_view: LinePlotControlsView,
        metadata_tab_view: MetadataTabView,
        about_tab_view: AboutTabView,
    ) -> None:
        """Initialize drawer view.

        Args:
            save_buttons_view: Save buttons view instance.
            analysis_toolbar_view: Analysis toolbar view instance.
            stall_analysis_toolbar_view: Stall analysis toolbar view instance (DEPRECATED, can be None).
            contrast_view: Contrast view instance.
            line_plot_controls_view: Line plot controls view instance.
            metadata_tab_view: Metadata tab view instance.
        """
        self._save_buttons_view = save_buttons_view
        self._analysis_toolbar_view = analysis_toolbar_view
        # DEPRECATED: Stall analysis is deprecated
        self._stall_analysis_toolbar_view = stall_analysis_toolbar_view
        self._contrast_view = contrast_view
        self._line_plot_controls_view = line_plot_controls_view
        self._metadata_tab_view = metadata_tab_view
        self._about_tab_view = about_tab_view

    def render(self, *, on_tab_click: Optional[Callable[[], None]] = None) -> None:
        """Create the splitter pane UI.

        Always creates fresh UI elements because NiceGUI creates a new container
        context on each page navigation. Old UI elements are automatically cleaned
        up by NiceGUI when navigating away.

        This method renders into the current container context (expected to be
        splitter.before). It does not return a UI element since it renders
        directly into the parent container.

        Args:
            on_tab_click: Optional callback to call when a tab is clicked (for auto-expand behavior).
        """
        # Add CSS for icon-only tabs with smaller icons/fonts
        ui.add_css("""
            .icon_only_tabs .q-tab__label { display: none; }
            .icon_only_tabs .q-tab__icon { font-size: 24px; }
            .icon_only_tabs .q-tab { min-height: 34px; padding: 0 6px; }
            .icon_only_tabs .q-tab__content { padding: 0; }

            @layer overrides {
            /* Reusable knob: apply this class to the EXPANSION HEADER via header-class */
            .my-expansion-header-shift-left {
                margin-left: -32px !important;  /* adjust: -8px, -12px, -16px, -24px */
            }
            }
        """)

        with ui.row(wrap=False).classes("w-full h-full items-start"):
            # Left side: Vertical tabs for organizing splitter pane content
            with ui.tabs().props('vertical dense').classes("w-12 shrink-0 icon_only_tabs") as tabs:
                tab_analysis = ui.tab("Analysis", icon="science").tooltip("Analysis")
                tab_plotting = ui.tab("Plotting", icon="bar_chart").tooltip("Plotting")
                tab_metadata = ui.tab("Metadata", icon="description").tooltip("Metadata")
                tab_about = ui.tab("About", icon="info").tooltip("About")
            
            # Auto-expand left pane when user clicks a tab icon (while minimized)
            if on_tab_click is not None:
                for t in (tab_analysis, tab_plotting, tab_metadata, tab_about):
                    t.on('click', lambda e: on_tab_click())
            
            # Right side: Tab panels - content for each tab
            with ui.tab_panels(tabs, value=tab_analysis) \
                    .props('vertical animated') \
                    .classes("flex-grow min-w-0 p-4"):
                    # Analysis tab panel - contains analysis tools and save buttons
                    with ui.tab_panel(tab_analysis):
                        with ui.column().classes("w-full gap-4"):
                            # Save buttons section
                            self._save_buttons_view.render()

                            # Analysis toolbar section
                            self._analysis_toolbar_view.render()
                            
                            # Task progress section
                            # COMMENTED OUT: Progress toolbar is currently broken because multiprocessing
                            # for 'analyze flow' does not work properly. Task state updates are not
                            # being communicated correctly across processes, causing the progress bar
                            # to not update. Re-enable once multiprocessing task state communication is fixed.
                            # ui.label("Progress").classes("text-sm font-semibold mt-2")
                            # self._drawer_task_progress_view.render()
                            
                            # DEPRECATED: Stall analysis is deprecated
                            # # Stall analysis section - in disclosure triangle (default closed)
                            # if self._stall_analysis_toolbar_view is not None:
                            #     with ui.expansion("Stall Analysis", value=False) \
                            #         .props('header-class="my-expansion-header-shift-left"') \
                            #         .classes("w-full"):
                            #         self._stall_analysis_toolbar_view.render()
                    
                    # Plotting tab panel - contains plotting and visualization controls
                    with ui.tab_panel(tab_plotting):
                        with ui.column().classes("w-full gap-4"):

                            # Line plot controls section - in disclosure triangle
                            # with ui.expansion("Line Plot Controls", value=True).classes("w-full"):
                            self._line_plot_controls_view.render()

                            # Contrast section - in disclosure triangle
                            with ui.expansion("Contrast", value=True) \
                                .props('header-class="my-expansion-header-shift-left"') \
                                .classes("w-full"):
                                self._contrast_view.render()
                            
                    
                    # Metadata tab panel - contains metadata editing widgets
                    with ui.tab_panel(tab_metadata):
                        with ui.column().classes("w-full gap-4"):
                            self._metadata_tab_view.render()
                    
                    # About tab panel - contains version info and logs
                    with ui.tab_panel(tab_about):
                        with ui.column().classes("w-full gap-4"):
                            self._about_tab_view.render()

    def initialize_views(
        self,
        current_file: Optional[KymImage],
        current_roi: Optional[int],
        theme_mode: str,
    ) -> None:
        """Initialize splitter pane views with current state.

        Called by parent to set up splitter pane views with current AppState values.
        This ensures splitter pane shows current selection/theme on first render.

        Args:
            current_file: Currently selected file, or None if no selection.
            current_roi: Currently selected ROI ID, or None if no selection.
            theme_mode: Current theme mode (e.g., "dark" or "light").
        """
        if current_file is not None:
            self._analysis_toolbar_view.set_selected_file(current_file)
            self._save_buttons_view.set_selected_file(current_file)
            # DEPRECATED: Stall analysis is deprecated
            # if self._stall_analysis_toolbar_view is not None:
            #     self._stall_analysis_toolbar_view.set_selected_file(current_file)
            self._contrast_view.set_selected_file(current_file)
            self._line_plot_controls_view.set_selected_file(current_file)
            self._metadata_tab_view.set_selected_file(current_file)
        
        if current_roi is not None:
            self._analysis_toolbar_view.set_selected_roi(current_roi)
            # DEPRECATED: Stall analysis is deprecated
            # if self._stall_analysis_toolbar_view is not None:
            #     self._stall_analysis_toolbar_view.set_selected_roi(current_roi)
            self._line_plot_controls_view.set_selected_roi(current_roi)
        
        # Initialize contrast view theme
        self._contrast_view.set_theme(theme_mode)
        # Note: Display params will be updated via ImageDisplayChange events from bindings
