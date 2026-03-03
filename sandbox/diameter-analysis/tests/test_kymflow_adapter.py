from __future__ import annotations

import numpy as np
import pytest

from gui import diameter_kymflow_adapter as adapter


def test_require_channel_and_roi_raises_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(adapter, "_facade_get_channel_ids", lambda _acq: [])
    monkeypatch.setattr(adapter, "_facade_get_roi_ids", lambda _acq: [1])
    acq = object()
    with pytest.raises(ValueError, match="Missing channel 1"):
        adapter.require_channel_and_roi(acq, channel=1, roi_id=1)


def test_load_channel_for_calls_facade(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, int] = {}

    def _fake_load_kym_channel(_acq: object, channel: int) -> np.ndarray:
        calls["channel"] = channel
        return np.ones((3, 4), dtype=np.float32)

    monkeypatch.setattr(adapter, "_facade_load_kym_channel", _fake_load_kym_channel)
    out = adapter.load_channel_for(object(), channel=2)
    assert calls["channel"] == 2
    assert out.shape == (3, 4)


def test_defaults_channel_one_and_roi_one_are_applied(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, int] = {}

    def _fake_get_channel_ids(_acq: object) -> list[int]:
        return [1, 2]

    def _fake_get_roi_ids(_acq: object) -> list[int]:
        return [1, 3]

    def _fake_get_roi_pixel_bounds(_acq: object, roi_id: int) -> object:
        calls["roi_id"] = roi_id
        return {"roi_id": roi_id}

    def _fake_load_kym_channel(_acq: object, channel: int) -> np.ndarray:
        calls["channel"] = channel
        return np.zeros((2, 2), dtype=np.uint16)

    monkeypatch.setattr(adapter, "_facade_get_channel_ids", _fake_get_channel_ids)
    monkeypatch.setattr(adapter, "_facade_get_roi_ids", _fake_get_roi_ids)
    monkeypatch.setattr(adapter, "_facade_get_roi_pixel_bounds", _fake_get_roi_pixel_bounds)
    monkeypatch.setattr(adapter, "_facade_load_kym_channel", _fake_load_kym_channel)

    acq = object()
    adapter.require_channel_and_roi(acq)
    _ = adapter.get_roi_pixel_bounds_for(acq)
    _ = adapter.load_channel_for(acq)

    assert calls["roi_id"] == 1
    assert calls["channel"] == 1


def test_list_file_table_kym_images_fails_fast_without_images() -> None:
    class _NoImages:
        pass

    with pytest.raises(TypeError, match=r"Expected klist with \.images"):
        adapter.list_file_table_kym_images(_NoImages())


def test_list_file_table_kym_images_uses_images_contract() -> None:
    class _WithImages:
        def __init__(self) -> None:
            self.images = [object(), object()]

    out = adapter.list_file_table_kym_images(_WithImages())
    assert len(out) == 2
