"""Home page for GUI v2 with folder selection and file table."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

from kymflow.gui_v2.app_context import AppContext
from kymflow.gui_v2.bus import EventBus
from kymflow.gui_v2.controllers import (
    AddKymEventController,
    AddRoiController,
    AnalysisController,
    AnalysisUpdateController,
    AppStateBridgeController,
    DeleteKymEventController,
    DeleteRoiController,
    EditRoiController,
    EventAnalysisController,
    EventSelectionController,
    FileSelectionController,
    FileTablePersistenceController,
    FolderController,
    ImageDisplayController,
    KymEventCacheSyncController,
    KymEventRangeStateController,
    MetadataController,
    NextPrevFileController,
    ROISelectionController,
    RoiEditStateController,
    SaveController,
    TaskStateBridgeController,
    VelocityEventUpdateController,
)
from kymflow.gui_v2.events import FileSelection, NextPrevFileEvent, SaveSelected, SelectionOrigin
from kymflow.gui_v2.pages.base_page import BasePage
from kymflow.gui_v2.utils.splitter_handle import add_splitter_handle
from kymflow.gui_v2.menus import FileTableContextMenu
from kymflow.gui_v2.views.file_table_view import (
    get_file_table_initial_column_visibility,
    get_file_table_toggleable_column_fields,
)
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
    FolderSelectorBindings,
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
    OptionsTabView,
    PlotPoolBindings,  # 20260213ppc
    TaskProgressBindings,
    TaskProgressView,
)
from nicewidgets.utils.clipboard import copy_to_clipboard
from nicewidgets.utils.file_manager import reveal_in_file_manager
from kymflow.core.utils.logging import get_logger
from nicewidgets.utils.lazy_section import LazySection, LazySectionConfig  # 20260213ppc
from nicewidgets.plot_pool_widget.plot_pool_controller import PlotPoolConfig, PlotPoolController  # 20260213ppc
from nicewidgets.plot_pool_widget.plot_state import PlotState, PlotType

logger = get_logger(__name__)

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
        _file_table_view: File table UI component (CustomAgGrid).
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
        self._analysis_update_controller: AnalysisUpdateController | None = None
        self._velocity_event_update_controller: VelocityEventUpdateController | None = None
        self._add_kym_event_controller: AddKymEventController | None = None
        self._delete_kym_event_controller: DeleteKymEventController | None = None
        self._kym_event_cache_sync_controller: KymEventCacheSyncController | None = None
        self._analysis_controller: AnalysisController | None = None
        self._save_controller: SaveController | None = None
        self._task_state_bridge: TaskStateBridgeController | None = None
        self._persistence: FileTablePersistenceController | None = None

        # View objects (created in __init__, UI elements created in build())
        self._folder_view = FolderSelectorView(
            bus,
            context.app_state,
            context.user_config,
            runtime_env=context.runtime_env,
            on_save_selected=bus.emit,
            on_save_all=bus.emit,
        )
        self._file_table_view = FileTableView(
            context,
            on_selected=bus.emit,
            on_metadata_update=bus.emit,
            on_analysis_update=bus.emit,
            selection_mode="single",
        )
        # Right-click context menu is built by FileTableContextMenu and wired into the grid.
        _file_table_menu = FileTableContextMenu(
            on_action=self._on_context_menu,
            get_grid=lambda: self._file_table_view._grid,
            toggleable_columns=get_file_table_toggleable_column_fields(),
            initial_visibility=get_file_table_initial_column_visibility(),
        )
        self._file_table_view.set_context_menu_builder(_file_table_menu.build)
        self._image_line_viewer = ImageLineViewerView(
            on_kym_event_x_range=bus.emit,
            on_set_roi_bounds=bus.emit,
        )
        self._event_view = KymEventView(
            context,
            on_selected=bus.emit,
            on_file_selected=bus.emit,
            on_event_update=bus.emit,
            on_range_state=bus.emit,
            on_add_event=bus.emit,
            on_delete_event=bus.emit,
            on_next_prev_file=bus.emit,
            selection_mode="single",
        )
        self._table_bindings: FileTableBindings | None = None
        self._folder_bindings: FolderSelectorBindings | None = None
        self._image_line_viewer_bindings: ImageLineViewerBindings | None = None
        self._event_bindings: KymEventBindings | None = None
        # 20260213ppc: Plot pool controller refs (set when LazySection render runs)
        self._plot_pool_controller_ref: dict = {"value": None}
        self._plot_pool_velocity_controller_ref: dict = {"value": None}
        self._plot_pool_bindings: PlotPoolBindings | None = None

        # Splitter pane toolbar views
        self._drawer_analysis_toolbar_view = AnalysisToolbarView(
            app_context=context,
            on_analysis_start=bus.emit,
            on_analysis_cancel=bus.emit,
            on_add_roi=bus.emit,
            on_delete_roi=bus.emit,
            on_set_roi_edit_state=bus.emit,
            on_roi_selected=bus.emit,
            on_detect_events=bus.emit,
        )
        self._drawer_task_progress_view = TaskProgressView()
        self._drawer_contrast_view = ContrastView(on_image_display_change=bus.emit)
        self._drawer_line_plot_controls_view = LinePlotControlsView(
            on_filter_change=self._on_drawer_filter_change,
            on_full_zoom=self._on_drawer_full_zoom,
        )
        # Splitter pane metadata views
        def _get_metadata_field_options(field_name: str) -> list[str]:
            """Get unique experimental metadata values for a field from current file list."""
            files = self.context.app_state.files
            if not files:
                return []
            try:
                return files.get_unique_metadata_values(field_name)
            except Exception:
                logger.exception(
                    "Error getting unique experimental metadata values for field '%s'",
                    field_name,
                )
                return []

        self._drawer_metadata_experimental_view = MetadataExperimentalView(
            on_metadata_update=bus.emit,
            get_field_options=_get_metadata_field_options,
        )
        self._drawer_metadata_header_view = MetadataHeaderView(
            on_metadata_update=bus.emit,
            on_edit_physical_units=bus.emit,
        )
        self._drawer_metadata_tab_view = MetadataTabView(
            self._drawer_metadata_experimental_view,
            self._drawer_metadata_header_view,
            context,
        )
        self._drawer_about_tab_view = AboutTabView()
        self._drawer_options_tab_view = OptionsTabView(context.app_config, context)
        # Drawer view (organizes all splitter pane content)
        self._drawer_view = DrawerView(
            analysis_toolbar_view=self._drawer_analysis_toolbar_view,
            contrast_view=self._drawer_contrast_view,
            line_plot_controls_view=self._drawer_line_plot_controls_view,
            metadata_tab_view=self._drawer_metadata_tab_view,
            about_tab_view=self._drawer_about_tab_view,
            options_tab_view=self._drawer_options_tab_view,
        )
        self._drawer_analysis_toolbar_bindings: AnalysisToolbarBindings | None = None
        self._drawer_task_progress_bindings: TaskProgressBindings | None = None
        self._drawer_contrast_bindings: ContrastBindings | None = None
        self._drawer_line_plot_controls_bindings: LinePlotControlsBindings | None = None
        self._drawer_metadata_experimental_bindings: MetadataExperimentalBindings | None = None
        self._drawer_metadata_header_bindings: MetadataHeaderBindings | None = None

        # Per-client state tracking
        self._restored_once: bool = False
        self._setup_complete: bool = False
        self._full_zoom_shortcut_registered: bool = False
        self._full_zoom_shortcut_event: str = "kymflow_full_zoom_enter"
        self._next_prev_file_shortcut_registered: bool = False
        self._next_file_shortcut_event: str = "kymflow_next_file"
        self._prev_file_shortcut_event: str = "kymflow_prev_file"
        self._save_selected_shortcut_registered: bool = False
        self._save_selected_shortcut_event: str = "kymflow_save_selected"

    def _ensure_setup(self) -> None:
        """Ensure controllers and bindings are set up once per client.

        This method is idempotent and will only create controllers/bindings
        once per client session, preventing duplicate event subscriptions.
        """
        if self._setup_complete:
            return

        # Controllers (subscribe to events once per client)
        self._bridge = AppStateBridgeController(self.context.app_state, self.bus)
        self._folder_controller = FolderController(
            self.context.app_state, self.bus, self.context.user_config
        )
        self._file_selection_controller = FileSelectionController(
            self.context.app_state, self.bus, self.context
        )
        self._next_prev_file_controller = NextPrevFileController(
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
        self._analysis_update_controller = AnalysisUpdateController(
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
        self._kym_event_cache_sync_controller = KymEventCacheSyncController(
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
        self._add_roi_controller = AddRoiController(
            self.context.app_state, self.bus
        )
        self._delete_roi_controller = DeleteRoiController(
            self.context.app_state, self.bus
        )
        self._edit_roi_controller = EditRoiController(
            self.context.app_state, self.bus
        )
        self._roi_edit_state_controller = RoiEditStateController(self.bus)
        self._event_analysis_controller = EventAnalysisController(
            self.context.app_state, self.bus
        )

        self._persistence = FileTablePersistenceController(
            self.context.app_state,
            self.bus,
            storage_key="kymflow_selected_file_path_v2",
        )

        # Bindings (subscribe to events once per client)
        self._table_bindings = FileTableBindings(
            self.bus, self._file_table_view, app_state=self.context.app_state
        )
        self._folder_bindings = FolderSelectorBindings(self.bus, self._folder_view)
        self._image_line_viewer_bindings = ImageLineViewerBindings(
            self.bus, self._image_line_viewer
        )
        self._event_bindings = KymEventBindings(self.bus, self._event_view, app_state=self.context.app_state)

        # Splitter pane toolbar bindings
        self._drawer_analysis_toolbar_bindings = AnalysisToolbarBindings(
            self.bus, self._drawer_analysis_toolbar_view
        )
        self._drawer_task_progress_bindings = TaskProgressBindings(
            self.bus, self._drawer_task_progress_view
        )
        self._drawer_contrast_bindings = ContrastBindings(
            self.bus, self._drawer_contrast_view
        )
        self._drawer_line_plot_controls_bindings = LinePlotControlsBindings(
            self.bus, self._drawer_line_plot_controls_view
        )
        self._drawer_metadata_experimental_bindings = MetadataExperimentalBindings(
            self.bus, self._drawer_metadata_experimental_view, parent_tab_view=self._drawer_metadata_tab_view
        )
        self._drawer_metadata_header_bindings = MetadataHeaderBindings(
            self.bus, self._drawer_metadata_header_view
        )
        # 20260213ppc: Plot pool bindings (FileSelection, FileListChanged, RadonReportUpdated, VelocityEventDbUpdated, AnalysisCompleted)
        self._plot_pool_bindings = PlotPoolBindings(
            self.bus,
            self._plot_pool_controller_ref,
            app_state=self.context.app_state,
            refresh_callback=self._refresh_plot_pool_content,
            plot_pool_velocity_controller_ref=self._plot_pool_velocity_controller_ref,
            refresh_velocity_callback=self._refresh_plot_pool_velocity_content,
        )

        self._setup_complete = True

    def _refresh_plot_pool_content(self) -> None:
        """Refresh plot pool with radon data. Unified handler for FileListChanged and RadonReportUpdated.

        20260213ppc: If controller exists (section open), calls update_df. Else rebuilds section.
        """
        if not hasattr(self, "_plot_pool_container") or self._plot_pool_container is None:
            return
        ctrl = self._plot_pool_controller_ref.get("value")
        if ctrl is not None:
            # Section is open: update in place
            app_state = self.context.app_state
            if not hasattr(app_state.files, "get_radon_report_df"):
                return
            try:
                df = app_state.files.get_radon_report_df()
            except Exception as ex:
                logger.warning("20260213ppc get_radon_report_df failed: %s", ex)
                return
            if df is None or df.empty or "_unique_row_id" not in df.columns:
                return
            try:
                ctrl.update_df(df)
            except Exception as ex:
                logger.warning("20260213ppc plot pool update_df failed: %s", ex)
        else:
            # Section is closed or never opened: rebuild
            self._plot_pool_container.clear()
            with self._plot_pool_container:
                self._build_plot_pool_lazy_section()

    def _refresh_plot_pool_velocity_content(self) -> None:
        """Refresh velocity event plot pool. Handler for VelocityEventDbUpdated and FileListChanged.

        If controller exists (section open), calls update_df. Else rebuilds section.
        """
        if not hasattr(self, "_plot_pool_container") or self._plot_pool_container is None:
            return
        app_state = self.context.app_state
        if app_state.files is None or not hasattr(app_state.files, "get_velocity_event_df"):
            return
        ctrl = self._plot_pool_velocity_controller_ref.get("value")
        if ctrl is not None:
            try:
                df = app_state.files.get_velocity_event_df()
            except Exception as ex:
                logger.warning("get_velocity_event_df failed: %s", ex)
                return
            if df is None or df.empty or "_unique_row_id" not in df.columns:
                return
            try:
                ctrl.update_df(df)
            except Exception as ex:
                logger.warning("velocity plot pool update_df failed: %s", ex)
        else:
            self._plot_pool_container.clear()
            with self._plot_pool_container:
                self._build_plot_pool_lazy_section()

    def _build_plot_pool_lazy_section(self):  # 20260213ppc
        """Build PlotPoolControllers in LazySections. Radon and Velocity Events. Starts minimized."""
        app_state = self.context.app_state
        # Wrap in column to ensure radon and velocity stack vertically (not side-by-side)
        with ui.column().classes("w-full flex flex-col gap-2"):
            if app_state.files is None:
                with ui.expansion("Pool Plot (Radon)", value=False).classes("w-full"):
                    ui.label("No data. Load a folder.").classes("text-sm text-gray-500")
                with ui.expansion("Pool Plot (Velocity Events)", value=False).classes("w-full"):
                    ui.label("No data. Load a folder.").classes("text-sm text-gray-500")
                return

            # Radon Pool Plot
            has_radon = False
            if hasattr(app_state.files, "get_radon_report_df"):
                try:
                    df = app_state.files.get_radon_report_df()
                    has_radon = (
                        df is not None
                        and not df.empty
                        and hasattr(df, "columns")
                        and "_unique_row_id" in df.columns
                    )
                except Exception as ex:
                    logger.warning("20260213ppc get_radon_report_df failed: %s", ex)

            if has_radon:

                def render_radon_fn(container):
                    self._plot_pool_controller_ref["value"] = None
                    try:
                        df = app_state.files.get_radon_report_df()
                    except Exception as ex:
                        logger.warning("20260213ppc get_radon_report_df failed: %s", ex)
                        with container:
                            ui.label("No radon data.").classes("text-sm text-gray-500")
                        return
                    if df is None or df.empty or "_unique_row_id" not in df.columns:
                        with container:
                            ui.label("No radon data.").classes("text-sm text-gray-500")
                        return
                    cfg = self._get_plot_pool_config("radon_db")
                    ctrl = PlotPoolController(df, config=cfg)
                    ctrl.build(container=container)
                    self._plot_pool_controller_ref["value"] = ctrl

                LazySection(
                    "Pool Plot (Radon)",
                    render_fn=render_radon_fn,
                    config=LazySectionConfig(render_once=False, clear_on_close=True, show_spinner=True),
                )
            else:
                with ui.expansion("Pool Plot (Radon)", value=False).classes("w-full"):
                    ui.label("No radon data. Load a folder with analyzed kymographs.").classes("text-sm text-gray-500")

            # Velocity Events Pool Plot
            has_velocity = False
            if hasattr(app_state.files, "get_velocity_event_df"):
                try:
                    df_vel = app_state.files.get_velocity_event_df()
                    has_velocity = (
                        df_vel is not None
                        and not df_vel.empty
                        and hasattr(df_vel, "columns")
                        and "_unique_row_id" in df_vel.columns
                    )
                except Exception as ex:
                    logger.warning("get_velocity_event_df failed: %s", ex)

            if has_velocity:

                def render_velocity_fn(container):
                    self._plot_pool_velocity_controller_ref["value"] = None
                    try:
                        df_vel = app_state.files.get_velocity_event_df()
                    except Exception as ex:
                        logger.warning("get_velocity_event_df failed: %s", ex)
                        with container:
                            ui.label("No velocity event data.").classes("text-sm text-gray-500")
                        return
                    if df_vel is None or df_vel.empty or "_unique_row_id" not in df_vel.columns:
                        with container:
                            ui.label("No velocity event data.").classes("text-sm text-gray-500")
                        return
                    cfg = self._get_plot_pool_config("velocity_event_db")
                    ctrl = PlotPoolController(df_vel, config=cfg)
                    ctrl.build(container=container)
                    self._plot_pool_velocity_controller_ref["value"] = ctrl

                LazySection(
                    "Pool Plot (Velocity Events)",
                    render_fn=render_velocity_fn,
                    config=LazySectionConfig(render_once=False, clear_on_close=True, show_spinner=True),
                )
            else:
                with ui.expansion("Pool Plot (Velocity Events)", value=False).classes("w-full"):
                    ui.label("No velocity event data. Load a folder and run event detection.").classes(
                        "text-sm text-gray-500"
                    )

    def _get_plot_pool_config(self, db_type: str) -> PlotPoolConfig:
        """Create PlotPoolConfig based on db_type.
        
        Args:
            db_type: Either "radon_db" or "velocity_event_db"
            
        Returns:
            Configured PlotPoolConfig instance
        """
        if db_type == "radon_db":
            return PlotPoolConfig(
                pre_filter_columns=["roi_id", "accepted"],
                unique_row_id_col="_unique_row_id",
                db_type="radon_db",
                plot_state=PlotState(
                    xcol="treatment",
                    ycol="vel_mean",
                    pre_filter={
                        "roi_id": "1",
                        "accepted": "True",
                    },
                    plot_type=PlotType.SWARM,
                    group_col="treatment",
                    color_grouping="roi_id",
                    use_absolute_value=False,
                    show_legend=False,
                ),
                app_name="kymflow",
                on_table_row_selected=self._on_plot_pool_row_selected,
            )
        elif db_type == "velocity_event_db":
            return PlotPoolConfig(
                pre_filter_columns=["roi_id", "accepted", "event_type"],
                unique_row_id_col="_unique_row_id",
                db_type="velocity_event_db",
                app_name="kymflow",
                plot_state=PlotState(
                    xcol="grandparent_folder",
                    ycol="t_start",
                    pre_filter={
                        "roi_id": "1",
                        "accepted": "True",
                        "event_type": "User Added",
                    },
                    plot_type=PlotType.SWARM,
                    group_col="grandparent_folder",
                    color_grouping="event_type",
                    # use_absolute_value=False,
                    show_legend=False,
                ),
                on_table_row_selected=self._on_plot_pool_velocity_row_selected,
            )
        else:
            raise ValueError(f"Unknown db_type: {db_type}")

    def _on_plot_pool_row_selected(self, row_id: str, row_dict: dict) -> None:
        """Callback when user selects a row in Radon PlotPoolController. Emits FileSelection intent."""
        parts = row_id.split("|", 1)
        path = parts[0] if parts else ""
        roi_id_raw = parts[1] if len(parts) > 1 else None
        if not path:
            return
        roi_id: int | None = None
        if roi_id_raw is not None:
            try:
                roi_id = int(roi_id_raw)
            except (ValueError, TypeError):
                roi_id = None
        app_state = self.context.app_state
        if app_state.files.find_by_path(path) is None:
            return
        self.bus.emit(
            FileSelection(
                path=path,
                file=None,
                roi_id=roi_id,
                origin=SelectionOrigin.EXTERNAL,
                phase="intent",
            )
        )

    def _on_plot_pool_velocity_row_selected(self, row_id: str, row_dict: dict) -> None:
        """Callback when user selects a row in Velocity Events PlotPoolController.

        Parses _unique_row_id (path|roi_id|event_idx) and emits FileSelection with path, roi_id.
        Event-level selection (path, roi, event_id) deferred to Next Steps.
        """
        parts = row_id.split("|", 2)
        path = parts[0] if parts else ""
        roi_id_raw = parts[1] if len(parts) > 1 else None
        if not path:
            return
        roi_id: int | None = None
        if roi_id_raw is not None:
            try:
                roi_id = int(roi_id_raw)
            except (ValueError, TypeError):
                roi_id = None
        app_state = self.context.app_state
        if app_state.files.find_by_path(path) is None:
            return
        self.bus.emit(
            FileSelection(
                path=path,
                file=None,
                roi_id=roi_id,
                origin=SelectionOrigin.EXTERNAL,
                phase="intent",
            )
        )

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

    def _on_next_file_shortcut(self, _event) -> None:
        """Handle Shift+Down next file shortcut when not editing."""
        self.bus.emit(
            NextPrevFileEvent(
                direction="Next File",
                origin=SelectionOrigin.EXTERNAL,
                phase="intent",
            )
        )

    def _on_prev_file_shortcut(self, _event) -> None:
        """Handle Shift+Up previous file shortcut when not editing."""
        self.bus.emit(
            NextPrevFileEvent(
                direction="Prev File",
                origin=SelectionOrigin.EXTERNAL,
                phase="intent",
            )
        )

    def _register_next_prev_file_shortcuts(self) -> None:
        """Register global Shift+Up/Down shortcuts for file navigation (unless editing)."""
        if self._next_prev_file_shortcut_registered:
            return
        self._next_prev_file_shortcut_registered = True
        ui.on(self._next_file_shortcut_event, self._on_next_file_shortcut)
        ui.on(self._prev_file_shortcut_event, self._on_prev_file_shortcut)
        ui.run_javascript(
            """
