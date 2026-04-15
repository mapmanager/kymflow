from __future__ import annotations

from kymflow.core.analysis.diameter_analysis.gui.controllers import AppController
from kymflow.core.analysis.diameter_analysis.gui.models import AppState


def _make_controller_and_counters() -> tuple[AppController, dict[str, int]]:
    state = AppState()
    controller = AppController(state)
    calls = {"rebuild": 0, "emit": 0}

    def _rebuild() -> None:
        calls["rebuild"] += 1

    def _emit() -> None:
        calls["emit"] += 1

    controller._rebuild_figures = _rebuild  # type: ignore[method-assign]
    controller._emit = _emit  # type: ignore[method-assign]
    return controller, calls


def test_on_relayout_image_updates_xrange_and_triggers_once() -> None:
    controller, calls = _make_controller_and_counters()

    controller.on_relayout("img", {"xaxis.range[0]": 1.25, "xaxis.range[1]": 4.5})

    assert controller.state.x_range == (1.25, 4.5)
    assert calls["rebuild"] == 0
    assert calls["emit"] == 1


def test_on_relayout_line_list_form_updates_xrange_and_triggers_once() -> None:
    controller, calls = _make_controller_and_counters()

    controller.on_relayout("line", {"xaxis.range": [2.0, 7.0]})

    assert controller.state.x_range == (2.0, 7.0)
    assert calls["rebuild"] == 0
    assert calls["emit"] == 1


def test_on_relayout_y_only_payload_is_noop() -> None:
    controller, calls = _make_controller_and_counters()
    controller.state.x_range = (0.5, 1.5)

    controller.on_relayout("img", {"yaxis.range[0]": 1, "yaxis.range[1]": 9})

    assert controller.state.x_range == (0.5, 1.5)
    assert calls["rebuild"] == 0
    assert calls["emit"] == 0


def test_on_relayout_autorange_resets_xrange_once() -> None:
    controller, calls = _make_controller_and_counters()
    controller.state.x_range = (3.0, 6.0)

    controller.on_relayout("line", {"xaxis.autorange": True})

    assert controller.state.x_range is None
    assert calls["rebuild"] == 0
    assert calls["emit"] == 1


def test_on_relayout_guard_prevents_feedback_loop() -> None:
    controller, calls = _make_controller_and_counters()
    controller.state._syncing_axes = True

    controller.on_relayout("img", {"xaxis.range": [1.0, 2.0]})

    assert controller.state.x_range is None
    assert calls["rebuild"] == 0
    assert calls["emit"] == 0
