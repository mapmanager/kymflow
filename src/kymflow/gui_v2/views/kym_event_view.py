"""Velocity event table view component using CustomAgGrid_v2."""

from __future__ import annotations

from typing import Callable, Iterable, List, Optional

from nicegui import ui
from nicewidgets.custom_ag_grid.config import ColumnConfig, GridConfig, SelectionMode
from nicewidgets.custom_ag_grid.custom_ag_grid_v2 import CustomAgGrid_v2

from kymflow.core.analysis.velocity_events.velocity_events import UserType, VelocityEvent
from kymflow.gui_v2.events import (
    EventSelection,
    EventSelectionOptions,
    SelectionOrigin,
    VelocityEventUpdate,
)

Rows = List[dict[str, object]]
OnSelected = Callable[[EventSelection], None]
OnEventUpdate = Callable[[VelocityEventUpdate], None]


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
        selection_mode: SelectionMode = "single",
    ) -> None:
        self._on_selected = on_selected
        self._on_event_update = on_event_update
        self._selection_mode = selection_mode
        self._grid: CustomAgGrid_v2 | None = None
        self._suppress_emit: bool = False
        self._pending_rows: Rows = []
        self._all_rows: Rows = []
        self._roi_filter: int | None = None
        self._zoom_enabled: bool = False
        self._zoom_pad_sec: float = 1.0

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
