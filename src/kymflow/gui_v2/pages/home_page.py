"""Home page for GUI v2 with folder selection and file table."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from nicegui import ui

from kymflow.gui.app_context import AppContext
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.controllers.analysis_controller import AnalysisController
from kymflow.gui_v2.controllers.app_state_bridge import AppStateBridgeController
from kymflow.gui_v2.controllers.file_selection_controller import FileSelectionController
from kymflow.gui_v2.controllers.file_table_persistence import FileTablePersistenceController
from kymflow.gui_v2.controllers.folder_controller import FolderController
from kymflow.gui_v2.controllers.image_display_controller import ImageDisplayController
from kymflow.gui_v2.controllers.metadata_controller import MetadataController
from kymflow.gui_v2.controllers.roi_selection_controller import ROISelectionController
from kymflow.gui_v2.controllers.save_controller import SaveController
from kymflow.gui_v2.controllers.task_state_bridge import TaskStateBridgeController
from kymflow.gui_v2.events import SelectionOrigin
from kymflow.gui_v2.pages.base_page import BasePage
from kymflow.gui_v2.views.analysis_toolbar_bindings import AnalysisToolbarBindings
from kymflow.gui_v2.views.analysis_toolbar_view import AnalysisToolbarView
from kymflow.gui_v2.views.contrast_bindings import ContrastBindings
from kymflow.gui_v2.views.contrast_view import ContrastView
from kymflow.gui_v2.views.file_table_bindings import FileTableBindings
from kymflow.gui_v2.views.file_table_view import FileTableView
from kymflow.gui_v2.views.folder_selector_view import FolderSelectorView
from kymflow.gui_v2.views.image_line_viewer_bindings import ImageLineViewerBindings
from kymflow.gui_v2.views.image_line_viewer_view import ImageLineViewerView
from kymflow.gui_v2.views.metadata_experimental_bindings import MetadataExperimentalBindings
from kymflow.gui_v2.views.metadata_experimental_view import MetadataExperimentalView
from kymflow.gui_v2.views.metadata_header_bindings import MetadataHeaderBindings
from kymflow.gui_v2.views.metadata_header_view import MetadataHeaderView
from kymflow.gui_v2.views.save_buttons_bindings import SaveButtonsBindings
from kymflow.gui_v2.views.save_buttons_view import SaveButtonsView
from kymflow.gui_v2.views.task_progress_bindings import TaskProgressBindings
from kymflow.gui_v2.views.task_progress_view import TaskProgressView

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
        self._image_display_controller: ImageDisplayController | None = None
        self._metadata_controller: MetadataController | None = None
        self._analysis_controller: AnalysisController | None = None
        self._save_controller: SaveController | None = None
        self._task_state_bridge: TaskStateBridgeController | None = None
        self._persistence: FileTablePersistenceController | None = None

        # View objects (created in __init__, UI elements created in build())
        self._folder_view = FolderSelectorView(bus, context.app_state)
        self._table_view = FileTableView(on_selected=bus.emit, selection_mode="single")
        self._image_line_viewer = ImageLineViewerView(on_roi_selected=bus.emit)
        self._contrast_view = ContrastView(on_image_display_change=bus.emit)
        self._metadata_experimental_view = MetadataExperimentalView(on_metadata_update=bus.emit)
        self._metadata_header_view = MetadataHeaderView(on_metadata_update=bus.emit)
        self._analysis_toolbar_view = AnalysisToolbarView(
            on_analysis_start=bus.emit, on_analysis_cancel=bus.emit
        )
        self._task_progress_view = TaskProgressView()
        self._save_buttons_view = SaveButtonsView(
            on_save_selected=bus.emit, on_save_all=bus.emit
        )
        self._table_bindings: FileTableBindings | None = None
        self._image_line_viewer_bindings: ImageLineViewerBindings | None = None
        self._contrast_bindings: ContrastBindings | None = None
        self._metadata_experimental_bindings: MetadataExperimentalBindings | None = None
        self._metadata_header_bindings: MetadataHeaderBindings | None = None
        self._analysis_toolbar_bindings: AnalysisToolbarBindings | None = None
        self._task_progress_bindings: TaskProgressBindings | None = None
        self._save_buttons_bindings: SaveButtonsBindings | None = None

        # Per-client state tracking
        self._restored_once: bool = False
        self._setup_complete: bool = False

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
        self._image_display_controller = ImageDisplayController(
            self.context.app_state, self.bus
        )
        self._metadata_controller = MetadataController(
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
        self._contrast_bindings = ContrastBindings(self.bus, self._contrast_view)
        self._metadata_experimental_bindings = MetadataExperimentalBindings(
            self.bus, self._metadata_experimental_view
        )
        self._metadata_header_bindings = MetadataHeaderBindings(
            self.bus, self._metadata_header_view
        )
        self._analysis_toolbar_bindings = AnalysisToolbarBindings(
            self.bus, self._analysis_toolbar_view
        )
        self._task_progress_bindings = TaskProgressBindings(
            self.bus, self._task_progress_view
        )
        self._save_buttons_bindings = SaveButtonsBindings(
            self.bus, self._save_buttons_view
        )

        self._setup_complete = True

    def build(self) -> None:
        """Build the Home page UI.

        Creates the folder selector and file table UI elements. This method
        is called every time the page is rendered, but controllers/bindings
        are only created once per client (in _ensure_setup()).

        Selection restoration happens after the UI is created, but only once
        per client session to avoid overwriting user selections.
        """
        with ui.column().classes("w-full p-4 gap-4"):
            # Folder selector FIRST (renders first in DOM)
            initial_folder = self.context.app_state.folder or Path(".")
            self._folder_view.render(initial_folder=initial_folder)

            # Analysis toolbar, progress, and save buttons
            with ui.row().classes("w-full items-start gap-4"):
                with ui.column().classes("flex-1 gap-2"):
                    self._analysis_toolbar_view.render()
                with ui.column().classes("shrink gap-2"):
                    self._task_progress_view.render()
                with ui.column().classes("shrink gap-2"):
                    self._save_buttons_view.render()

            # Initialize analysis toolbar and save buttons with current file
            current_file = self.context.app_state.selected_file
            if current_file is not None:
                self._analysis_toolbar_view.set_selected_file(current_file)
                self._save_buttons_view.set_selected_file(current_file)

            # File table SECOND (creates grid ui here) - in disclosure triangle
            with ui.expansion("Files", value=True).classes("w-full"):
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

            # Contrast widget - in disclosure triangle
            with ui.expansion("Contrast Controls", value=False).classes("w-full"):
                self._contrast_view.render()

                # Initialize contrast view with current AppState
                current_file = self.context.app_state.selected_file
                if current_file is not None:
                    self._contrast_view.set_selected_file(current_file)
                # Get current display params from AppState if available
                # Note: AppState doesn't store display params directly, so we'll initialize with defaults
                # The view will be updated when ImageDisplayChange events arrive
                self._contrast_view.set_theme(self.context.app_state.theme_mode)

            # Image/line viewer THIRD (creates plot ui here) - in disclosure triangle
            with ui.expansion("Image & Line Viewer", value=True).classes("w-full"):
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

            # Metadata widgets - both in single disclosure triangle
            with ui.expansion("Metadata", value=True).classes("w-full"):
                # Experimental metadata widget
                self._metadata_experimental_view.render()

                # Header metadata widget
                self._metadata_header_view.render()

                # Initialize metadata views with current AppState
                current_file = self.context.app_state.selected_file
                if current_file is not None:
                    self._metadata_experimental_view.set_selected_file(current_file)
                    self._metadata_header_view.set_selected_file(current_file)

            # Restore selection once per client (after UI is created)
            if not self._restored_once:
                if self._persistence is not None:
                    restored = self._persistence.restore_selection()
                    if restored:
                        self._table_view.set_selected_paths(
                            restored, origin=SelectionOrigin.RESTORE
                        )
                self._restored_once = True