(function() {
  if (window._kymflow_next_prev_file_listener) return;
  window._kymflow_next_prev_file_listener = true;
  window.addEventListener('keydown', (e) => {
    if (!e.shiftKey) return;
    if (e.key !== 'ArrowUp' && e.key !== 'ArrowDown') return;
    const active = document.activeElement;
    const tag = active ? active.tagName : '';
    const isEditable = !!active && (
      active.isContentEditable ||
      tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' ||
      (active.classList && active.classList.contains('ag-cell-edit-input')) ||
      (active.closest && (active.closest('.ag-cell-inline-editing') || active.closest('.ag-cell-editor')))
    );
    if (isEditable) return;
    if (e.key === 'ArrowDown') {
      emitEvent('kymflow_next_file', {});
    } else if (e.key === 'ArrowUp') {
      emitEvent('kymflow_prev_file', {});
    }
  });
})();
            """
        )

    def _on_save_selected_shortcut(self, _event) -> None:
        """Handle Command+S/Ctrl+S save selected shortcut when not editing."""
        self.bus.emit(
            SaveSelected(
                phase="intent",
            )
        )

    def _on_context_menu(self, action: str) -> None:
        """Handle context menu actions for file table.
        
        Args:
            action: Action identifier ('reveal_in_finder' or 'other')
        """
        if action == 'reveal_in_finder':

            selected_file = self.context.app_state.selected_file
            if selected_file is None:
                logger.warning(f"No file selected for context menu action: {action}")
                return

            # TODO: Implement reveal in Finder functionality
            # Example: subprocess.run(['open', '-R', str(selected_file.path)])
            logger.info(f"Reveal In Finder: {selected_file.path}")
            
            reveal_in_file_manager(selected_file.path)
        elif action == 'copy_file_table':
            table_text = self._file_table_view.get_table_as_text()
            if table_text:
                copy_to_clipboard(table_text)
                logger.info("File table copied to clipboard")
            else:
                logger.warning("No table data to copy")
        elif action == 'other':
            # TODO: Implement other action functionality
            logger.info(f"Other action:")
        else:
            logger.warning(f"Unknown context menu action: '{action}'")

    def _register_save_selected_shortcut(self) -> None:
        """Register global Command+S/Ctrl+S shortcut for save selected (unless editing)."""
        if self._save_selected_shortcut_registered:
            return
        self._save_selected_shortcut_registered = True
        ui.on(self._save_selected_shortcut_event, self._on_save_selected_shortcut)
        ui.run_javascript(
            """
