from __future__ import annotations

import json
import logging

from typing import Any

from nicegui import ui

from kymflow.gui_v2.events import FileSelection
from kymflow.gui_v2.views.file_table_view import FileTableView

from .controllers import AppController
from .file_table_integration import filter_tiff_images, find_kym_image_by_path, iter_kym_images
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

    def _on_file_selected(file_selection: FileSelection) -> None:
        if state.is_busy:
            ui.notify("Busy... detect is running", type="warning", timeout=2000)
            return
        path = file_selection.path
        if not path:
            return
        try:
            # abb we do not need find_kym_image_by_path()
            # we can use KymImageList.find_by_path(path)
            # selected_kym_image = find_kym_image_by_path(state.kym_image_list, str(path))
            selected_kym_image = state.kym_image_list.find_by_path(str(path)) if state.kym_image_list else None
            
            # we do not need to load, we can get image (lazy load from KymImage with just
            # img_data:np.ndarray = selected_kym_image.getChannelData(1)
            controller.load_tiff(str(path), selected_kym_image=selected_kym_image)

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
                if state.detection_params is not None and hasattr(
                    state.detection_params, "__dataclass_fields__"
                ):
                    def _reset_detection_params() -> None:
                        from diameter_analysis import DiameterDetectionParams

                        controller.state.detection_params = DiameterDetectionParams()
                        controller._emit()
                        ui.notify("Detection Params reset to defaults", type="positive", timeout=1500)

                    dataclass_editor_card(
                        state.detection_params,
                        title="Detection Params",
                        on_change=lambda name, val: _mutate_dataclass(
                            controller, "detection_params", name, val
                        ),
                        header_actions=lambda: ui.button(
                            "Reset to Defaults",
                            on_click=_reset_detection_params,
                        ).props("outline dense"),
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
                    _set_textarea_from_dataclass(synthetic_dict_el, state.synthetic_params)
                    _set_textarea_from_dataclass(detection_dict_el, state.detection_params)

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


def _set_textarea_from_dataclass(textarea: Any, obj: Any) -> None:
    if obj is None:
        return
    try:
        textarea.value = _pretty_dict(obj.to_dict())
        textarea.update()
    except Exception:
        return


def _set_center(controller: AppController, v: bool) -> None:
    controller.state.gui.show_center_overlay = v
    controller._rebuild_figures()
    controller._emit()
