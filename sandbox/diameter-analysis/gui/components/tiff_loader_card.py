from __future__ import annotations

import logging
from typing import Any

from nicegui import ui

from ..controllers import AppController
from ..diameter_kymflow_adapter import get_kym_by_path
from ..file_picker import prompt_tiff_path

logger = logging.getLogger(__name__)


class TiffLoaderCard:
    def __init__(self, controller: AppController, *, initial_dir: str) -> None:
        self.controller = controller
        self.initial_dir = initial_dir

        self._seconds_input: Any | None = None
        self._um_input: Any | None = None
        self._loaded_path_label: Any | None = None
        self._loaded_shape_label: Any | None = None
        self._loaded_dtype_label: Any | None = None
        self._loaded_min_label: Any | None = None
        self._loaded_max_label: Any | None = None
        self._error_label: Any | None = None

    def render(self) -> None:
        state = self.controller.state
        try:
            seconds, um = self.controller.resolve_units(source=state.source)
        except Exception:
            seconds, um = 0.001, 0.15

        with ui.card().classes("w-full"):
            ui.label("TIFF Loader").classes("text-lg font-semibold")
            self._seconds_input = ui.number(
                label="seconds_per_line",
                value=float(seconds),
                step=0.0001,
            ).classes("w-full")
            self._um_input = ui.number(
                label="um_per_pixel",
                value=float(um),
                step=0.001,
            ).classes("w-full")
            self._loaded_path_label = ui.label(
                f"Loaded path: {state.loaded_path if state.loaded_path else '(none)'}"
            ).classes("text-sm break-all")
            self._loaded_shape_label = ui.label("Shape: (none)").classes("text-sm")
            self._loaded_dtype_label = ui.label("Dtype: (none)").classes("text-sm")
            self._loaded_min_label = ui.label("Min: (none)").classes("text-sm")
            self._loaded_max_label = ui.label("Max: (none)").classes("text-sm")
            self._error_label = ui.label("").classes("text-sm text-red-600")
            ui.button("Open TIFF...", on_click=self._on_open_tiff).props("outline")

        self.refresh()

    async def _on_open_tiff(self) -> None:
        if self.controller.state.is_busy:
            ui.notify("Busy... detect is running", type="warning", timeout=2000)
            return
        try:
            chosen = await prompt_tiff_path(initial_dir=self.initial_dir)
            if not chosen:
                return
            self._load_path(str(chosen))
            ui.notify("TIFF loaded", type="positive", timeout=1200)
        except Exception as e:
            msg = f"Failed to load TIFF: {e}"
            logger.error("TIFF load failed: %s", e)
            self.controller.state.tiff_error = msg
            self.controller._emit()
            ui.notify(msg, type="negative", timeout=8000)

    def _load_path(self, path: str) -> None:
        state = self.controller.state
        selected_kym_image = (
            get_kym_by_path(state.kym_image_list, str(path))
            if state.kym_image_list is not None
            else None
        )
        self.controller.load_tiff(
            path,
            seconds_per_line=self._input_value(self._seconds_input),
            um_per_pixel=self._input_value(self._um_input),
            selected_kym_image=selected_kym_image,
        )

    @staticmethod
    def _input_value(widget: Any | None) -> float | None:
        if widget is None:
            return None
        try:
            raw = widget.value
        except Exception:
            return None
        try:
            return float(raw)
        except Exception:
            return None

    @staticmethod
    def _set_widget(widget: Any | None, *, value: Any) -> None:
        if widget is None:
            return
        widget.value = value
        widget.update()

    @staticmethod
    def _set_label(widget: Any | None, text: str) -> None:
        if widget is None:
            return
        widget.text = text
        widget.update()

    def refresh(self) -> None:
        state = self.controller.state
        try:
            seconds, um = self.controller.resolve_units(source=state.source)
        except Exception:
            seconds, um = 0.001, 0.15

        self._set_widget(self._seconds_input, value=float(seconds))
        self._set_widget(self._um_input, value=float(um))
        self._set_label(
            self._loaded_path_label,
            f"Loaded path: {state.loaded_path if state.loaded_path else '(none)'}",
        )
        self._set_label(
            self._loaded_shape_label,
            f"Shape: {state.loaded_shape}" if state.loaded_shape is not None else "Shape: (none)",
        )
        self._set_label(
            self._loaded_dtype_label,
            f"Dtype: {state.loaded_dtype}" if state.loaded_dtype is not None else "Dtype: (none)",
        )
        self._set_label(
            self._loaded_min_label,
            f"Min: {state.loaded_min}" if state.loaded_min is not None else "Min: (none)",
        )
        self._set_label(
            self._loaded_max_label,
            f"Max: {state.loaded_max}" if state.loaded_max is not None else "Max: (none)",
        )
        self._set_label(self._error_label, state.tiff_error or "")
