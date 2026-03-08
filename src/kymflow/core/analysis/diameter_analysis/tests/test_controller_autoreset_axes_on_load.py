from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from gui.controllers import AppController
from gui.models import AppState


def _make_controller(seconds_per_line: float = 0.5, um_per_pixel: float = 2.0) -> AppController:
    state = AppState()
    state.synthetic_params = SimpleNamespace(
        seconds_per_line=seconds_per_line,
        um_per_pixel=um_per_pixel,
    )
    return AppController(state)


def _img_xrange(controller: AppController) -> list[float]:
    assert controller.fig_img is not None
    return controller.fig_img["layout"]["xaxis"]["range"]


def _img_yrange(controller: AppController) -> list[float]:
    assert controller.fig_img is not None
    return controller.fig_img["layout"]["yaxis"]["range"]


def _line_xrange(controller: AppController) -> list[float]:
    assert controller.fig_line is not None
    return controller.fig_line["layout"]["xaxis"]["range"]


def test_load_twice_resets_to_new_full_extents() -> None:
    controller = _make_controller(seconds_per_line=0.5, um_per_pixel=2.0)

    controller.set_img(np.ones((4, 6), dtype=float), source="synthetic")
    assert _img_xrange(controller) == [0.0, 1.5]
    assert _img_yrange(controller) == [0.0, 10.0]
    assert _line_xrange(controller) == [0.0, 1.5]

    controller.set_img(np.ones((8, 3), dtype=float), source="synthetic")
    assert _img_xrange(controller) == [0.0, 3.5]
    assert _img_yrange(controller) == [0.0, 4.0]
    assert _line_xrange(controller) == [0.0, 3.5]


def test_user_zoom_persists_on_non_load_rebuild() -> None:
    controller = _make_controller(seconds_per_line=0.25, um_per_pixel=1.0)
    controller.set_img(np.ones((10, 5), dtype=float), source="synthetic")

    controller.on_relayout("img", {"xaxis.range": [0.5, 1.5]})
    assert controller.state.x_range == (0.5, 1.5)

    controller.apply_post_filter_only()
    assert controller.state.x_range == (0.5, 1.5)
    assert _img_xrange(controller) == [0.5, 1.5]
    assert _line_xrange(controller) == [0.5, 1.5]


def test_new_load_overwrites_previous_zoom_once() -> None:
    controller = _make_controller(seconds_per_line=0.1, um_per_pixel=1.5)
    controller.set_img(np.ones((20, 12), dtype=float), source="synthetic")

    controller.on_relayout("line", {"xaxis.range[0]": 0.3, "xaxis.range[1]": 0.9})
    assert controller.state.x_range == (0.3, 0.9)

    controller.set_img(np.ones((6, 12), dtype=float), source="synthetic")
    assert controller.state.x_range == (0.0, 0.5)
    assert _img_xrange(controller) == [0.0, 0.5]
    assert _line_xrange(controller) == [0.0, 0.5]
