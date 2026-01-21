"""Drawer view component.

This module provides a view component that displays the left drawer with tabs
for Analysis and Metadata. This component encapsulates the drawer layout and
organization of drawer toolbar widgets.
"""

from __future__ import annotations

from typing import Optional

from nicegui import ui

from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.gui_v2.views.analysis_toolbar_view import AnalysisToolbarView
from kymflow.gui_v2.views.contrast_view import ContrastView
from kymflow.gui_v2.views.line_plot_controls_view import LinePlotControlsView
from kymflow.gui_v2.views.metadata_tab_view import MetadataTabView
from kymflow.gui_v2.views.save_buttons_view import SaveButtonsView
from kymflow.gui_v2.views.stall_analysis_toolbar_view import StallAnalysisToolbarView
from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)


class DrawerView:
    """Drawer view component.

    This view displays the left drawer with tabs for organizing analysis tools
    and metadata editing. It acts as a container that organizes multiple drawer
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
        _drawer: NiceGUI drawer element (created in render()).
    """

    def __init__(
        self,
        save_buttons_view: SaveButtonsView,
        analysis_toolbar_view: AnalysisToolbarView,
        stall_analysis_toolbar_view: StallAnalysisToolbarView,
        contrast_view: ContrastView,
        line_plot_controls_view: LinePlotControlsView,
        metadata_tab_view: MetadataTabView,
    ) -> None:
        """Initialize drawer view.

        Args:
            save_buttons_view: Save buttons view instance.
            analysis_toolbar_view: Analysis toolbar view instance.
            stall_analysis_toolbar_view: Stall analysis toolbar view instance.
            contrast_view: Contrast view instance.
            line_plot_controls_view: Line plot controls view instance.
            metadata_tab_view: Metadata tab view instance.
        """
        self._save_buttons_view = save_buttons_view
        self._analysis_toolbar_view = analysis_toolbar_view
        self._stall_analysis_toolbar_view = stall_analysis_toolbar_view
        self._contrast_view = contrast_view
        self._line_plot_controls_view = line_plot_controls_view
        self._metadata_tab_view = metadata_tab_view
        self._drawer: Optional[ui.drawer] = None

    def render(self) -> ui.drawer:
        """Create the drawer UI.

        Always creates fresh UI elements because NiceGUI creates a new container
        context on each page navigation. Old UI elements are automatically cleaned
        up by NiceGUI when navigating away.

        Returns:
            The NiceGUI drawer element.
        """
        # Create drawer at page level (must be before column)
        with ui.drawer(side="left", value=False).classes("w-80 p-4").props("behavior=desktop") as drawer:
            self._drawer = drawer
            with ui.column().classes("w-full gap-4"):
                # Tabs for organizing drawer content
                with ui.tabs().classes("w-full") as tabs:
                    tab_analysis = ui.tab("Analysis")
                    tab_metadata = ui.tab("Metadata")
                
                # Tab panels - content for each tab
                with ui.tab_panels(tabs, value=tab_analysis).classes("w-full"):
                    # Analysis tab panel - contains all current drawer content
                    with ui.tab_panel(tab_analysis):
                        with ui.column().classes("w-full gap-4"):
                            # Save buttons section
                            self._save_buttons_view.render()

                            # Analysis toolbar section - in disclosure triangle
                            with ui.expansion("Analysis", value=True).classes("w-full"):
                                self._analysis_toolbar_view.render()
                            
                            # Task progress section
                            # COMMENTED OUT: Progress toolbar is currently broken because multiprocessing
                            # for 'analyze flow' does not work properly. Task state updates are not
                            # being communicated correctly across processes, causing the progress bar
                            # to not update. Re-enable once multiprocessing task state communication is fixed.
                            # ui.label("Progress").classes("text-sm font-semibold mt-2")
                            # self._drawer_task_progress_view.render()
                            
                            # Stall analysis section - in disclosure triangle
                            with ui.expansion("Stall Analysis", value=True).classes("w-full"):
                                self._stall_analysis_toolbar_view.render()
                            
                            # Contrast section - in disclosure triangle
                            with ui.expansion("Contrast", value=True).classes("w-full"):
                                self._contrast_view.render()
                            
                            # Line plot controls section - in disclosure triangle
                            with ui.expansion("Line Plot Controls", value=True).classes("w-full"):
                                self._line_plot_controls_view.render()
                    
                    # Metadata tab panel - contains metadata editing widgets
                    with ui.tab_panel(tab_metadata):
                        with ui.column().classes("w-full gap-4"):
                            self._metadata_tab_view.render()
        
        return drawer

    def initialize_views(
        self,
        current_file: Optional[KymImage],
        current_roi: Optional[int],
        theme_mode: str,
    ) -> None:
        """Initialize drawer views with current state.

        Called by parent to set up drawer views with current AppState values.
        This ensures drawer shows current selection/theme on first render.

        Args:
            current_file: Currently selected file, or None if no selection.
            current_roi: Currently selected ROI ID, or None if no selection.
            theme_mode: Current theme mode (e.g., "dark" or "light").
        """
        if current_file is not None:
            self._analysis_toolbar_view.set_selected_file(current_file)
            self._save_buttons_view.set_selected_file(current_file)
            self._stall_analysis_toolbar_view.set_selected_file(current_file)
            self._contrast_view.set_selected_file(current_file)
            self._line_plot_controls_view.set_selected_file(current_file)
            self._metadata_tab_view.set_selected_file(current_file)
        
        if current_roi is not None:
            self._analysis_toolbar_view.set_selected_roi(current_roi)
            self._stall_analysis_toolbar_view.set_selected_roi(current_roi)
            self._line_plot_controls_view.set_selected_roi(current_roi)
        
        # Initialize contrast view theme
        self._contrast_view.set_theme(theme_mode)
        # Note: Display params will be updated via ImageDisplayChange events from bindings

    @property
    def drawer(self) -> Optional[ui.drawer]:
        """Return the NiceGUI drawer element."""
        return self._drawer
