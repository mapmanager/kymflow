"""Velocity event table view component using CustomAgGrid_v2."""

from __future__ import annotations

# from pathlib import Path  # Commented out - only used in _update_file_path_label which is also commented out
from typing import Callable, Iterable, List, Optional

from nicegui import ui
from nicewidgets.custom_ag_grid.config import ColumnConfig, GridConfig, SelectionMode
from nicewidgets.custom_ag_grid.custom_ag_grid_v2 import CustomAgGrid_v2

from kymflow.core.analysis.velocity_events.velocity_events import UserType, VelocityEvent
from kymflow.core.utils.logging import get_logger
from kymflow.gui_v2.events import (
    AddKymEvent,
    DeleteKymEvent,
    EventSelection,
    EventSelectionOptions,
    FileSelection,
    NextPrevFileEvent,
    SelectionOrigin,
    SetKymEventRangeState,
    SetKymEventXRange,
    VelocityEventUpdate,
)

Rows = List[dict[str, object]]
OnSelected = Callable[[EventSelection], None]
OnFileSelected = Callable[[FileSelection], None]
OnEventUpdate = Callable[[VelocityEventUpdate], None]
OnRangeState = Callable[[SetKymEventRangeState], None]
OnAddEvent = Callable[[AddKymEvent], None]
OnDeleteEvent = Callable[[DeleteKymEvent], None]
OnNextPrevFile = Callable[[NextPrevFileEvent], None]

logger = get_logger(__name__)


def _col(
    field: str,
    header: Optional[str] = None,
    *,
    width: Optional[int] = None,
    min_width: Optional[int] = None,
    hide: bool = False,
    cell_class: Optional[str] = None,
    editable: bool = False,
    editor: str = "auto",
    choices: Optional[Iterable[object] | str] = None,
    resizable: bool = True,
) -> ColumnConfig:
    extra: dict[str, object] = {}
    if width is not None:
        extra["width"] = width
    if min_width is not None:
        extra["minWidth"] = min_width
    # Only lock width (set maxWidth) when column is not resizable
    if width is not None and not resizable:
        # Use width for both min and max to lock it, unless min_width was explicitly provided
        if min_width is None:
            extra["minWidth"] = width
        extra["maxWidth"] = width
    if hide:
        extra["hide"] = True
    if cell_class is not None:
        extra["cellClass"] = cell_class
    return ColumnConfig(
        field=field,
        header=header,
        editable=editable,
        editor=editor,  # type: ignore[arg-type]
        choices=choices,  # type: ignore[arg-type]
        resizable=resizable,
        extra_grid_options=extra,
    )


def _default_columns() -> list[ColumnConfig]:
    return [
        # we only allow one roi
        # _col("roi_id", "ROI", width=80, cell_class="ag-cell-right"),
        _col("file_name", "File", width=180, min_width=180),
        _col("grandparent_folder", "GP", width=80, min_width=80),
        _col(
            "user_type",
            "User Type",
            width=160,
            editable=True,
            editor="select",
            choices=[v.value for v in UserType],
        ),
        _col("event_type", "Type", width=160),
        _col("t_start", "Start (s)", width=110, cell_class="ag-cell-right"),
        # _col("t_end", "Stop (s)", width=110, cell_class="ag-cell-right"),
        _col("duration_sec", "Dur (s)", width=110, cell_class="ag-cell-right"),
        _col("strength", "Strength", width=110, cell_class="ag-cell-right"),
        _col("event_id", "event_id", hide=True),
        _col("path", "path", hide=True),
    ]


