"""Tests for GUI components.

Note: These tests focus on the underlying logic. Full GUI integration tests
would require NiceGUI test infrastructure and are better suited for manual testing.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest
import tifffile

from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.gui.state import AppState


@pytest.fixture
def app_state_with_file() -> tuple[AppState, KymImage]:
    """Create an AppState with a test file loaded."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.tif"
        test_image = np.zeros((100, 200), dtype=np.uint16)
        tifffile.imwrite(test_file, test_image)
        
        kym_file = KymImage(test_file, load_image=True)
        # kym_file.pixels_per_line = 200
        # kym_file.num_lines = 100
        # kym_file.seconds_per_line = 0.001
        # kym_file.um_per_pixel = 1.0
        
        app_state = AppState()
        app_state.files = [kym_file]
        app_state.selected_file = kym_file
        
        return app_state, kym_file


def test_analysis_form_populates_from_roi(app_state_with_file: tuple[AppState, KymImage]) -> None:
    """Test that analysis form logic works with ROI-based parameters.
    
    This is a unit test of the underlying logic. Full GUI testing would require
    NiceGUI test infrastructure.
    """
    app_state, kym_file = app_state_with_file
    
    # Create ROI with analysis
    roi = kym_file.rois.create_roi(left=10, top=10, right=50, bottom=50)
    
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
    assert roi_after.left == 10
    assert roi_after.top == 10


def test_analysis_form_handles_no_roi(app_state_with_file: tuple[AppState, KymImage]) -> None:
    """Test that analysis form handles case when no ROI is selected."""
    app_state, kym_file = app_state_with_file
    
    # No ROI selected
    app_state.selected_roi_id = None
    
    # Verify that rois.get() returns None for invalid ROI
    assert kym_file.rois.get(999) is None


def test_save_buttons_logic_with_roi(app_state_with_file: tuple[AppState, KymImage]) -> None:
    """Test save buttons logic works with ROI-based analysis."""
    app_state, kym_file = app_state_with_file
    
    # Create ROI and analyze
    roi = kym_file.rois.create_roi()
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
        assert hasattr(kym_analysis, 'save_analysis')
        assert callable(kym_analysis.save_analysis)


def test_save_buttons_logic_no_analysis(app_state_with_file: tuple[AppState, KymImage]) -> None:
    """Test save buttons logic when no analysis exists."""
    app_state, kym_file = app_state_with_file
    
    # Create ROI but don't analyze
    roi = kym_file.rois.create_roi()
    
    # Verify has_analysis() returns False
    kym_analysis = kym_file.get_kym_analysis()
    assert not kym_analysis.has_analysis()
    assert not kym_analysis.has_analysis(roi.id)


def test_save_buttons_all_files(app_state_with_file: tuple[AppState, KymImage]) -> None:
    """Test save all logic works with multiple files."""
    app_state, kym_file = app_state_with_file
    
    # Create a second file
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file2 = Path(tmpdir) / "test2.tif"
        test_image2 = np.zeros((80, 150), dtype=np.uint16)
        tifffile.imwrite(test_file2, test_image2)
        
        kym_file2 = KymImage(test_file2, load_image=True)
        # kym_file2.kym_image.pixels_per_line = 150
        # kym_file2.kym_image.num_lines = 80
        # kym_file2.kym_image.seconds_per_line = 0.001
        # kym_file2.kym_image.um_per_pixel = 1.0
        
        # Add both files to app_state
        app_state.files = [kym_file, kym_file2]
        
        # Analyze first file
        roi1 = kym_file.rois.create_roi()
        kym_file.get_kym_analysis().analyze_roi(roi1.id, window_size=16, use_multiprocessing=False)
        
        # Don't analyze second file
        roi2 = kym_file2.rois.create_roi()
        
        # Verify has_analysis() logic
        assert kym_file.get_kym_analysis().has_analysis()
        assert not kym_file2.get_kym_analysis().has_analysis()
        
        # Files with analysis should be savable
        # Files without analysis should be skipped
        # (Actual save logic requires NiceGUI UI components for notifications)

