"""Sandbox: nested splitters with CustomAgGrid_v2 and Plotly."""

from __future__ import annotations

from nicegui import ui
import plotly.graph_objects as go

from nicewidgets.custom_ag_grid.config import ColumnConfig, GridConfig
from nicewidgets.custom_ag_grid.custom_ag_grid_v2 import CustomAgGrid_v2


def _file_list_grid() -> CustomAgGrid_v2:
    rows = [
        {"file_id": "F001", "name": "kym_001.tif", "frames": 1200, "status": "ready"},
        {"file_id": "F002", "name": "kym_002.tif", "frames": 980, "status": "ready"},
        {"file_id": "F003", "name": "kym_003.tif", "frames": 1430, "status": "processing"},
        {"file_id": "F004", "name": "kym_004.tif", "frames": 1110, "status": "ready"},
    ]
    columns = [
        ColumnConfig(field="file_id", header="File ID", extra_grid_options={"width": 120}),
        ColumnConfig(field="name", header="Filename", extra_grid_options={"width": 220}),
        ColumnConfig(field="frames", header="Frames", extra_grid_options={"width": 100}),
        ColumnConfig(field="status", header="Status", extra_grid_options={"width": 120}),
    ]
    grid_cfg = GridConfig(selection_mode="single", row_id_field="file_id", show_row_index=True)
    return CustomAgGrid_v2(
        data=rows,
        columns=columns,
        grid_config=grid_cfg,
        runtimeWidgetName="SandboxFileList",
    )


def _kym_event_grid(parent: ui.element | None = None) -> CustomAgGrid_v2:
    rows = [
        {"event_id": "E01", "roi": 1, "t_start": 0.5, "t_end": 2.1, "type": "stall"},
        {"event_id": "E02", "roi": 1, "t_start": 3.2, "t_end": 4.0, "type": "run"},
        {"event_id": "E03", "roi": 2, "t_start": 1.1, "t_end": 1.8, "type": "stall"},
        {"event_id": "E04", "roi": 3, "t_start": 5.0, "t_end": 6.4, "type": "run"},
    ]
    columns = [
        ColumnConfig(field="event_id", header="Event ID", extra_grid_options={"width": 120}),
        ColumnConfig(field="roi", header="ROI", extra_grid_options={"width": 80}),
        ColumnConfig(field="t_start", header="t_start", extra_grid_options={"width": 110}),
        ColumnConfig(field="t_end", header="t_end", extra_grid_options={"width": 110}),
        ColumnConfig(field="type", header="Type", extra_grid_options={"width": 120}),
    ]
    grid_cfg = GridConfig(selection_mode="single", row_id_field="event_id", show_row_index=True)
    return CustomAgGrid_v2(
        data=rows,
        columns=columns,
        grid_config=grid_cfg,
        parent=parent,
        runtimeWidgetName="SandboxKymEventList",
    )


def _standalone_grid() -> CustomAgGrid_v2:
    rows = [
        {"item_id": "S01", "label": "alpha", "value": 10},
        {"item_id": "S02", "label": "beta", "value": 20},
        {"item_id": "S03", "label": "gamma", "value": 15},
        {"item_id": "S04", "label": "delta", "value": 30},
    ]
    columns = [
        ColumnConfig(field="item_id", header="Item ID", extra_grid_options={"width": 120}),
        ColumnConfig(field="label", header="Label", extra_grid_options={"width": 160}),
        ColumnConfig(field="value", header="Value", extra_grid_options={"width": 100}),
    ]
    grid_cfg = GridConfig(selection_mode="single", row_id_field="item_id", show_row_index=True)
    return CustomAgGrid_v2(
        data=rows,
        columns=columns,
        grid_config=grid_cfg,
        runtimeWidgetName="SandboxStandaloneGrid",
    )


def _dummy_plot() -> ui.plotly:
    fig = go.Figure(
        data=[
            go.Scatter(
                x=[0, 1, 2, 3, 4, 5],
                y=[0.2, 1.4, 0.7, 2.2, 1.8, 2.9],
                mode="lines+markers",
                name="signal",
            )
        ]
    )
    fig.update_layout(margin=dict(l=20, r=20, t=20, b=20))
    return ui.plotly(fig).classes("w-full h-full")