class KymEventView:
    """Velocity event table view using CustomAgGrid_v2."""

    def __init__(
        self,
        *,
        on_selected: OnSelected,
        on_file_selected: OnFileSelected | None = None,
        on_event_update: OnEventUpdate | None = None,
        on_range_state: OnRangeState | None = None,
        on_add_event: OnAddEvent | None = None,
        on_delete_event: OnDeleteEvent | None = None,
        on_next_prev_file: OnNextPrevFile | None = None,
        selection_mode: SelectionMode = "single",
    ) -> None:
        self._on_selected = on_selected
        self._on_file_selected = on_file_selected
        self._on_event_update = on_event_update
        self._on_range_state = on_range_state
        self._on_add_event = on_add_event
        self._on_delete_event = on_delete_event
        self._on_next_prev_file = on_next_prev_file
        self._selection_mode = selection_mode
        self._grid: CustomAgGrid_v2 | None = None
        self._grid_container: ui.element | None = None  # pyinstaller event table
        self._suppress_emit: bool = False
        self._pending_rows: Rows = []
        self._all_rows: Rows = []
        self._roi_filter: int | None = None
        self._zoom_enabled: bool = True
        self._zoom_pad_sec: float = 1.0
        self._setting_kym_event_range_state: bool = False
        self._adding_new_event: bool = False  # Track if we're adding a new event vs updating
        self._set_range_button: ui.button | None = None
        self._cancel_range_button: ui.button | None = None
        self._add_event_button: ui.button | None = None
        self._delete_event_button: ui.button | None = None
        self._prev_file_button: ui.button | None = None
        self._next_file_button: ui.button | None = None
        self._range_notification: ui.notification | None = None
        self._dismissing_programmatically: bool = False  # Flag to track programmatic dismiss
        self._selected_event_id: str | None = None
        self._selected_event_roi_id: int | None = None
        self._selected_event_path: str | None = None
        self._current_file_path: str | None = None  # Track current file path from row data
        # self._file_path_label: ui.label | None = None  # Label showing current file name (commented out - aggrid has 'file' column)
        self._show_all_files: bool = False  # Track "All Files" mode state
        self._all_files_checkbox: ui.checkbox | None = None  # Checkbox UI element
        self._on_all_files_mode_changed: Callable[[], None] | None = None  # Callback for bindings
        self._get_current_selected_file_path: Callable[[], str | None] | None = None  # Callback to get current selected file path
        self._pending_event_selection_after_file_change: str | None = None  # Track event_id to preserve when file change clears selection
        self._file_selection_originated_from_view: str | None = None  # Track file path when we emit FileSelection to prevent unnecessary refreshes
        # Event type filter state: dict mapping event_type (str) to bool (True = show, False = hide)
        self._event_filter: dict[str, bool] = {
            "baseline_drop": True,
            "baseline_rise": True,
            "nan_gap": True,
            "zero_gap": True,
            "User Added": True,
        }
        self._on_event_filter_changed: Callable[[dict[str, bool]], None] | None = None  # Callback for plot refresh
        self._event_filter_menu: ui.menu | None = None  # Menu for event type filters
        self._event_filter_menu_button: ui.button | None = None  # Button to open event filter menu
        self._event_filter_menu: ui.menu | None = None  # Menu for event type filters
        self._event_filter_menu_button: ui.button | None = None  # Button to open event filter menu

    def render(self) -> None:
        """Create the grid UI inside the current container."""
        # Cleanup: If we're in range-setting state when view is recreated (e.g., navigation away/back),
        # cancel the state to prevent stale state from persisting.
        if self._setting_kym_event_range_state or self._adding_new_event:
            # Cancel the state without showing notification (it may have been auto-dismissed)
            self._setting_kym_event_range_state = False
            self._adding_new_event = False
            self._emit_range_state(False)
            # Clear notification reference if it exists (it may have been auto-dismissed by NiceGUI)
            if self._range_notification is not None:
                self._range_notification = None
        
        self._grid = None
        self._grid_container = None  # pyinstaller event table
        with ui.row().classes("w-full h-full min-h-0 min-w-0 items-stretch gap-1"):
            with ui.column().classes("w-50 shrink-0"):
                
                
                with ui.row().classes("w-full gap-1"):
                    ui.label("Kym Event").classes("text-sm text-gray-500")
                    self._prev_file_button = ui.button(
                        "",
                        on_click=self._on_prev_file_clicked,
                        icon="keyboard_double_arrow_up",
                    ).props("dense").classes('text-sm')
                    self._prev_file_button.tooltip("Previous File")
                    self._next_file_button = ui.button(
                        "",
                        on_click=self._on_next_file_clicked,
                        icon="keyboard_double_arrow_down",
                    ).props("dense").classes('text-sm')
                    self._next_file_button.tooltip("Next File")

                # self._file_path_label = ui.label("No file selected").classes("text-xs text-gray-400")  # Commented out - aggrid has 'file' column

                with ui.row().classes("w-full gap-1"):
                    self._all_files_checkbox = ui.checkbox("All Files", value=self._show_all_files).on_value_change(
                        lambda e: self.set_all_files_mode(bool(e.value))
                    ).props("dense").classes('text-sm')

                # Event type filter dropdown menu
                with ui.row().classes("w-full gap-1"):
                    with ui.element("div").classes("inline-block"):
                        # Create button first
                        self._event_filter_menu_button = ui.button(
                            "Filter Events",
                            on_click=lambda: self._event_filter_menu.open() if self._event_filter_menu else None,
                        ).props("dense").classes('text-sm')
                        
                        # Then create menu (will be positioned relative to button)
                        self._build_event_filter_menu()

                with ui.row().classes("w-full gap-1"):
                    ui.checkbox("Zoom (+/- s)", value=self._zoom_enabled).on_value_change(
                        lambda e: self._set_zoom_enabled(bool(e.value))
                    ).props("dense").classes('text-sm')
                    ui.number("", value=self._zoom_pad_sec, step=0.1).on_value_change(
                        lambda e: self._set_zoom_pad_sec(float(e.value))
                    ).props("dense").classes("w-10 text-sm")

                with ui.row().classes("w-full gap-1"):
                    self._set_range_button = ui.button(
                        "Set Start/Stop",
                        on_click=self._on_set_event_range_clicked,
                    ).props("dense").classes('text-sm')
                    self._cancel_range_button = ui.button(
                        "Cancel",
                        on_click=self._on_cancel_event_range_clicked,
                    ).props("dense").classes('text-sm')
                with ui.row().classes("w-full gap-1"):
                    self._add_event_button = ui.button(
                        "Add Event",
                        on_click=self._on_add_event_clicked,
                    ).props("dense").classes('text-sm')
                    self._delete_event_button = ui.button(
                        "Delete Event",
                        on_click=self._on_delete_event_clicked,
                    ).props("dense").classes('text-sm')
                self._update_range_button_state()
                self._update_add_delete_button_state()

            with ui.column().classes("flex-1 min-h-0 min-w-0 flex flex-col"):
                self._grid_container = ui.column().classes(
                    "w-full h-full min-h-0 flex flex-col overflow-hidden"
                )  # pyinstaller event table
                self._create_grid(self._pending_rows)

    def _create_grid(self, rows: Rows) -> None:
        """Create a fresh grid instance inside the current container."""
        # logger.debug(f'pyinstaller num rows={len(rows)}')
        if self._grid_container is None:
            return
        grid_cfg = GridConfig(
            selection_mode=self._selection_mode,  # type: ignore[arg-type]
            # height="16rem",
            row_id_field="event_id",
            show_row_index=True,
            # row_index_width=60,  # Wider to fit index >= 100
            zebra_rows=False,
            hover_highlight=False,
        )
        # logger.debug(f'pyinstaller instantiating CustomAgGrid_v2(rows={len(rows)})')
        if 1:
            self._grid = CustomAgGrid_v2(
                data=rows,
                columns=_default_columns(),
                grid_config=grid_cfg,
                parent=self._grid_container,
                runtimeWidgetName="KymEventTableView",
            )
            self._grid.on_row_selected(self._on_row_selected)
            self._grid.on_cell_edited(self._on_cell_edited)

    def _set_zoom_enabled(self, value: bool) -> None:
        self._zoom_enabled = value

    def _set_zoom_pad_sec(self, value: float) -> None:
        self._zoom_pad_sec = value

    def _build_event_filter_menu(self) -> None:
        """Build the event type filter menu with checkboxes."""
        # Build menu with checkboxes inside (not as menu items)
        with ui.menu() as menu:
            self._event_filter_menu = menu
            # Prevent auto-close so menu stays open when toggling checkboxes
            menu.props("auto-close=false")
            
            # Wrap checkboxes in a column for vertical layout
            with ui.column().classes("gap-1 p-2"):
                self._baseline_drop_checkbox = ui.checkbox(
                    "Baseline Drop",
                    value=self._event_filter["baseline_drop"]
                ).on_value_change(
                    lambda e: self._on_event_type_filter_changed("baseline_drop", bool(e.value))
                ).props("dense").classes('text-sm')
                
                self._baseline_rise_checkbox = ui.checkbox(
                    "Baseline Rise",
                    value=self._event_filter["baseline_rise"]
                ).on_value_change(
                    lambda e: self._on_event_type_filter_changed("baseline_rise", bool(e.value))
                ).props("dense").classes('text-sm')
                
                self._nan_gap_checkbox = ui.checkbox(
                    "NaN Gap",
                    value=self._event_filter["nan_gap"]
                ).on_value_change(
                    lambda e: self._on_event_type_filter_changed("nan_gap", bool(e.value))
                ).props("dense").classes('text-sm')
                
                self._zero_gap_checkbox = ui.checkbox(
                    "Zero Gap",
                    value=self._event_filter["zero_gap"]
                ).on_value_change(
                    lambda e: self._on_event_type_filter_changed("zero_gap", bool(e.value))
                ).props("dense").classes('text-sm')
                
                self._user_added_checkbox = ui.checkbox(
                    "User Added",
                    value=self._event_filter["User Added"]
                ).on_value_change(
                    lambda e: self._on_event_type_filter_changed("User Added", bool(e.value))
                ).props("dense").classes('text-sm')

    def _on_event_type_filter_changed(self, event_type: str, enabled: bool) -> None:
        """Handle event type filter checkbox change."""
        self._event_filter[event_type] = enabled
        # Refresh ag grid with new filter
        self._apply_filter()
        # Notify plot to refresh if callback is set
        if self._on_event_filter_changed is not None:
            self._on_event_filter_changed(self._event_filter)

    def set_events(
        self, rows: Iterable[dict[str, object]], *, select_event_id: str | None = None, skip_if_originated: bool = False
    ) -> None:
        """Update table contents from velocity report rows.
        
        Args:
            rows: Velocity report rows to display.
            select_event_id: Optional event_id to select after updating the grid.
            skip_if_originated: If True and we originated a FileSelection, skip set_data to preserve column state.
        """
        rows_list = list(rows) if not isinstance(rows, list) else rows
        
        self._all_rows = rows_list
        # Extract current file path from first row if available
        # If rows are empty, keep existing _current_file_path (don't reset to None)
        # This allows the label to show the correct file even when there are no events
        if self._all_rows:
            first_path = self._all_rows[0].get("path")
            if first_path:
                self._current_file_path = str(first_path)
            # If first row has no path, don't update _current_file_path (keep existing)
        # If rows are empty, don't update _current_file_path (keep existing)
        # self._update_file_path_label()  # Commented out - aggrid has 'file' column
        self._apply_filter(skip_if_originated=skip_if_originated)
        
        # Select event after grid update if requested
        if select_event_id is not None:
            self.set_selected_event_ids([select_event_id], origin=SelectionOrigin.EXTERNAL)
        else:
            # Update button state even if no event is selected (file path may have changed)
            self._update_add_delete_button_state()

    def set_selected_event_ids(self, event_ids: list[str], *, origin: SelectionOrigin) -> None:
        """Programmatically select rows by event_id."""
        if self._grid is None:
            return
        self._suppress_emit = True
        try:
            if hasattr(self._grid, "set_selected_row_ids"):
                self._grid.set_selected_row_ids(event_ids, origin=origin.value)
        finally:
            self._suppress_emit = False
        if len(event_ids) == 1:
            self._selected_event_id = event_ids[0]
            # Find row data to emit EventSelection for plot highlighting
            # Search _all_rows first (source of truth), then _pending_rows as fallback
            row_data = None
            for row in self._all_rows:
                if row.get("event_id") == event_ids[0]:
                    row_data = row
                    break
            if row_data is None:
                # Not in all rows, search filtered rows as fallback
                for row in self._pending_rows:
                    if row.get("event_id") == event_ids[0]:
                        row_data = row
                        break
            if row_data is not None:
                roi_id = row_data.get("roi_id")
                path = row_data.get("path")
                event = VelocityEvent.from_dict(row_data)
                self._selected_event_roi_id = int(roi_id) if roi_id is not None else None
                self._selected_event_path = str(path) if path else None
                # Only emit EventSelection for user-initiated selections (EVENT_TABLE origin)
                # EXTERNAL origin selections are programmatic and should NOT emit EventSelection
                # to avoid infinite recursion: EXTERNAL → EventSelection → bindings → EXTERNAL
                if origin == SelectionOrigin.EVENT_TABLE:
                    self._on_selected(
                        EventSelection(
                            event_id=str(event_ids[0]),
                            roi_id=int(roi_id) if roi_id is not None else None,
                            path=str(path) if path else None,
                            event=event,
                            options=EventSelectionOptions(
                                zoom=self._zoom_enabled,
                                zoom_pad_sec=self._zoom_pad_sec,
                            ),
                            origin=origin,
                            phase="intent",
                        )
                    )
        else:
            self._selected_event_id = None
            self._selected_event_roi_id = None
            self._selected_event_path = None
        self._update_range_button_state()
        self._update_add_delete_button_state()

    def set_selected_roi(self, roi_id: int | None) -> None:
        """Filter rows by ROI ID (None clears filter)."""
        logger.debug(f'== roi_id:{roi_id}')
        self._roi_filter = roi_id
        # In all-files mode, if we originated a FileSelection, skip refresh to preserve column state
        skip_refresh = self._show_all_files and self._file_selection_originated_from_view is not None
        logger.warning(f'skip_refresh:{skip_refresh}')
        self._apply_filter(skip_if_originated=skip_refresh)

    def _apply_filter(self, *, skip_if_originated: bool = False) -> None:
        """Apply ROI filter and event type filter, then update grid data.
        
        Args:
            skip_if_originated: If True and we originated a FileSelection, skip set_data to preserve column state.
        """
        if skip_if_originated and self._file_selection_originated_from_view is not None:
            # We originated a FileSelection, don't refresh grid to preserve column sort/width
            return
        # First filter by ROI
        if self._roi_filter is None:
            rows = list(self._all_rows)
        else:
            rows = [
                row for row in self._all_rows if row.get("roi_id") == self._roi_filter
            ]
        # Then filter by event_type
        rows = [
            row for row in rows
            if self._event_filter.get(row.get("event_type"), True) is True
        ]
        self._pending_rows = rows
        if self._grid is not None:
            # logger.debug('  === calling grid self._grid.set_data(rows)')
            self._grid.set_data(rows)

    def _on_row_selected(self, row_index: int, row_data: dict[str, object]) -> None:
        """Handle user selecting a row."""
        if self._suppress_emit:
            return
        event_id = row_data.get("event_id")
        if event_id is None:
            return
        roi_id = row_data.get("roi_id")
        path = row_data.get("path")
        event = VelocityEvent.from_dict(row_data)
        self._selected_event_id = str(event_id)
        self._selected_event_roi_id = int(roi_id) if roi_id is not None else None
        self._selected_event_path = str(path) if path else None
        self._update_range_button_state()
        self._update_add_delete_button_state()
        
        # In all-files mode, check if we need to switch the selected file first
        if self._show_all_files and path and self._on_file_selected is not None:
            # Get current selected file path
            current_path = None
            if self._get_current_selected_file_path is not None:
                current_path = self._get_current_selected_file_path()
            
            # If event belongs to a different file, emit FileSelection first
            event_path_str = str(path) if path else None
            if event_path_str and event_path_str != current_path:
                # Set flag to preserve this event selection when file change clears it
                self._pending_event_selection_after_file_change = str(event_id)
                # Track that we originated this FileSelection to prevent unnecessary refreshes
                self._file_selection_originated_from_view = event_path_str
                self._on_file_selected(
                    FileSelection(
                        path=event_path_str,
                        file=None,
                        origin=SelectionOrigin.EXTERNAL,
                        phase="intent",
                    )
                )
        
        # Always emit EventSelection
        self._on_selected(
            EventSelection(
                event_id=str(event_id),
                roi_id=int(roi_id) if roi_id is not None else None,
                path=str(path) if path else None,
                event=event,
                options=EventSelectionOptions(
                    zoom=self._zoom_enabled,
                    zoom_pad_sec=self._zoom_pad_sec,
                ),
                origin=SelectionOrigin.EVENT_TABLE,
                phase="intent",
            )
        )

    def _on_cell_edited(
        self,
        row_index: int,
        field: str,
        old_value: object,
        new_value: object,
        row_data: dict[str, object],
    ) -> None:
        """Handle user editing a cell."""
        if self._on_event_update is None:
            return
        if field != "user_type":
            return
        event_id = row_data.get("event_id")
        if not event_id:
            return
        path = row_data.get("path")
        self._on_event_update(
            VelocityEventUpdate(
                event_id=str(event_id),
                path=str(path) if path else None,
                field=field,
                value=new_value,
                origin=SelectionOrigin.EVENT_TABLE,
                phase="intent",
            )
        )

    def handle_set_kym_event_x_range(self, e: SetKymEventXRange) -> None:
        """Handle proposed x-range selection for a velocity event."""
        # logger.debug("handle_set_kym_event_x_range event_id=%s adding_new_event=%s", e.event_id, self._adding_new_event)
        self._setting_kym_event_range_state = False
        self._emit_range_state(False)
        self._update_range_button_state()
        self._set_range_notification_visible(False)

        # If adding a new event, emit AddKymEvent instead of VelocityEventUpdate
        if self._adding_new_event:
            self._adding_new_event = False
            if self._on_add_event is None:
                logger.warning("handle_set_kym_event_x_range: on_add_event callback not set")
                return
            if self._roi_filter is None:
                logger.warning("handle_set_kym_event_x_range: roi_filter is None, cannot add event")
                return
            self._on_add_event(
                AddKymEvent(
                    event_id=None,  # Will be set by controller after creation
                    roi_id=self._roi_filter,
                    path=self._current_file_path,
                    t_start=e.x0,
                    t_end=e.x1,
                    origin=SelectionOrigin.EVENT_TABLE,
                    phase="intent",
                )
            )
            self._update_add_delete_button_state()
            return

        # Otherwise, update existing event (original behavior)
        if self._selected_event_id is None:
            # logger.debug("no selected event; ignoring range proposal")
            return
        if e.event_id is not None and e.event_id != self._selected_event_id:
            # logger.debug("range proposal event_id mismatch (current=%s)", self._selected_event_id)
            return
        if self._selected_event_path is not None and e.path is not None:
            if self._selected_event_path != e.path:
                # logger.debug("range proposal path mismatch (current=%s)", self._selected_event_path)
                return
        if self._on_event_update is None:
            return
        self._on_event_update(
            VelocityEventUpdate(
                event_id=self._selected_event_id,
                path=self._selected_event_path,
                updates={"t_start": e.x0, "t_end": e.x1},
                origin=SelectionOrigin.EVENT_TABLE,
                phase="intent",
            )
        )

    def _on_set_event_range_clicked(self) -> None:
        if self._selected_event_id is None:
            return
        # logger.debug("set_event_range_clicked -> toggle state")
        self._setting_kym_event_range_state = not self._setting_kym_event_range_state
        self._adding_new_event = False  # Ensure we're not in add mode
        self._emit_range_state(self._setting_kym_event_range_state)
        self._update_range_button_state()
        self._update_add_delete_button_state()
        if self._setting_kym_event_range_state:
            self._set_range_notification_visible(True)
        else:
            self._set_range_notification_visible(False)

    def _on_notification_dismissed(self, e) -> None:
        """Handle notification dismiss event (either programmatic or user-initiated)."""
        # logger.debug("_on_notification_dismissed called, _dismissing_programmatically=%s", self._dismissing_programmatically)
        if self._dismissing_programmatically:
            # Programmatic dismiss - just clear the flag and reference
            self._dismissing_programmatically = False
            self._range_notification = None
            return
        # User clicked "Cancel" button on notification - clear reference and call cancel handler
        # logger.debug("User clicked Cancel button on notification")
        self._range_notification = None  # Clear reference since notification is already dismissed
        self._on_cancel_event_range_clicked()

    def _on_cancel_event_range_clicked(self) -> None:
        if not self._setting_kym_event_range_state and not self._adding_new_event:
            return
        # logger.debug("cancel_event_range_clicked -> disable state")
        self._setting_kym_event_range_state = False
        self._adding_new_event = False
        self._emit_range_state(False)
        self._update_range_button_state()
        self._update_add_delete_button_state()
        # Only dismiss notification if it still exists (not already dismissed by user)
        if self._range_notification is not None:
            self._set_range_notification_visible(False)

    def _emit_range_state(self, enabled: bool) -> None:
        if self._on_range_state is None:
            return
        # logger.debug("emit SetKymEventRangeState enabled=%s adding_new_event=%s", enabled, self._adding_new_event)
        # For new events, event_id is None
        event_id = None if self._adding_new_event else self._selected_event_id
        roi_id = self._roi_filter if self._adding_new_event else self._selected_event_roi_id
        path = self._current_file_path if self._adding_new_event else self._selected_event_path
        self._on_range_state(
            SetKymEventRangeState(
                enabled=enabled,
                event_id=event_id,
                roi_id=roi_id,
                path=path,
                origin=SelectionOrigin.EVENT_TABLE,
                phase="intent",
            )
        )

    def _update_range_button_state(self) -> None:
        if self._set_range_button is None or self._cancel_range_button is None:
            return
        if self._selected_event_id is None:
            self._set_range_button.disable()
            # self._set_range_button.text = "Set Event Start/Stop"
            # self._set_range_button.props(remove="color")
            self._cancel_range_button.disable()
            # self._cancel_range_button.props(remove="color")
            self._set_range_notification_visible(False)
            return
        self._set_range_button.enable()
        if self._setting_kym_event_range_state:
            # self._set_range_button.text = "Set Event Start/Stop"
            # self._set_range_button.props("color=orange")
            self._cancel_range_button.enable()
            # self._cancel_range_button.props("color=orange")
        else:
            # self._set_range_button.text = "Set Event Start/Stop"
            # self._set_range_button.props(remove="color")
            self._cancel_range_button.disable()
            #  self._cancel_range_button.props(remove="color")
            self._set_range_notification_visible(False)

    def _set_range_notification_visible(self, visible: bool) -> None:
        if visible:
            if self._range_notification is not None:
                self._dismissing_programmatically = True
                self._range_notification.dismiss()
            message = (
                "Draw a rectangle on the plot to add new event start/stop."
                if self._adding_new_event
                else "Draw a rectangle on the plot to set event start/stop."
            )
            self._range_notification = ui.notification(
                message,
                color="warning",
                timeout=None,
                close_button="Cancel",
                on_dismiss=self._on_notification_dismissed,
            )
        else:
            if self._range_notification is None:
                return
            self._dismissing_programmatically = True
            self._range_notification.dismiss()
            self._range_notification = None

    def _on_add_event_clicked(self) -> None:
        """Handle Add Event button click."""
        if self._roi_filter is None:
            logger.warning("Add Event: roi_filter is None, cannot add event")
            return
        if self._current_file_path is None:
            logger.warning("Add Event: current_file_path is None, cannot add event")
            return
        # logger.debug("add_event_clicked -> enable range state for new event")
        self._adding_new_event = True
        self._setting_kym_event_range_state = True
        self._emit_range_state(True)
        self._update_range_button_state()
        self._update_add_delete_button_state()
        self._set_range_notification_visible(True)

    def _on_delete_event_clicked(self) -> None:
        """Handle Delete Event button click."""
        if self._selected_event_id is None:
            return
        if self._on_delete_event is None:
            logger.warning("Delete Event: on_delete_event callback not set")
            return

        # Show confirmation dialog
        with ui.dialog() as dialog, ui.card():
            ui.label("Delete Event").classes("text-lg font-semibold")

            # abb TODO we do not have easy access to event
            # get selected event
            # selected_event = self._selected_event
            # name_str = f"event_type:{selected_event.event_type} user_type:{selected_event.user_type} t_start:{selected_event.t_start} t_end:{selected_event.t_end}"

            name_str = ''
            ui.label(f"Are you sure you want to delete event {name_str}?")

            with ui.row():
                ui.button("Cancel", on_click=dialog.close)
                ui.button("Delete", on_click=lambda: self._confirm_delete(dialog))

        dialog.open()

    def _confirm_delete(self, dialog: ui.dialog) -> None:
        """Confirm deletion and emit DeleteKymEvent."""
        dialog.close()
        if self._on_delete_event is None:
            return
        # logger.debug("confirm_delete event_id=%s", self._selected_event_id)
        self._on_delete_event(
            DeleteKymEvent(
                event_id=self._selected_event_id,
                roi_id=self._selected_event_roi_id,
                path=self._selected_event_path,
                origin=SelectionOrigin.EVENT_TABLE,
                phase="intent",
            )
        )

    def _on_prev_file_clicked(self) -> None:
        """Handle Previous File button click."""
        if self._on_next_prev_file is None:
            logger.warning("Previous File: on_next_prev_file callback not set")
            return
        self._on_next_prev_file(
            NextPrevFileEvent(
                direction="Prev File",
                origin=SelectionOrigin.EXTERNAL,
                phase="intent",
            )
        )

    def _on_next_file_clicked(self) -> None:
        """Handle Next File button click."""
        if self._on_next_prev_file is None:
            logger.warning("Next File: on_next_prev_file callback not set")
            return
        self._on_next_prev_file(
            NextPrevFileEvent(
                direction="Next File",
                origin=SelectionOrigin.EXTERNAL,
                phase="intent",
            )
        )

    # def _update_file_path_label(self) -> None:
    #     """Update the file path label with current file name (stem) or placeholder."""
    #     # Commented out - aggrid has 'file' column, no need for separate label
    #     if self._file_path_label is None:
    #         return
    #     if self._current_file_path:
    #         try:
    #             file_name = Path(self._current_file_path).stem
    #             self._file_path_label.text = file_name
    #         except (ValueError, TypeError):
    #             self._file_path_label.text = "No file selected"
    #     else:
    #         self._file_path_label.text = "No file selected"

    def _update_add_delete_button_state(self) -> None:
        """Update Add/Delete button enable/disable state."""
        if self._add_event_button is None or self._delete_event_button is None:
            return

        # Add button: enabled when roi_filter and file path are available, and not in range-selection state
        # Disable in all-files mode since we can't add events without a specific file context
        add_enabled = (
            not self._show_all_files
            and self._roi_filter is not None
            and self._current_file_path is not None
            and not self._setting_kym_event_range_state
            and not self._adding_new_event
        )
        if add_enabled:
            self._add_event_button.enable()
        else:
            self._add_event_button.disable()

        # Delete button: enabled only when a row is selected
        delete_enabled = self._selected_event_id is not None
        if delete_enabled:
            self._delete_event_button.enable()
        else:
            self._delete_event_button.disable()

    def set_all_files_mode(self, enabled: bool) -> None:
        """Set all-files mode and notify bindings to refresh data.
        
        Args:
            enabled: True to show all files, False to show single file.
        """
        self._show_all_files = enabled
        # Update checkbox state if it exists
        if self._all_files_checkbox is not None:
            self._all_files_checkbox.value = enabled
        # Notify bindings to refresh if callback is set
        if self._on_all_files_mode_changed is not None:
            self._on_all_files_mode_changed()