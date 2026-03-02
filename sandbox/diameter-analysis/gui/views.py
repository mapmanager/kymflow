from __future__ import annotations

import json

from typing import Any

from nicegui import ui

from .models import AppState
from .controllers import AppController
from .file_picker import prompt_tiff_path
from .widgets import dataclass_editor_card


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

    with ui.row().classes("w-full items-center gap-2"):
        ui.button("Generate synthetic", on_click=lambda: _safe_run(controller.generate_synthetic)).props("outline")
        ui.button("Detect", on_click=lambda: _safe_run(controller.detect)).props("color=primary")
        ui.switch("Show center", value=state.gui.show_center_overlay).on(
            "update:model-value",
            lambda e: _set_center(controller, bool(e.args)),
        )

    ui.separator()

    # Two-column layout:
    # - Left: parameter editors (synthetic + detection)
    # - Right: plots (image over line)
    # Use 'no-wrap' so the plots never flow below the cards.
    with ui.row().classes("w-full gap-2 items-start no-wrap"):
        # Left column: stacked parameter cards
        with ui.column().classes("w-[460px] shrink-0 gap-2"):
            if state.synthetic_params is not None and hasattr(state.synthetic_params, "__dataclass_fields__"):
                dataclass_editor_card(
                    state.synthetic_params,
                    title="Synthetic Params",

                    on_change=lambda name, val: _mutate_dataclass(controller, "synthetic_params", name, val),
                )
            else:
                with ui.card().classes("w-full"):
                    ui.label("Synthetic params not set.").classes("text-sm")

            synthetic_dict_el = ui.textarea(
                label="Synthetic Params (dict / copy)",
                value=_pretty_dict(state.synthetic_params.to_dict()),
            ).props("readonly autogrow").classes("w-full font-mono text-xs")

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

                async def _on_open_tiff() -> None:
                    try:
                        chosen = await prompt_tiff_path(
                            initial_dir="/Users/cudmore/Dropbox/data/cell-shortening/fig1"
                        )
                        if not chosen:
                            return
                        controller.load_tiff(
                            chosen,
                            seconds_per_line=float(tiff_seconds_el.value or 0.001),
                            um_per_pixel=float(tiff_um_el.value or 0.15),
                        )
                        ui.notify("TIFF loaded", type="positive", timeout=1200)
                    except Exception as e:
                        ui.notify(str(e), type="negative", timeout=8000)

                ui.button("Open TIFF...", on_click=_on_open_tiff).props("outline")

            if state.detection_params is not None and hasattr(state.detection_params, "__dataclass_fields__"):
                dataclass_editor_card(
                    state.detection_params,
                    title="Detection Params",

                    on_change=lambda name, val: _mutate_dataclass(controller, "detection_params", name, val),
                )
            else:
                with ui.card().classes("w-full"):
                    ui.label("Detection params not set (import/build failed).").classes("text-sm")
                    ui.label("Check console for the failure reason.").classes("text-xs text-gray-500")

            detection_dict_el = ui.textarea(
                label="Detection Params (dict / copy)",
                value=_pretty_dict(state.detection_params.to_dict()),
            ).props("readonly autogrow").classes("w-full font-mono text-xs")

        with ui.column().classes("w-[460px] shrink-0 gap-2"):
            if state.post_filter_params is not None and hasattr(state.post_filter_params, "__dataclass_fields__"):
                dataclass_editor_card(
                    state.post_filter_params,
                    title="Post Filter Params",
                    on_change=lambda name, val: _mutate_dataclass(controller, "post_filter_params", name, val),
                )
            else:
                with ui.card().classes("w-full"):
                    ui.label("Post filter params not set (loaded by app).").classes("text-sm")
                    
        # Right column: stacked plots, positioned to the right of the params
        with ui.column().classes("flex-1 gap-2"):
            fig_img_el = ui.plotly(controller.fig_img or {}).classes("w-full h-[560px]")
            fig_line_el = ui.plotly(controller.fig_line or {}).classes("w-full h-[320px]")

            fig_img_el.on("plotly_relayout", lambda e: controller.on_relayout("img", e.args or {}))
            fig_line_el.on("plotly_relayout", lambda e: controller.on_relayout("line", e.args or {}))

            def _refresh(_: AppState) -> None:
                fig_img_el.figure = controller.fig_img or {}
                fig_line_el.figure = controller.fig_line or {}
                fig_img_el.update()
                fig_line_el.update()

                # Update dict textareas so they match the current dataclass state.
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
                    loaded_path_el.text = f"Loaded path: {state.loaded_path if state.loaded_path else '(none)'}"
                    loaded_path_el.update()
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
