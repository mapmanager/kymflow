"""Focused unit tests for RadonAnalysis and RadonEventAnalysis modules."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from kymflow.core.image_loaders.acq_image import AcqImage
from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.image_loaders.radon_analysis import RadonAnalysis
from kymflow.core.image_loaders.radon_event_analysis import RadonEventAnalysis


def test_radon_analysis_get_kym_analysis_none_for_plain_acq_image() -> None:
    """RadonAnalysis.get_kym_analysis returns None when acq_image is not KymImage."""
    img = AcqImage(path=None, img_data=np.zeros((8, 8), dtype=np.uint8))
    radon = RadonAnalysis(img)
    assert radon.get_kym_analysis() is None


def test_radon_analysis_get_kym_analysis_returns_kym_analysis_for_kym_image() -> None:
    """RadonAnalysis.get_kym_analysis delegates to KymImage.get_kym_analysis()."""
    img = KymImage(img_data=np.zeros((8, 8), dtype=np.uint16), load_image=False)
    radon = RadonAnalysis(img)
    assert radon.get_kym_analysis() is img.get_kym_analysis()


def test_radon_event_analysis_empty_state_and_save_skipped_when_clean(tmp_path: Path) -> None:
    """Fresh RadonEventAnalysis has no keys, is not dirty, save_analysis is False."""
    tif_path = tmp_path / "kym.tif"
    tif_path.touch()
    img = KymImage(
        path=tif_path,
        img_data=np.zeros((24, 24), dtype=np.uint16),
        load_image=False,
    )
    ka = img.get_kym_analysis()
    events = ka.get_analysis_object("RadonEventAnalysis")
    assert isinstance(events, RadonEventAnalysis)
    assert events.iter_roi_channel_keys() == []
    assert events.is_dirty is False
    folder = ka._get_analysis_folder_path()
    folder.mkdir(parents=True, exist_ok=True)
    assert events.save_analysis(folder) is False


def test_radon_event_clear_missing_roi_channel_does_not_mark_dirty() -> None:
    """clear_analysis_for_roi_channel on missing key leaves is_dirty False."""
    img = KymImage(img_data=np.zeros((16, 16), dtype=np.uint16), load_image=False)
    ka = img.get_kym_analysis()
    events = ka.get_analysis_object("RadonEventAnalysis")
    assert events.is_dirty is False
    events.clear_analysis_for_roi_channel(roi_id=999, channel=1)
    assert events.is_dirty is False
