from __future__ import annotations

import copy

import pytest

from gui.controllers import AppController
from gui.models import AppState


def _make_controller() -> AppController:
    state = AppState()
    c = AppController(state)
    # Minimal figure dicts with explicit y-range (must be preserved)
    c.fig_img = {"layout": {"xaxis": {"range": [0.0, 10.0]}, "yaxis": {"range": [0.0, 50.0]}}}
    c.fig_line = {"layout": {"xaxis": {"range": [0.0, 10.0]}, "yaxis": {"range": [0.0, 5.0]}}}
    # Provide an image so full-range computation can work.
    import numpy as np
    c.state.img = np.zeros((11, 3), dtype=np.float32)  # 11 timepoints -> max x = 10 * dt
    # Avoid depending on unit resolution internals for this test.
    c.resolve_units = lambda source=None: (1.0, 1.0)  # dt=1s/line
    # Ensure controller thinks figures were built
    c._last_built_data_version = c.state.data_version
    return c


def test_on_relayout_updates_x_only_no_rebuild(monkeypatch: pytest.MonkeyPatch) -> None:
    c = _make_controller()

    # If on_relayout calls rebuild, this test should fail.
    monkeypatch.setattr(c, "_rebuild_figures", lambda: (_ for _ in ()).throw(AssertionError("rebuild called")))

    before_img = copy.deepcopy(c.fig_img)
    before_line = copy.deepcopy(c.fig_line)

    c.on_relayout("img", {"xaxis.range[0]": 2.0, "xaxis.range[1]": 4.0})

    assert c.fig_img is not None and c.fig_line is not None
    assert c.fig_img["layout"]["xaxis"]["range"] == [2.0, 4.0]
    assert c.fig_line["layout"]["xaxis"]["range"] == [2.0, 4.0]

    # y-range must be unchanged
    assert c.fig_img["layout"]["yaxis"]["range"] == before_img["layout"]["yaxis"]["range"]
    assert c.fig_line["layout"]["yaxis"]["range"] == before_line["layout"]["yaxis"]["range"]


def test_on_relayout_autorange_reset_sets_full_x(monkeypatch: pytest.MonkeyPatch) -> None:
    c = _make_controller()
    monkeypatch.setattr(c, "_rebuild_figures", lambda: (_ for _ in ()).throw(AssertionError("rebuild called")))

    c.on_relayout("img", {"xaxis.autorange": True})

    assert c.fig_img is not None and c.fig_line is not None
    assert c.fig_img["layout"]["xaxis"]["range"] == [0.0, 10.0]
    assert c.fig_line["layout"]["xaxis"]["range"] == [0.0, 10.0]
