"""Always-visible main contrast widget above image viewer."""

from __future__ import annotations

from typing import Callable, Optional

from nicewidgets.image_line_widget.image_contrast_widget import ImageContrastWidget
from nicewidgets.image_line_widget.models import ContrastEvent
from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.plotting.colorscales import get_colorscale
from kymflow.core.plotting.theme import ThemeMode
from kymflow.gui_v2.client_utils import safe_call
from kymflow.gui_v2.events import ImageDisplayChange, SelectionOrigin
from kymflow.gui_v2.events_legacy import ImageDisplayOrigin
from kymflow.gui_v2.state import ImageDisplayParams
OnImageDisplayChange = Callable[[ImageDisplayChange], None]
DEFAULT_FILE_LUT = "Gray"


def _widget_to_plotly_lut(value: str) -> str | list[list[float | str]]:
    resolved = get_colorscale(value)
    return resolved


def _plotly_to_widget_lut(value: str) -> str:
    return "Gray" if value in {"Grays", "gray", "greys"} else value


class MainContrastWidgetView:
    """Thin adapter around `ImageContrastWidget` for gui_v2 event flow."""

    def __init__(self, *, on_image_display_change: OnImageDisplayChange) -> None:
        self._on_image_display_change = on_image_display_change
        self._widget: Optional[ImageContrastWidget] = None
        self._current_file: Optional[KymImage] = None

    def render(self) -> None:
        self._widget = ImageContrastWidget(
            "main_image_contrast_widget",
            on_contrast_changed=self._on_contrast_changed,
            build_ui=True,
        )
        # Bailout mode: disable LUT changes in UI (zmin/zmax only).
        if getattr(self._widget, "_lut_select", None) is not None:
            self._widget._lut_select.disable()
            self._widget._lut_select.tooltip("Color LUT is temporarily fixed to grayscale")
        self._widget.set_colorscale(DEFAULT_FILE_LUT)

    def set_selected_file(self, file: Optional[KymImage]) -> None:
        safe_call(self._set_selected_file_impl, file)

    def _set_selected_file_impl(self, file: Optional[KymImage]) -> None:
        self._current_file = file
        if self._widget is None:
            return
        if file is None:
            self._widget.set_file(None)
            return
        image = file.get_img_slice(channel=1)
        self._widget.set_channel(1, image)
        # Policy: every file click resets LUT to default and applies auto contrast.
        self._widget.set_colorscale(DEFAULT_FILE_LUT)
        zmin, zmax = self._widget.get_contrast()
        self._on_image_display_change(
            ImageDisplayChange(
                params=ImageDisplayParams(
                    colorscale=_widget_to_plotly_lut(DEFAULT_FILE_LUT),
                    zmin=int(zmin),
                    zmax=int(zmax),
                    origin=ImageDisplayOrigin.CONTRAST_WIDGET,
                ),
                origin=SelectionOrigin.IMAGE_VIEWER,
                phase="intent",
            )
        )

    def set_selected_roi(self, roi_id: Optional[int]) -> None:
        safe_call(self._set_selected_roi_impl, roi_id)

    def _set_selected_roi_impl(self, roi_id: Optional[int]) -> None:
        if self._widget is None:
            return
        # Keep ROI context in sync with app state; widget currently does not crop by ROI.
        self._widget.select_roi_by_index(roi_id)

    def set_image_display(self, params: ImageDisplayParams) -> None:
        safe_call(self._set_image_display_impl, params)

    def _set_image_display_impl(self, params: ImageDisplayParams) -> None:
        if self._widget is None:
            return
        # Bailout mode: keep widget LUT pinned to default grayscale.
        self._widget.set_colorscale(DEFAULT_FILE_LUT)
        if params.zmin is not None and params.zmax is not None:
            self._widget.set_contrast(int(params.zmin), int(params.zmax))

    def set_theme(self, theme: ThemeMode) -> None:
        safe_call(self._set_theme_impl, theme)

    def _set_theme_impl(self, theme: ThemeMode) -> None:
        # Reserved for future styling; widget already supports theme input.
        _ = theme

    def _on_contrast_changed(self, event: ContrastEvent) -> None:
        params = ImageDisplayParams(
            # Bailout mode: ignore UI LUT and always use default grayscale.
            colorscale=_widget_to_plotly_lut(DEFAULT_FILE_LUT),
            zmin=int(event.zmin),
            zmax=int(event.zmax),
            origin=ImageDisplayOrigin.CONTRAST_WIDGET,
        )
        self._on_image_display_change(
            ImageDisplayChange(
                params=params,
                origin=SelectionOrigin.IMAGE_VIEWER,
                phase="intent",
            )
        )

