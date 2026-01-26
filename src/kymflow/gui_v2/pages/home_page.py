"""Home page for GUI v2 with folder selection and file table."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from nicegui import ui

from kymflow.gui_v2.app_context import AppContext
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.controllers import (
    AddKymEventController,
    AnalysisController,
    AppStateBridgeController,
    DeleteKymEventController,
    EventSelectionController,
    FileSelectionController,
    FileTablePersistenceController,
    FolderController,
    ImageDisplayController,
    KymEventRangeStateController,
    MetadataController,
    ROISelectionController,
    SaveController,
    TaskStateBridgeController,
    VelocityEventUpdateController,
)
from kymflow.gui_v2.events import SelectionOrigin
from kymflow.gui_v2.pages.base_page import BasePage
from kymflow.gui_v2.views import (
    AboutTabView,
    AnalysisToolbarBindings,
    AnalysisToolbarView,
    ContrastBindings,
    ContrastView,
    DrawerView,
    FileTableBindings,
    FileTableView,
    FolderSelectorView,
    ImageLineViewerBindings,
    ImageLineViewerView,
    KymEventBindings,
    KymEventView,
    LinePlotControlsBindings,
    LinePlotControlsView,
    MetadataExperimentalBindings,
    MetadataExperimentalView,
    MetadataHeaderBindings,
    MetadataHeaderView,
    MetadataTabView,
    SaveButtonsBindings,
    SaveButtonsView,
    StallAnalysisToolbarBindings,
    StallAnalysisToolbarView,
    TaskProgressBindings,
    TaskProgressView,
)

if TYPE_CHECKING:
    pass


class HomePage(BasePage):
    """Home page: folder selector + file table wired through the event bus.

    This page provides the main file browsing and selection interface:
    - Folder selection and reload
    - File table with single selection
    - Automatic selection persistence across page reloads

    Lifecycle:
        - Controllers and bindings are created once per client in _ensure_setup()
        - UI elements are created fresh on each render() in build()
        - Selection is restored once per client session after UI is created

    Attributes:
        _bridge: Bridges AppState callbacks to event bus.
        _folder_controller: Handles folder selection events.
        _file_selection_controller: Handles file selection events.
        _persistence: Persists file selection to browser storage.
        _folder_view: Folder selector UI component.
        _table_view: File table UI component (CustomAgGrid).
        _table_bindings: Binds table view to event bus (state → view updates).
        _restored_once: Tracks if selection has been restored for this client.
    """

    def __init__(self, context: AppContext, bus: EventBus) -> None:
        """Initialize HomePage.

        Args:
            context: Shared application context.
            bus: Per-client EventBus instance.
        """
        super().__init__(context, bus)

        # Controllers and bindings will be created in _ensure_setup() (once per client)
        self._bridge: AppStateBridgeController | None = None
        self._folder_controller: FolderController | None = None
        self._file_selection_controller: FileSelectionController | None = None
        self._roi_selection_controller: ROISelectionController | None = None
        self._event_selection_controller: EventSelectionController | None = None
        self._image_display_controller: ImageDisplayController | None = None
        self._kym_event_range_state_controller: KymEventRangeStateController | None = None
        self._metadata_controller: MetadataController | None = None
        self._velocity_event_update_controller: VelocityEventUpdateController | None = None
        self._add_kym_event_controller: AddKymEventController | None = None
        self._delete_kym_event_controller: DeleteKymEventController | None = None
        self._analysis_controller: AnalysisController | None = None
        self._save_controller: SaveController | None = None
        self._task_state_bridge: TaskStateBridgeController | None = None
        self._persistence: FileTablePersistenceController | None = None

        # View objects (created in __init__, UI elements created in build())
        self._folder_view = FolderSelectorView(bus, context.app_state)
        self._table_view = FileTableView(
            on_selected=bus.emit,
            on_metadata_update=bus.emit,
            selection_mode="single",
        )
        self._image_line_viewer = ImageLineViewerView(
            on_roi_selected=bus.emit,
            on_kym_event_x_range=bus.emit,
        )
        self._event_view = KymEventView(
            on_selected=bus.emit,
            on_event_update=bus.emit,
            on_range_state=bus.emit,
            on_add_event=bus.emit,
            on_delete_event=bus.emit,
            selection_mode="single",
        )
        self._table_bindings: FileTableBindings | None = None
        self._image_line_viewer_bindings: ImageLineViewerBindings | None = None
        self._event_bindings: KymEventBindings | None = None

        # Splitter pane toolbar views
        self._drawer_analysis_toolbar_view = AnalysisToolbarView(
            on_analysis_start=bus.emit, on_analysis_cancel=bus.emit
        )
        self._drawer_task_progress_view = TaskProgressView()
        self._drawer_save_buttons_view = SaveButtonsView(
            on_save_selected=bus.emit, on_save_all=bus.emit
        )
        self._drawer_stall_analysis_toolbar_view = StallAnalysisToolbarView()
        self._drawer_contrast_view = ContrastView(on_image_display_change=bus.emit)
        self._drawer_line_plot_controls_view = LinePlotControlsView(
            on_filter_change=self._on_drawer_filter_change,
            on_full_zoom=self._on_drawer_full_zoom,
        )
        # Splitter pane metadata views
        self._drawer_metadata_experimental_view = MetadataExperimentalView(on_metadata_update=bus.emit)
        self._drawer_metadata_header_view = MetadataHeaderView(on_metadata_update=bus.emit)
        self._drawer_metadata_tab_view = MetadataTabView(
            self._drawer_metadata_experimental_view,
            self._drawer_metadata_header_view,
        )
        self._drawer_about_tab_view = AboutTabView()
        # Drawer view (organizes all splitter pane content)
        self._drawer_view = DrawerView(
            save_buttons_view=self._drawer_save_buttons_view,
            analysis_toolbar_view=self._drawer_analysis_toolbar_view,
            stall_analysis_toolbar_view=self._drawer_stall_analysis_toolbar_view,
            contrast_view=self._drawer_contrast_view,
            line_plot_controls_view=self._drawer_line_plot_controls_view,
            metadata_tab_view=self._drawer_metadata_tab_view,
            about_tab_view=self._drawer_about_tab_view,
        )
        self._drawer_analysis_toolbar_bindings: AnalysisToolbarBindings | None = None
        self._drawer_task_progress_bindings: TaskProgressBindings | None = None
        self._drawer_save_buttons_bindings: SaveButtonsBindings | None = None
        self._drawer_stall_analysis_toolbar_bindings: StallAnalysisToolbarBindings | None = None
        self._drawer_contrast_bindings: ContrastBindings | None = None
        self._drawer_line_plot_controls_bindings: LinePlotControlsBindings | None = None
        self._drawer_metadata_experimental_bindings: MetadataExperimentalBindings | None = None
        self._drawer_metadata_header_bindings: MetadataHeaderBindings | None = None

        # Per-client state tracking
        self._restored_once: bool = False
        self._setup_complete: bool = False
        self._full_zoom_shortcut_registered: bool = False
        self._full_zoom_shortcut_event: str = "kymflow_full_zoom_enter"

    def _ensure_setup(self) -> None:
        """Ensure controllers and bindings are set up once per client.

        This method is idempotent and will only create controllers/bindings
        once per client session, preventing duplicate event subscriptions.
        """
        if self._setup_complete:
            return

        # Controllers (subscribe to events once per client)
        self._bridge = AppStateBridgeController(self.context.app_state, self.bus)
        self._folder_controller = FolderController(self.context.app_state, self.bus)
        self._file_selection_controller = FileSelectionController(
            self.context.app_state, self.bus
        )
        self._roi_selection_controller = ROISelectionController(
            self.context.app_state, self.bus
        )
        self._event_selection_controller = EventSelectionController(
            self.context.app_state, self.bus
        )
        self._image_display_controller = ImageDisplayController(
            self.context.app_state, self.bus
        )
        self._kym_event_range_state_controller = KymEventRangeStateController(self.bus)
        self._metadata_controller = MetadataController(
            self.context.app_state, self.bus
        )
        self._velocity_event_update_controller = VelocityEventUpdateController(
            self.context.app_state, self.bus
        )
        self._add_kym_event_controller = AddKymEventController(
            self.context.app_state, self.bus
        )
        self._delete_kym_event_controller = DeleteKymEventController(
            self.context.app_state, self.bus
        )
        self._analysis_controller = AnalysisController(
            self.context.app_state, self.context.home_task, self.bus
        )
        self._save_controller = SaveController(
            self.context.app_state, self.context.home_task, self.bus
        )
        self._task_state_bridge = TaskStateBridgeController(
            self.context.home_task, self.bus, task_type="home"
        )

        self._persistence = FileTablePersistenceController(
            self.context.app_state,
            self.bus,
            storage_key="kymflow_selected_file_path_v2",
        )

        # Bindings (subscribe to events once per client)
        self._table_bindings = FileTableBindings(self.bus, self._table_view)
        self._image_line_viewer_bindings = ImageLineViewerBindings(
            self.bus, self._image_line_viewer
        )
        self._event_bindings = KymEventBindings(self.bus, self._event_view)

        # Splitter pane toolbar bindings
        self._drawer_analysis_toolbar_bindings = AnalysisToolbarBindings(
            self.bus, self._drawer_analysis_toolbar_view
        )
        self._drawer_task_progress_bindings = TaskProgressBindings(
            self.bus, self._drawer_task_progress_view
        )
        self._drawer_save_buttons_bindings = SaveButtonsBindings(
            self.bus, self._drawer_save_buttons_view
        )
        self._drawer_stall_analysis_toolbar_bindings = StallAnalysisToolbarBindings(
            self.bus, self._drawer_stall_analysis_toolbar_view
        )
        self._drawer_contrast_bindings = ContrastBindings(
            self.bus, self._drawer_contrast_view
        )
        self._drawer_line_plot_controls_bindings = LinePlotControlsBindings(
            self.bus, self._drawer_line_plot_controls_view
        )
        self._drawer_metadata_experimental_bindings = MetadataExperimentalBindings(
            self.bus, self._drawer_metadata_experimental_view
        )
        self._drawer_metadata_header_bindings = MetadataHeaderBindings(
            self.bus, self._drawer_metadata_header_view
        )

        # Set up stall analysis callback to trigger plot update
        self._drawer_stall_analysis_toolbar_view.set_on_stall_analysis_complete(
            self._on_drawer_stall_analysis_complete
        )

        self._setup_complete = True

    def _on_drawer_stall_analysis_complete(self) -> None:
        """Callback when splitter pane stall analysis completes - triggers plot update."""
        # Trigger plot re-render by calling set_selected_roi with current ROI
        # This will cause the plot to refresh with the new stall analysis data
        current_roi = self.context.app_state.selected_roi_id
        if current_roi is not None:
            self._image_line_viewer.set_selected_roi(current_roi)

    def _on_drawer_filter_change(self, remove_outliers: bool, median_filter: bool) -> None:
        """Callback when splitter pane filter controls change - applies filters to plot."""
        self._image_line_viewer.apply_filters(remove_outliers, median_filter)

    def _on_drawer_full_zoom(self) -> None:
        """Callback when splitter pane full zoom button is clicked - resets plot zoom."""
        self._image_line_viewer.reset_zoom()

    def _on_full_zoom_shortcut(self, _event) -> None:
        """Handle Enter/Return full-zoom shortcut when not editing."""
        if (
            self.context.app_state.selected_file is None
            or self.context.app_state.selected_roi_id is None
        ):
            return
        self._image_line_viewer.reset_zoom()

    def _register_full_zoom_shortcut(self) -> None:
        """Register a global Enter/Return shortcut for full zoom (unless editing)."""
        if self._full_zoom_shortcut_registered:
            return
        self._full_zoom_shortcut_registered = True
        ui.on(self._full_zoom_shortcut_event, self._on_full_zoom_shortcut)
        ui.run_javascript(
            """
