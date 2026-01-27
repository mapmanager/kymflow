"""Tests for AppState analysis-related logic in GUI v2."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest
import tifffile

from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.image_loaders.acq_image_list import AcqImageList
from kymflow.core.image_loaders.roi import RoiBounds
from kymflow.gui_v2.state import AppState


@pytest.fixture
def app_state_with_file() -> tuple[AppState, KymImage]:
    """Create an AppState with a test file loaded."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.tif"
        test_image = np.zeros((100, 200), dtype=np.uint16)
        tifffile.imwrite(test_file, test_image)

        kym_file = KymImage(test_file, load_image=True)

        app_state = AppState()
        # Replace default empty list with a test AcqImageList containing our file
        image_list = AcqImageList(path=None, image_cls=KymImage, file_extension=".tif", depth=1)
        image_list.images = [kym_file]
        app_state.files = image_list
        app_state.selected_file = kym_file

        return app_state, kym_file


def test_analysis_form_populates_from_roi(
    app_state_with_file: tuple[AppState, KymImage]
) -> None:
    """Test that analysis form logic works with ROI-based parameters."""
    app_state, kym_file = app_state_with_file

    # Create ROI with analysis
    bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi = kym_file.rois.create_roi(bounds=bounds)

    # Analyze the ROI
    kym_file.get_kym_analysis().analyze_roi(
        roi.id,
        window_size=16,
        use_multiprocessing=False,
    )

    # Set selected ROI
    app_state.selected_roi_id = roi.id

    # Verify ROI exists and has analysis metadata
    roi_after = kym_file.rois.get(roi.id)
    assert roi_after is not None
    kym_analysis = kym_file.get_kym_analysis()
    meta = kym_analysis.get_analysis_metadata(roi.id)
    assert meta is not None
    assert meta.algorithm is not None
    assert meta.window_size == 16

    # Verify form would be able to access these parameters
    # (Actual form population requires NiceGUI UI components)
    assert roi_after.id == roi.id
    assert roi_after.bounds.dim0_start == 10
    assert roi_after.bounds.dim1_start == 10


def test_analysis_form_handles_no_roi(
    app_state_with_file: tuple[AppState, KymImage]
) -> None:
    """Test that analysis form handles case when no ROI is selected."""
    app_state, kym_file = app_state_with_file

    # No ROI selected
    app_state.selected_roi_id = None

    # Verify that rois.get() returns None for invalid ROI
    assert kym_file.rois.get(999) is None


def test_save_buttons_logic_with_roi(
    app_state_with_file: tuple[AppState, KymImage]
) -> None:
    """Test save buttons logic works with ROI-based analysis."""
    app_state, kym_file = app_state_with_file

    # Create ROI and analyze
    bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi = kym_file.rois.create_roi(bounds=bounds)
    kym_file.get_kym_analysis().analyze_roi(
        roi.id,
        window_size=16,
        use_multiprocessing=False,
    )

    # Verify has_analysis() works
    kym_analysis = kym_file.get_kym_analysis()
    assert kym_analysis.has_analysis()
    assert kym_analysis.has_analysis(roi.id)

    # Verify save_analysis() works
    # Save to temporary location
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a dummy path structure for save
        analysis_folder = Path(tmpdir) / "analysis"
        analysis_folder.mkdir()

        # Save should work (save_analysis uses kym_file.path to determine save location)
        # But we can't easily test this without mocking the file path structure
        # So we just verify the methods exist and work
        assert hasattr(kym_analysis, "save_analysis")
        assert callable(kym_analysis.save_analysis)


def test_save_buttons_logic_no_analysis(
    app_state_with_file: tuple[AppState, KymImage]
) -> None:
    """Test save buttons logic when no analysis exists."""
    app_state, kym_file = app_state_with_file

    # Create ROI but don't analyze
    bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi = kym_file.rois.create_roi(bounds=bounds)

    # Verify has_analysis() returns False
    kym_analysis = kym_file.get_kym_analysis()
    assert not kym_analysis.has_analysis()
    assert not kym_analysis.has_analysis(roi.id)


def test_save_buttons_all_files(
    app_state_with_file: tuple[AppState, KymImage]
) -> None:
    """Test save all logic works with multiple files."""
    app_state, kym_file = app_state_with_file

    # Create a second file
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file2 = Path(tmpdir) / "test2.tif"
        test_image2 = np.zeros((80, 150), dtype=np.uint16)
        tifffile.imwrite(test_file2, test_image2)

        kym_file2 = KymImage(test_file2, load_image=True)

        # Add both files to app_state using an AcqImageList
        image_list = AcqImageList(path=None, image_cls=KymImage, file_extension=".tif", depth=1)
        image_list.images = [kym_file, kym_file2]
        app_state.files = image_list

        # Analyze first file
        bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
        roi1 = kym_file.rois.create_roi(bounds=bounds)
        kym_file.get_kym_analysis().analyze_roi(
            roi1.id, window_size=16, use_multiprocessing=False
        )

        # Verify has_analysis() logic
        assert kym_file.get_kym_analysis().has_analysis()
        assert not kym_file2.get_kym_analysis().has_analysis()

        # Files with analysis should be savable
        # Files without analysis should be skipped
        # (Actual save logic requires NiceGUI UI components for notifications)