(function() {
  if (window._kymflow_save_selected_listener) return;
  window._kymflow_save_selected_listener = true;
  window.addEventListener('keydown', (e) => {
    // Check for Command (macOS) or Ctrl (Windows/Linux)
    if (!e.metaKey && !e.ctrlKey) return;
    // Check for 's' or 'S' key
    if (e.key !== 's' && e.key !== 'S') return;
    const active = document.activeElement;
    const tag = active ? active.tagName : '';
    const isEditable = !!active && (
      active.isContentEditable ||
      tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' ||
      (active.classList && active.classList.contains('ag-cell-edit-input')) ||
      (active.closest && (active.closest('.ag-cell-inline-editing') || active.closest('.ag-cell-editor')))
    );
    if (isEditable) return;
    // Prevent browser's default save dialog
    e.preventDefault();
    emitEvent('kymflow_save_selected', {});
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
        self._register_next_prev_file_shortcuts()
        self._register_save_selected_shortcut()

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
                with ui.column().classes("w-full h-full min-h-0 p-4 gap-4 flex flex-col"):
                    # Ensure setup is called once per client before building
                    self._ensure_setup()
                    # build() creates fresh UI elements in the new container context
                    self.build()

            def _toggle_drawer_splitter() -> None:
                if splitter.value > (CLOSED + 2):
                    last_open['value'] = splitter.value
                    splitter.value = CLOSED
                else:
                    splitter.value = last_open['value']

            add_splitter_handle(
                splitter,
                on_dblclick=_toggle_drawer_splitter,
                orientation="vertical",
            )

    def build(self) -> None:
        """Build the Home page UI.

        Creates the folder selector and file table UI elements. This method
        is called every time the page is rendered, but controllers/bindings
        are only created once per client (in _ensure_setup()).

        Selection restoration happens after the UI is created, but only once
        per client session to avoid overwriting user selections.
        """
        # Splitter parameters (percentages, horizontal layout). Tweak these as needed.
        file_plot_splitter = {"value": 15.0, "limits": (0, 60)}
        plot_event_splitter = {"value": 50.0, "limits": (30, 90)}
        from kymflow.core.user_config import HOME_EVENTS_PLOT_SPLITTER_RANGE

        events_plot_splitter = {"value": 55.0, "limits": HOME_EVENTS_PLOT_SPLITTER_RANGE}

        user_config = self.context.user_config
        if user_config is not None:
            saved_file_plot, saved_plot_event, saved_events_plot = user_config.get_home_splitter_positions()
            min_fp, max_fp = file_plot_splitter["limits"]
            min_pe, max_pe = plot_event_splitter["limits"]
            min_ep, max_ep = events_plot_splitter["limits"]
            file_plot_splitter["value"] = max(min_fp, min(max_fp, saved_file_plot))
            plot_event_splitter["value"] = max(min_pe, min(max_pe, saved_plot_event))
            events_plot_splitter["value"] = max(min_ep, min(max_ep, saved_events_plot))
        # Remember last open sizes for double-click min/max toggles.
        file_plot_last = {"value": file_plot_splitter["value"]}
        plot_event_last = {"value": plot_event_splitter["value"]}
        events_plot_last = {"value": events_plot_splitter["value"]}

        # File table SECOND (creates grid ui here) - in disclosure triangle
        # with ui.expansion("Files", value=True).classes("w-full"):
        if 1:
            # Splitter between file table (top) and plot/event area (bottom).
            plot_splitter_ref: dict[str, ui.splitter | None] = {"value": None}
            events_plot_splitter_ref: dict[str, ui.splitter | None] = {"value": None}

            def _update_splitter_positions() -> None:
                if user_config is None:
                    return
                file_val = float(file_plot_splitter_ui.value)
                plot_splitter = plot_splitter_ref["value"]
                events_splitter = events_plot_splitter_ref["value"]
                if plot_splitter is None:
                    plot_val = float(plot_event_splitter["value"])
                else:
                    plot_val = float(plot_splitter.value)
                if events_splitter is None:
                    events_val = float(events_plot_splitter["value"])
                else:
                    events_val = float(events_splitter.value)
                user_config.set_home_splitter_positions(file_val, plot_val, events_val)

            with ui.splitter(
                value=file_plot_splitter["value"],
                limits=file_plot_splitter["limits"],
                horizontal=True,
            ).classes("w-full flex-1 min-h-0") as file_plot_splitter_ui:
                def _toggle_file_plot_splitter() -> None:
                    """Double-click: snap file/plot splitter to min/max with memory."""
                    min_val, max_val = file_plot_splitter["limits"]
                    if file_plot_splitter_ui.value > (min_val + 1):
                        file_plot_last["value"] = file_plot_splitter_ui.value
                        file_plot_splitter_ui.value = min_val
                    else:
                        file_plot_splitter_ui.value = file_plot_last["value"] or max_val
                    _update_splitter_positions()
                # TOP: Folder controls + file table
                with file_plot_splitter_ui.before:

                    with ui.column().classes("w-full h-full min-h-0 flex flex-col"):
                        # IMPORTANT: constrain folder controls to *natural height* (do not let it become flex-1)
                        with ui.column().classes("w-full flex-none"):
                            self._folder_view.render(initial_folder=self.context.app_state.folder)

                        # File table gets all remaining height. Context menu is provided by
                        # FileTableContextMenu via the grid's on_build_context_menu (Phase 1).
                        with ui.column().classes("w-full flex-1 min-h-0"):
                            self._file_table_view.render()
                            self._file_table_view.set_files(list(self.context.app_state.files))
                
                # BOTTOM: Image/line viewer + event table in a nested splitter
                # abb turned off expansion
                # with ui.expansion("Image & Line Viewer", value=True).classes("w-full"):
                with file_plot_splitter_ui.after:
                    with ui.splitter(
                        value=plot_event_splitter["value"],
                        limits=plot_event_splitter["limits"],
                        horizontal=True,
                    ).classes("w-full flex-1 min-h-0") as plot_splitter:
                        plot_splitter_ref["value"] = plot_splitter
                        def _toggle_plot_event_splitter() -> None:
                            """Double-click: snap plot/event splitter to min/max with memory."""
                            min_val, max_val = plot_event_splitter["limits"]
                            if plot_splitter.value > (min_val + 1):
                                plot_event_last["value"] = plot_splitter.value
                                plot_splitter.value = min_val
                            else:
                                plot_splitter.value = plot_event_last["value"] or max_val
                            _update_splitter_positions()
                        # TOP: Image/line viewer
                        with plot_splitter.before:
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

                        # BOTTOM: Event table + Plot pool in nested splitter (20260213ppc layout fix)
                        with plot_splitter.after:
                            # just some v-height to seperate splitters
                            # ui.element("div").style("height:1px; min-height:1px; line-height:1px; padding:0; margin:0;")
                            # ui.element("div").style("height: 1px; padding: 0; margin: 0")
                            with ui.splitter(
                                value=events_plot_splitter["value"],
                                limits=events_plot_splitter["limits"],
                                horizontal=True,
                            ).classes("w-full flex-1 min-h-0 mt-[6px]") as events_plot_splitter_ui:
                                events_plot_splitter_ref["value"] = events_plot_splitter_ui

                                def _toggle_events_plot_splitter() -> None:
                                    min_val, max_val = events_plot_splitter["limits"]
                                    if events_plot_splitter_ui.value > (min_val + 1):
                                        events_plot_last["value"] = events_plot_splitter_ui.value
                                        events_plot_splitter_ui.value = min_val
                                    else:
                                        events_plot_splitter_ui.value = events_plot_last["value"] or 55.0
                                    _update_splitter_positions()

                                # Events pane (left)
                                with events_plot_splitter_ui.before:
                                    with ui.column().classes("w-full h-full min-h-0 flex flex-col"):
                                        self._event_view.render()
                                        current_file = self.context.app_state.selected_file
                                        if current_file is not None:
                                            blinded = self.context.app_config.get_blinded() if self.context.app_config else False
                                            report = current_file.get_kym_analysis().get_velocity_report(blinded=blinded)
                                            self._event_view.set_events(report)
                                        current_roi = self.context.app_state.selected_roi_id
                                        if current_roi is not None:
                                            self._event_view.set_selected_roi(current_roi)
                                        # Wire up event filter callback to refresh plot
                                        self._event_view._on_event_filter_changed = lambda filter: self._image_line_viewer.set_event_filter(filter)
                                        # Sync initial filter state from event view to image line viewer
                                        self._image_line_viewer.set_event_filter(self._event_view._event_filter)
                                # Plot pool pane (right) - 20260213ppc
                                with events_plot_splitter_ui.after:
                                    self._plot_pool_container = ui.column().classes(
                                        "w-full h-full min-h-0 flex flex-col overflow-auto"
                                    )
                                    self._refresh_plot_pool_content()

                                add_splitter_handle(
                                    events_plot_splitter_ui,
                                    on_dblclick=_toggle_events_plot_splitter,
                                    offset="center",
                                    # offset="before",
                                )
                                events_plot_splitter_ui.on(
                                    "update:model-value",
                                    _update_splitter_positions,
                                    throttle=0.2,
                                )

                        add_splitter_handle(plot_splitter, on_dblclick=_toggle_plot_event_splitter)
                        plot_splitter.on(
                            "update:model-value",
                            _update_splitter_positions,
                            throttle=0.2,
                        )

                add_splitter_handle(file_plot_splitter_ui, on_dblclick=_toggle_file_plot_splitter)
                file_plot_splitter_ui.on(
                    "update:model-value",
                    _update_splitter_positions,
                    throttle=0.2,
                )

        # Restore selection once per client (after UI is created)
        if not self._restored_once:
            if self._persistence is not None:
                restored = self._persistence.restore_selection()
                if restored:
                    logger.error(f'=== CALLING self._file_table_view.set_selected_paths')
                    self._file_table_view.set_selected_paths(
                        restored, origin=SelectionOrigin.RESTORE
                    )
            self._restored_once = True