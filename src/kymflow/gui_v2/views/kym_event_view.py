"""Velocity event table view component using CustomAgGrid_v2."""

from __future__ import annotations

from typing import Callable, Iterable, List, Optional

from nicegui import ui
from nicewidgets.custom_ag_grid.config import ColumnConfig, GridConfig, SelectionMode
from nicewidgets.custom_ag_grid.custom_ag_grid_v2 import CustomAgGrid_v2

from kymflow.core.analysis.velocity_events.velocity_events import UserType, VelocityEvent
from kymflow.core.utils.logging import get_logger
from kymflow.gui_v2.events import (
    EventSelection,
    EventSelectionOptions,
    SelectionOrigin,
    SetKymEventRangeState,
    SetKymEventXRange,
    VelocityEventUpdate,
)

Rows = List[dict[str, object]]
OnSelected = Callable[[EventSelection], None]
OnEventUpdate = Callable[[VelocityEventUpdate], None]
OnRangeState = Callable[[SetKymEventRangeState], None]

logger = get_logger(__name__)


def _col(
    field: str,
    header: Optional[str] = None,
    *,
    width: Optional[int] = None,
    hide: bool = False,
    cell_class: Optional[str] = None,
    editable: bool = False,
    editor: str = "auto",
    choices: Optional[Iterable[object] | str] = None,
) -> ColumnConfig:
    extra: dict[str, object] = {}
    if width is not None:
        extra["width"] = width
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
        extra_grid_options=extra,
    )


def _default_columns() -> list[ColumnConfig]:
    return [
        _col("roi_id", "ROI", width=80, cell_class="ag-cell-right"),
        _col(
            "user_type",
            "User Type",
            width=160,
            editable=True,
            editor="select",
            choices=[v.value for v in UserType],
        ),
        _col("event_type", "Type", width=160),
        _col("t_start", "t_start", width=110, cell_class="ag-cell-right"),
        _col("t_end", "t_end", width=110, cell_class="ag-cell-right"),
        _col("t_duration", "t_duration", width=110, cell_class="ag-cell-right"),
        _col("strength", "strength", width=110, cell_class="ag-cell-right"),
        _col("event_id", "event_id", hide=True),
        _col("path", "path", hide=True),
    ]


