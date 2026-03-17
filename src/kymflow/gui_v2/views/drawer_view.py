"""Drawer view component.

This module provides a view component that displays the left splitter pane with tabs
for Analysis, Metadata, Options, Diameter, and About. This component encapsulates the splitter pane layout and
organization of toolbar widgets.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Optional

from nicegui import ui

from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.utils.logging import get_logger
from kymflow.gui_v2.views.about_tab_view import AboutTabView
from kymflow.gui_v2.views.analysis_toolbar_view import AnalysisToolbarView
from kymflow.gui_v2.views.metadata_tab_view import MetadataTabView
from kymflow.gui_v2.views.options_tab_view import OptionsTabView

logger = get_logger(__name__)


class DrawerView:
    """Drawer view component.

    This view displays the left splitter pane with tabs for organizing analysis tools
    and metadata editing. It acts as a container that organizes multiple toolbar
    views and delegates operations to them.

    Lifecycle:
        - UI elements are created in render() (not __init__) to ensure correct
          DOM placement within NiceGUI's client context
        - Data updates via setter methods (called by parent)
        - Child views handle their own event emission

    Attributes:
        _analysis_toolbar_view: Analysis toolbar view instance.
        _metadata_tab_view: Metadata tab view instance.
        _options_tab_view: Options tab view instance.
        _about_tab_view: About tab view instance.
    """

    def __init__(
        self,
        analysis_toolbar_view: AnalysisToolbarView,
        metadata_tab_view: MetadataTabView,
        about_tab_view: AboutTabView,
        options_tab_view: OptionsTabView,
    ) -> None:
        """Initialize drawer view.

        Args:
            analysis_toolbar_view: Analysis toolbar view instance.
            metadata_tab_view: Metadata tab view instance.
            about_tab_view: About tab view instance.
            options_tab_view: Options tab view instance.
        """
        self._analysis_toolbar_view = analysis_toolbar_view
        self._metadata_tab_view = metadata_tab_view
        self._about_tab_view = about_tab_view
        self._options_tab_view = options_tab_view
        self._tab_panels: Any = None  # Set in render(); used by get_current_tab()

    def get_current_tab(self) -> Any:
        """Return the currently selected tab element, or None if not yet rendered."""
        if self._tab_panels is None:
            return None
        return getattr(self._tab_panels, "value", None)

    def render(self, *, on_tab_click: Optional[Callable[[Any], None]] = None) -> None:
        """Create the splitter pane UI.

        Always creates fresh UI elements because NiceGUI creates a new container
        context on each page navigation. Old UI elements are automatically cleaned
        up by NiceGUI when navigating away.

        This method renders into the current container context (expected to be
        splitter.before). It does not return a UI element since it renders
        directly into the parent container.

        Args:
            on_tab_click: Optional callback(clicked_tab) when a tab is clicked.
                Receives the tab element that was clicked (for open/toggle behavior).
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
                tab_analysis = ui.tab("Analysis", icon="speed").tooltip("Analysis")
                tab_diameter = ui.tab("Diameter", icon="straighten").tooltip("Diameter")
                tab_metadata = ui.tab("Metadata", icon="description").tooltip("Metadata")
                tab_options = ui.tab("Options", icon="settings").tooltip("Options")
                tab_about = ui.tab("About", icon="info").tooltip("About")
            
            # Right side: Tab panels - content for each tab (store ref for get_current_tab)
            tab_panels = ui.tab_panels(tabs, value=tab_analysis).props("vertical animated").classes(
                "flex-grow min-w-0 p-4"
            )
            self._tab_panels = tab_panels

            # Tab click: pass clicked tab to callback (for open/toggle behavior)
            if on_tab_click is not None:
                for t in (tab_analysis, tab_diameter, tab_metadata, tab_options, tab_about):
                    t.on("click", lambda e, tab=t: on_tab_click(tab))

            with tab_panels:
                # Analysis tab panel - contains analysis tools
                with ui.tab_panel(tab_analysis):
                    with ui.column().classes("w-full gap-4"):
                        self._analysis_toolbar_view.render()

                # Diameter tab panel
                with ui.tab_panel(tab_diameter):
                    with ui.column().classes("w-full gap-4"):
                        pass  # placeholder

                # Metadata tab panel - contains metadata editing widgets
                with ui.tab_panel(tab_metadata):
                    with ui.column().classes("w-full gap-4"):
                        self._metadata_tab_view.render()

                # Options tab panel - contains app configuration settings
                with ui.tab_panel(tab_options):
                    with ui.column().classes("w-full gap-4"):
                        self._options_tab_view.render()

                # About tab panel - contains version info and logs
                with ui.tab_panel(tab_about):
                    with ui.column().classes("w-full gap-4"):
                        self._about_tab_view.render()

    def initialize_views(
        self,
        current_file: Optional[KymImage],
        current_channel: Optional[int],
        current_roi: Optional[int],
        theme_mode: str,
    ) -> None:
        """Initialize splitter pane views with current state.

        Called by parent to set up splitter pane views with current AppState values.
        This ensures splitter pane shows current selection/theme on first render.

        Args:
            current_file: Currently selected file, or None if no selection.
            current_channel: Currently selected channel index, or None.
            current_roi: Currently selected ROI ID, or None if no selection.
            theme_mode: Current theme mode (e.g., "dark" or "light").
        """
        if current_file is not None:
            self._analysis_toolbar_view.set_selected_file(
                current_file, current_channel, current_roi
            )
            self._metadata_tab_view.set_selected_file(current_file)
        
        if current_roi is not None:
            self._analysis_toolbar_view.set_selected_roi(current_roi)
        # Note: Display params will be updated via ImageDisplayChange events from bindings
