from __future__ import annotations

import json
import logging

from typing import Any

from nicegui import ui

from kymflow.gui_v2.events import FileSelection
from kymflow.gui_v2.views.file_table_view import FileTableView

from .controllers import AppController
from .file_picker import prompt_tiff_path
from .file_table_integration import filter_tiff_images, iter_kym_images
from .models import AppState
from .widgets import dataclass_editor_card

logger = logging.getLogger(__name__)


def _pretty_dict(d: dict) -> str:
    try:
        return json.dumps(d, indent=2, sort_keys=True)
    except Exception:
        try:
            return str(d)
        except Exception:
            return ""


def build_home_page(controller: AppController) -> None:
    state = controller.state

    ui.label("Diameter Explorer").classes("text-2xl font-bold")

    tiff_seconds_el: Any | None = None
    tiff_um_el: Any | None = None

    def _load_tiff_path(path: str) -> None:
        seconds = float(
            (tiff_seconds_el.value if tiff_seconds_el is not None else state.seconds_per_line) or 0.001
        )
        um = float((tiff_um_el.value if tiff_um_el is not None else state.um_per_pixel) or 0.15)
        controller.load_tiff(
            path,
            seconds_per_line=seconds,
            um_per_pixel=um,
        )

    def _on_file_selected(file_selection: FileSelection) -> None:
        if state.is_busy:
            ui.notify("Busy... detect is running", type="warning", timeout=2000)
            return
        path = file_selection.path
        if not path:
            return
        try:
            _load_tiff_path(str(path))
            ui.notify("TIFF loaded", type="positive", timeout=1200)
        except Exception as e:
            msg = f"Failed to load TIFF: {e}"
            logger.error("TIFF load failed from file table: %s", e)
            controller.state.tiff_error = msg
            controller._emit()
            ui.notify(msg, type="negative", timeout=8000)

    with ui.card().classes("w-full h-64"):
        ui.label("File Browser").classes("text-lg font-semibold")
        file_table_view = FileTableView(on_selected=_on_file_selected)
        file_table_view.render()
        if state.kym_image_list is not None:
            file_table_view.set_files(filter_tiff_images(iter_kym_images(state.kym_image_list)))
        else:
            file_table_view.set_files([])
        if state.file_table_warning:
            ui.label(state.file_table_warning).classes("text-sm text-orange-700")

    with ui.row().classes("w-full items-center gap-2"):
        ui.button("Generate synthetic", on_click=lambda: _safe_run(controller.generate_synthetic)).props(
            "outline"
        )
        ui.button("Detect", on_click=lambda: _safe_run(controller.detect)).props("color=primary")
        ui.switch("Show center", value=state.gui.show_center_overlay).on(
            "update:model-value",
            lambda e: _set_center(controller, bool(e.args)),
        )

    ui.separator()

    splitter = ui.splitter(value=28).props("limits=[0,100]").classes("w-full")

    with splitter.before:
        with ui.column().classes("w-full gap-2"):
            if state.synthetic_params is not None and hasattr(state.synthetic_params, "__dataclass_fields__"):
                dataclass_editor_card(
                    state.synthetic_params,
                    title="Synthetic Params",
                    on_change=lambda name, val: _mutate_dataclass(
                        controller, "synthetic_params", name, val
                    ),
                )
            else:
                with ui.card().classes("w-full"):
                    ui.label("Synthetic params not set.").classes("text-sm")

            synthetic_dict_el = ui.textarea(
                label="Synthetic Params (dict / copy)",
                value=(
                    _pretty_dict(state.synthetic_params.to_dict())
                    if state.synthetic_params is not None
                    else ""
                ),
            ).props("readonly autogrow").classes("w-full font-mono text-xs")

    with splitter.after:
        with ui.row().classes("w-full gap-2 items-start no-wrap"):
            with ui.column().classes("w-[460px] shrink-0 gap-2"):
                with ui.card().classes("w-full"):
                    ui.label("TIFF Loader").classes("text-lg font-semibold")
                    tiff_seconds_el = ui.number(
                        label="seconds_per_line",
                        value=float(state.seconds_per_line),
                        step=0.0001,
                    ).classes("w-full")
                    tiff_um_el = ui.number(
                        label="um_per_pixel",
                        value=float(state.um_per_pixel),
                        step=0.001,
                    ).classes("w-full")
                    loaded_path_el = ui.label(
                        f"Loaded path: {state.loaded_path if state.loaded_path else '(none)'}"
                    ).classes("text-sm break-all")
                    loaded_shape_el = ui.label("Shape: (none)").classes("text-sm")
                    loaded_dtype_el = ui.label("Dtype: (none)").classes("text-sm")
                    loaded_min_el = ui.label("Min: (none)").classes("text-sm")
                    loaded_max_el = ui.label("Max: (none)").classes("text-sm")
                    tiff_error_el = ui.label("").classes("text-sm text-red-600")

                    async def _on_open_tiff() -> None:
                        try:
                            chosen = await prompt_tiff_path(
                                initial_dir="/Users/cudmore/Dropbox/data/cell-shortening/fig1"
                            )
                            if not chosen:
                                return
                            _load_tiff_path(str(chosen))
                            ui.notify("TIFF loaded", type="positive", timeout=1200)
                        except Exception as e:
                            msg = f"Failed to load TIFF: {e}"
                            logger.error("TIFF load failed: %s", e)
                            controller.state.tiff_error = msg
                            controller._emit()
                            ui.notify(msg, type="negative", timeout=8000)

                    ui.button("Open TIFF...", on_click=_on_open_tiff).props("outline")

                if state.detection_params is not None and hasattr(
                    state.detection_params, "__dataclass_fields__"
                ):
                    dataclass_editor_card(
                        state.detection_params,
                        title="Detection Params",
                        on_change=lambda name, val: _mutate_dataclass(
                            controller, "detection_params", name, val
                        ),
                    )
                else:
                    with ui.card().classes("w-full"):
                        ui.label("Detection params not set (import/build failed)." ).classes("text-sm")
                        ui.label("Check console for the failure reason.").classes(
                            "text-xs text-gray-500"
                        )

                detection_dict_el = ui.textarea(
                    label="Detection Params (dict / copy)",
                    value=(
                        _pretty_dict(state.detection_params.to_dict())
                        if state.detection_params is not None
                        else ""
                    ),
                ).props("readonly autogrow").classes("w-full font-mono text-xs")

            with ui.column().classes("w-[460px] shrink-0 gap-2"):
                if state.post_filter_params is not None and hasattr(
                    state.post_filter_params, "__dataclass_fields__"
                ):
                    dataclass_editor_card(
                        state.post_filter_params,
                        title="Post Filter Params",
                        on_change=lambda name, val: _mutate_dataclass(
                            controller, "post_filter_params", name, val
                        ),
                    )
                else:
                    with ui.card().classes("w-full"):
                        ui.label("Post filter params not set (loaded by app)." ).classes("text-sm")

            with ui.column().classes("flex-1 gap-2"):
                fig_img_el = ui.plotly(controller.fig_img or {}).classes("w-full h-[560px]")
                fig_line_el = ui.plotly(controller.fig_line or {}).classes("w-full h-[320px]")

                fig_img_el.on("plotly_relayout", lambda e: controller.on_relayout("img", e.args or {}))
                fig_line_el.on(
                    "plotly_relayout", lambda e: controller.on_relayout("line", e.args or {})
                )

                def _refresh(_: AppState) -> None:
                    fig_img_el.figure = controller.fig_img or {}
                    fig_line_el.figure = controller.fig_line or {}
                    fig_img_el.update()
                    fig_line_el.update()

                    try:
                        if state.synthetic_params is not None:
                            synthetic_dict_el.value = _pretty_dict(state.synthetic_params.to_dict())
                            synthetic_dict_el.update()
                    except Exception:
                        pass
                    try:
                        if state.detection_params is not None:
                            detection_dict_el.value = _pretty_dict(state.detection_params.to_dict())
                            detection_dict_el.update()
                    except Exception:
                        pass
                    try:
                        tiff_seconds_el.value = float(state.seconds_per_line)
                        tiff_seconds_el.update()
                    except Exception:
                        pass
                    try:
                        tiff_um_el.value = float(state.um_per_pixel)
                        tiff_um_el.update()
                    except Exception:
                        pass
                    try:
                        loaded_path_el.text = (
                            f"Loaded path: {state.loaded_path if state.loaded_path else '(none)'}"
                        )
                        loaded_path_el.update()
                    except Exception:
                        pass
                    try:
                        loaded_shape_el.text = (
                            f"Shape: {state.loaded_shape}"
                            if state.loaded_shape is not None
                            else "Shape: (none)"
                        )
                        loaded_shape_el.update()
                    except Exception:
                        pass
                    try:
                        loaded_dtype_el.text = (
                            f"Dtype: {state.loaded_dtype}"
                            if state.loaded_dtype is not None
                            else "Dtype: (none)"
                        )
                        loaded_dtype_el.update()
                    except Exception:
                        pass
                    try:
                        loaded_min_el.text = (
                            f"Min: {state.loaded_min}"
                            if state.loaded_min is not None
                            else "Min: (none)"
                        )
                        loaded_min_el.update()
                    except Exception:
                        pass
                    try:
                        loaded_max_el.text = (
                            f"Max: {state.loaded_max}"
                            if state.loaded_max is not None
                            else "Max: (none)"
                        )
                        loaded_max_el.update()
                    except Exception:
                        pass
                    try:
                        tiff_error_el.text = state.tiff_error or ""
                        tiff_error_el.update()
                    except Exception:
                        pass

                controller._on_state_change = _refresh


def _safe_run(fn) -> None:
    try:
        fn()
        ui.notify("OK", type="positive", timeout=1200)
    except Exception as e:
        ui.notify(str(e), type="negative", timeout=8000)


def _mutate_dataclass(controller: AppController, attr: str, field_name: str, value: Any) -> None:
    obj = getattr(controller.state, attr)
    if obj is None:
        return
    try:
        setattr(obj, field_name, value)
        controller._emit()
    except Exception:
        try:
            from dataclasses import replace

            new_obj = replace(obj, **{field_name: value})
            setattr(controller.state, attr, new_obj)
            controller._emit()
        except Exception as e:
            ui.notify(f"Failed to set {field_name}: {e}", type="warning", timeout=6000)


def _set_center(controller: AppController, v: bool) -> None:
    controller.state.gui.show_center_overlay = v
    controller._rebuild_figures()
    controller._emit()