@ui.page("/")
def main_page() -> None:
    ui.label("Sandbox: CustomAgGrid_v2 in nested splitters").classes("text-lg")

    with ui.splitter(value=25, limits=(15, 60)).classes("w-full h-screen") as h_splitter:
        # LEFT: Dummy context pane
        with h_splitter.before:
            with ui.column().classes("w-full h-full p-4 gap-2"):
                ui.label("Left Pane (dummy content)").classes("text-sm text-gray-500")
                ui.label("Project: demo_session_01")
                ui.label("User: sandbox")
                ui.separator()
                ui.label("Notes:")
                ui.markdown("- Splitter layout demo\n- AG Grid in nested panes\n- Plotly in-between")

        # RIGHT: Nested splitters with grid/plot/grid
        with h_splitter.after:
            with ui.column().classes("w-full h-full min-h-0 min-w-0 p-4 gap-4 flex flex-col"):
                ui.label("Right Pane (file list + plot + kym events)").classes("text-sm text-gray-500")

                with ui.splitter(value=30, limits=(10, 70), horizontal=True).classes(
                    "w-full flex-1 min-h-0 min-w-0"
                ) as file_image_splitter:
                    # TOP: File list grid
                    with file_image_splitter.before:
                        with ui.column().classes("w-full h-full min-h-0 min-w-0"):
                            ui.label("File List").classes("text-sm text-gray-500")
                            _file_list_grid().grid.classes("w-full h-full")

                    # BOTTOM: nested splitter (plot + kym event list)
                    with file_image_splitter.after:
                        with ui.splitter(value=60, limits=(20, 85), horizontal=True).classes(
                            "w-full flex-1 min-h-0 min-w-0"
                        ) as plot_event_splitter:
                            # TOP: Plotly plot
                            with plot_event_splitter.before:
                                with ui.column().classes("w-full h-full min-h-0 min-w-0"):
                                    ui.label("Plotly Plot").classes("text-sm text-gray-500")
                                    _dummy_plot()

                            # BOTTOM: Kym event list grid + toolbar
                            with plot_event_splitter.after:
                                with ui.column().classes("w-full h-full min-h-0 min-w-0").style(
                                    "outline: 1px solid #f97316;"
                                ):
                                    ui.label("Kym Event List").classes("text-sm text-gray-500")
                                    with ui.row().classes(
                                        "w-full h-full min-h-0 min-w-0 items-stretch gap-2"
                                    ).style("outline: 1px dashed #22c55e;"):
                                        with ui.column().classes(
                                            "flex-1 min-h-0 min-w-0 flex flex-col"
                                        ).style("outline: 1px dashed #3b82f6;"):
                                            grid_container = ui.column().classes(
                                                "w-full h-full min-h-0 min-w-0 overflow-hidden flex flex-col"
                                            )
                                            _kym_event_grid(parent=grid_container)
                                        with ui.column().classes("w-40 shrink-0").style(
                                            "outline: 1px dashed #a855f7;"
                                        ):
                                            ui.label("Toolbar").classes("text-xs text-gray-400")
                                            ui.button("Add").props("dense")
                                            ui.button("Delete").props("dense")
                                            ui.button("Export").props("dense")

                # Test: plain ui.aggrid in a two-column layout
                with ui.column().classes("w-full min-h-0 min-w-0"):
                    ui.label("Plain ui.aggrid (toolbar + grid)").classes("text-sm text-gray-500")
                    with ui.row().classes("w-full min-h-0 min-w-0 items-stretch gap-2"):
                        with ui.column().classes("w-40 shrink-0"):
                            ui.label("Toolbar").classes("text-xs text-gray-400")
                            ui.button("Refresh").props("dense")
                        with ui.column().classes("flex-1 min-h-0 min-w-0 flex flex-col"):
                            ui.aggrid(
                                {
                                    "columnDefs": [
                                        {"headerName": "ID", "field": "id", "width": 90},
                                        {"headerName": "Name", "field": "name", "width": 180},
                                        {"headerName": "Value", "field": "value", "width": 120},
                                    ],
                                    "rowData": [
                                        {"id": "A1", "name": "alpha", "value": 10},
                                        {"id": "B2", "name": "beta", "value": 20},
                                        {"id": "C3", "name": "gamma", "value": 15},
                                        {"id": "D4", "name": "delta", "value": 30},
                                    ],
                                }
                            ).classes("w-full").style("height: 12rem;")
                # with ui.column().classes("w-full min-h-0 min-w-0"):
                #     ui.label("Standalone CustomAg Grid").classes("text-sm text-gray-500")
                #     with ui.element("div").classes("w-full min-w-0").style(
                #         "display: grid; grid-template-columns: 10rem 1fr; gap: 0.5rem; overflow: hidden;"
                #     ):
                #         with ui.column().classes("min-w-0"):
                #             ui.label("Controls").classes("text-xs text-gray-400")
                #             ui.button("Run").props("dense")
                #             ui.button("Clear").props("dense")
                #         with ui.column().classes("min-w-0"):
                #             _standalone_grid().grid.classes("w-full").style("height: 12rem;")


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(native=True,
        reload=False,
        window_size=(800, 800),
        title="AG Grid Layout",
    )