class KymEventView:
    """Velocity event table view using CustomAgGrid_v2."""

    def __init__(
        self,
        *,
        on_selected: OnSelected,
        on_event_update: OnEventUpdate | None = None,
        on_range_state: OnRangeState | None = None,
        selection_mode: SelectionMode = "single",
    ) -> None:
        self._on_selected = on_selected
        self._on_event_update = on_event_update
        self._on_range_state = on_range_state
        self._selection_mode = selection_mode
        self._grid: CustomAgGrid_v2 | None = None
        self._suppress_emit: bool = False
        self._pending_rows: Rows = []
        self._all_rows: Rows = []
        self._roi_filter: int | None = None
        self._zoom_enabled: bool = True
        self._zoom_pad_sec: float = 1.0
        self._setting_kym_event_range_state: bool = False
        self._set_range_button: ui.button | None = None
        self._cancel_range_button: ui.button | None = None
        self._range_notification: ui.notification | None = None
        self._selected_event_id: str | None = None
        self._selected_event_roi_id: int | None = None
        self._selected_event_path: str | None = None

    def render(self) -> None:
        """Create the grid UI inside the current container."""
        self._grid = None
        with ui.row().classes("w-full items-start gap-4"):
            with ui.column().classes("w-40 shrink-0"):
                ui.label("Event Controls").classes("text-sm text-gray-500")
                ui.checkbox("Auto Zoom", value=self._zoom_enabled).on_value_change(
                    lambda e: self._set_zoom_enabled(bool(e.value))
                )
                ui.number("+/- sec", value=self._zoom_pad_sec, step=0.1).on_value_change(
                    lambda e: self._set_zoom_pad_sec(float(e.value))
                )
                with ui.row().classes("w-full gap-2"):
                    self._set_range_button = ui.button(
                        "Set Start/Stop",
                        on_click=self._on_set_event_range_clicked,
                    )
                    self._cancel_range_button = ui.button(
                        "Cancel",
                        on_click=self._on_cancel_event_range_clicked,
                    )
                self._update_range_button_state()

            with ui.column().classes("grow"):
                grid_cfg = GridConfig(
                    selection_mode=self._selection_mode,  # type: ignore[arg-type]
                    height="16rem",
                    row_id_field="event_id",
                )
                self._grid = CustomAgGrid_v2(
                    data=self._pending_rows,
                    columns=_default_columns(),
                    grid_config=grid_cfg,
                )
                self._grid.on_row_selected(self._on_row_selected)
                self._grid.on_cell_edited(self._on_cell_edited)

    def _set_zoom_enabled(self, value: bool) -> None:
        self._zoom_enabled = value

    def _set_zoom_pad_sec(self, value: float) -> None:
        self._zoom_pad_sec = value

    def set_events(self, rows: Iterable[dict[str, object]]) -> None:
        """Update table contents from velocity report rows."""
        self._all_rows = list(rows)
        self._apply_filter()

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
        else:
            self._selected_event_id = None
        self._selected_event_roi_id = None
        self._selected_event_path = None
        self._update_range_button_state()

    def set_selected_roi(self, roi_id: int | None) -> None:
        """Filter rows by ROI ID (None clears filter)."""
        self._roi_filter = roi_id
        self._apply_filter()

    def _apply_filter(self) -> None:
        if self._roi_filter is None:
            rows = list(self._all_rows)
        else:
            rows = [
                row for row in self._all_rows if row.get("roi_id") == self._roi_filter
            ]
        self._pending_rows = rows
        if self._grid is not None:
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
        logger.debug("handle_set_kym_event_x_range event_id=%s", e.event_id)
        self._setting_kym_event_range_state = False
        self._emit_range_state(False)
        self._update_range_button_state()
        self._set_range_notification_visible(False)

        if self._selected_event_id is None:
            logger.debug("no selected event; ignoring range proposal")
            return
        if e.event_id is not None and e.event_id != self._selected_event_id:
            logger.debug("range proposal event_id mismatch (current=%s)", self._selected_event_id)
            return
        if self._selected_event_path is not None and e.path is not None:
            if self._selected_event_path != e.path:
                logger.debug("range proposal path mismatch (current=%s)", self._selected_event_path)
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
        logger.debug("set_event_range_clicked -> toggle state")
        self._setting_kym_event_range_state = not self._setting_kym_event_range_state
        self._emit_range_state(self._setting_kym_event_range_state)
        self._update_range_button_state()
        if self._setting_kym_event_range_state:
            self._set_range_notification_visible(True)
        else:
            self._set_range_notification_visible(False)

    def _on_cancel_event_range_clicked(self) -> None:
        if not self._setting_kym_event_range_state:
            return
        logger.debug("cancel_event_range_clicked -> disable state")
        self._setting_kym_event_range_state = False
        self._emit_range_state(False)
        self._update_range_button_state()
        self._set_range_notification_visible(False)

    def _emit_range_state(self, enabled: bool) -> None:
        if self._on_range_state is None:
            return
        logger.debug("emit SetKymEventRangeState enabled=%s", enabled)
        self._on_range_state(
            SetKymEventRangeState(
                enabled=enabled,
                event_id=self._selected_event_id,
                roi_id=self._selected_event_roi_id,
                path=self._selected_event_path,
                origin=SelectionOrigin.EVENT_TABLE,
                phase="intent",
            )
        )

    def _update_range_button_state(self) -> None:
        if self._set_range_button is None or self._cancel_range_button is None:
            return
        if self._selected_event_id is None:
            self._set_range_button.disable()
            self._set_range_button.text = "Set Event Start/Stop"
            # self._set_range_button.props(remove="color")
            self._cancel_range_button.disable()
            # self._cancel_range_button.props(remove="color")
            self._set_range_notification_visible(False)
            return
        self._set_range_button.enable()
        if self._setting_kym_event_range_state:
            self._set_range_button.text = "Set Event Start/Stop"
            # self._set_range_button.props("color=orange")
            self._cancel_range_button.enable()
            # self._cancel_range_button.props("color=orange")
        else:
            self._set_range_button.text = "Set Event Start/Stop"
            # self._set_range_button.props(remove="color")
            self._cancel_range_button.disable()
            #  self._cancel_range_button.props(remove="color")
            self._set_range_notification_visible(False)

    def _set_range_notification_visible(self, visible: bool) -> None:
        if visible:
            if self._range_notification is not None:
                self._range_notification.dismiss()
            self._range_notification = ui.notification(
                "Draw a rectangle on the plot to set event start/stop.",
                color="warning",
                timeout=None,
            )
        else:
            if self._range_notification is None:
                return
            self._range_notification.dismiss()
            self._range_notification = None