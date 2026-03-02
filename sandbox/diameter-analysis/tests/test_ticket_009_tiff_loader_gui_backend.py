from __future__ import annotations

import numpy as np
import pytest

from diameter_analysis import KymographPayload
from tiff_loader import load_tiff_kymograph


def test_load_tiff_kymograph_rejects_non_2d(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_imread(_path: str) -> np.ndarray:
        return np.zeros((3, 4, 5), dtype=np.uint16)

    monkeypatch.setattr("tifffile.imread", _fake_imread)

    with pytest.raises(ValueError, match="must be 2D"):
        load_tiff_kymograph(
            "fake.tif",
            seconds_per_line=0.001,
            um_per_pixel=0.15,
        )


def test_kymograph_payload_roundtrip_to_dict_from_dict() -> None:
    payload = KymographPayload(
        kymograph=np.arange(12, dtype=np.float32).reshape(3, 4),
        seconds_per_line=0.002,
        um_per_pixel=0.2,
        polarity="bright_on_dark",
        source="tiff",
        path="/tmp/example.tif",
    )

    raw = payload.to_dict()
    loaded = KymographPayload.from_dict(raw)

    assert np.array_equal(loaded.kymograph, payload.kymograph)
    assert loaded.seconds_per_line == payload.seconds_per_line
    assert loaded.um_per_pixel == payload.um_per_pixel
    assert loaded.polarity == payload.polarity
    assert loaded.source == payload.source
    assert loaded.path == payload.path