(function() {
  if (window._kymflow_full_zoom_listener) return;
  window._kymflow_full_zoom_listener = true;
  window.addEventListener('keydown', (e) => {
    if (e.key !== 'Enter') return;
    const active = document.activeElement;
    const tag = active ? active.tagName : '';
    const isEditable = !!active && (
      active.isContentEditable ||
      tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' ||
      (active.classList && active.classList.contains('ag-cell-edit-input')) ||
      (active.closest && (active.closest('.ag-cell-inline-editing') || active.closest('.ag-cell-editor')))
    );
    if (isEditable) return;
    emitEvent('kymflow_full_zoom_enter', {});
  });
})();
            """
        )

    def render(self, *, page_title: str) -> None:
        """Override render to create splitter layout at page level.

        The splitter divides the page into two panes:
        - Left pane (before): Contains DrawerView with tabs and toolbars
        - Right pane (after): Contains main page content (folder selector, file table, viewer)

        Snap positions are percentages for the LEFT pane (before):
        - CLOSED = 6 (icon tabs always visible, minimum width)
        """
        ui.page_title(page_title)

        dark_mode = self.context.init_dark_mode_for_page()
        from kymflow.gui_v2.navigation import build_header
        
        # Build header without drawer toggle (no drawer needed with splitter)
        build_header(self.context, dark_mode, drawer_toggle_callback=None)
        self._register_full_zoom_shortcut()

        # Add CSS for splitter handle container
        ui.add_css("""
            .handle_wrap {
                height: 100%;
                display: flex;
                align-items: center;
                justify-content: center;
            }
        """)

        # Snap positions are percentages for the LEFT pane (before)
        CLOSED = 6
        OPEN_DEFAULT = 28
        last_open = {'value': OPEN_DEFAULT}

        # Create splitter layout
        with ui.splitter(value=CLOSED, limits=(CLOSED, 70)).classes('w-full h-screen') as splitter:
            def ensure_open() -> None:
                """If the left pane is collapsed, restore it to a reasonable open width."""
                if splitter.value <= (CLOSED + 2):
                    splitter.value = last_open['value']

            # LEFT: Splitter pane with tabs and toolbars
            with splitter.before:
                # Render drawer view content into splitter before pane
                self._drawer_view.render(on_tab_click=ensure_open)
                
                # Initialize drawer views with current state
                self._drawer_view.initialize_views(
                    current_file=self.context.app_state.selected_file,
                    current_roi=self.context.app_state.selected_roi_id,
                    theme_mode=self.context.app_state.theme_mode,
                )

            # RIGHT: Main page content
            with splitter.after:
                with ui.column().classes("w-full p-4 gap-4"):
                    # Ensure setup is called once per client before building
                    self._ensure_setup()
                    # build() creates fresh UI elements in the new container context
                    self.build()

            # SEPARATOR: toggle button lives on the handle
            with splitter.separator:
                with ui.element('div').classes('handle_wrap'):
                    def toggle_snap() -> None:
                        """If open-ish, remember current width and close; else reopen to last width."""
                        if splitter.value > (CLOSED + 2):
                            last_open['value'] = splitter.value
                            splitter.value = CLOSED
                        else:
                            splitter.value = last_open['value']

                    ui.button(icon='chevron_left', on_click=toggle_snap).props('flat dense')

    def build(self) -> None:
        """Build the Home page UI.

        Creates the folder selector and file table UI elements. This method
        is called every time the page is rendered, but controllers/bindings
        are only created once per client (in _ensure_setup()).

        Selection restoration happens after the UI is created, but only once
        per client session to avoid overwriting user selections.
        """
        # Folder selector FIRST (renders first in DOM)
        initial_folder = self.context.app_state.folder or Path(".")
        self._folder_view.render(initial_folder=initial_folder)

        # File table SECOND (creates grid ui here) - in disclosure triangle
        # with ui.expansion("Files", value=True).classes("w-full"):
        if 1:
            self._table_view.render()

            # Populate with current state (if already loaded, shows immediately)
            self._table_view.set_files(list(self.context.app_state.files))

            # Restore current selection from AppState (ensures visibility on navigation back)
            # This handles both initial load and navigation back scenarios
            current_file = self.context.app_state.selected_file
            if current_file is not None and hasattr(current_file, "path"):
                self._table_view.set_selected_paths(
                    [str(current_file.path)], origin=SelectionOrigin.EXTERNAL
                )

        # Image/line viewer THIRD (creates plot ui here) - in disclosure triangle
        # abb turned off expansion
        # with ui.expansion("Image & Line Viewer", value=True).classes("w-full"):
        if 1:
            self._image_line_viewer.render()

            # Initialize viewer with current AppState (if already set)
            # This ensures viewer shows current selection/theme on first render
            current_file = self.context.app_state.selected_file
            if current_file is not None:
                self._image_line_viewer.set_selected_file(current_file)
            current_roi = self.context.app_state.selected_roi_id
            if current_roi is not None:
                self._image_line_viewer.set_selected_roi(current_roi)
            self._image_line_viewer.set_theme(self.context.app_state.theme_mode)

        if 1:
            self._event_view.render()
            current_file = self.context.app_state.selected_file
            if current_file is not None:
                report = current_file.get_kym_analysis().get_velocity_report()
                self._event_view.set_events(report)
            current_roi = self.context.app_state.selected_roi_id
            if current_roi is not None:
                self._event_view.set_selected_roi(current_roi)

        # Restore selection once per client (after UI is created)
        if not self._restored_once:
            if self._persistence is not None:
                restored = self._persistence.restore_selection()
                if restored:
                    self._table_view.set_selected_paths(
                        restored, origin=SelectionOrigin.RESTORE
                    )
            self._restored_once = True