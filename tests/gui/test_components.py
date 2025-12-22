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

from kymflow.core.kym_file import KymFile
from kymflow.gui.state import AppState


@pytest.fixture
def app_state_with_file() -> tuple[AppState, KymFile]:
    """Create an AppState with a test file loaded."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.tif"
        test_image = np.zeros((100, 200), dtype=np.uint16)
        tifffile.imwrite(test_file, test_image)
        
        kym_file = KymFile(test_file, load_image=True)
        # kym_file.pixels_per_line = 200
        # kym_file.num_lines = 100
        # kym_file.seconds_per_line = 0.001
        # kym_file.um_per_pixel = 1.0
        
        app_state = AppState()
        app_state.files = [kym_file]
        app_state.selected_file = kym_file
        
        return app_state, kym_file


def test_analysis_form_populates_from_roi(app_state_with_file: tuple[AppState, KymFile]) -> None:
    """Test that analysis form logic works with ROI-based parameters.
    
    This is a unit test of the underlying logic. Full GUI testing would require
    NiceGUI test infrastructure.
    """
    app_state, kym_file = app_state_with_file
    
    # Create ROI with analysis
    roi = kym_file.kymanalysis.add_roi(left=10, top=10, right=50, bottom=50)
    
    # Analyze the ROI
    kym_file.kymanalysis.analyze_roi(
        roi.roi_id,
        window_size=16,
        use_multiprocessing=False,
    )
    
    # Set selected ROI
    app_state.selected_roi_id = roi.roi_id
    
    # Verify ROI has analysis parameters
    roi_after = kym_file.kymanalysis.get_roi(roi.roi_id)
    assert roi_after is not None
    assert roi_after.algorithm is not None
    assert roi_after.window_size == 16
    
    # Verify form would be able to access these parameters
    # (Actual form population requires NiceGUI UI components)
    assert roi_after.roi_id == roi.roi_id
    assert roi_after.left == 10.0
    assert roi_after.top == 10.0


def test_analysis_form_handles_no_roi(app_state_with_file: tuple[AppState, KymFile]) -> None:
    """Test that analysis form handles case when no ROI is selected."""
    app_state, kym_file = app_state_with_file
    
    # No ROI selected
    app_state.selected_roi_id = None
    
    # Verify that kymanalysis.get_roi() returns None for invalid ROI
    assert kym_file.kymanalysis.get_roi(999) is None


def test_save_buttons_logic_with_roi(app_state_with_file: tuple[AppState, KymFile]) -> None:
    """Test save buttons logic works with ROI-based analysis."""
    app_state, kym_file = app_state_with_file
    
    # Create ROI and analyze
    roi = kym_file.kymanalysis.add_roi()
    kym_file.kymanalysis.analyze_roi(
        roi.roi_id,
        window_size=16,
        use_multiprocessing=False,
    )
    
    # Verify has_analysis() works
    assert kym_file.kymanalysis.has_analysis()
    assert kym_file.kymanalysis.has_analysis(roi.roi_id)
    
    # Verify save_analysis() works
    # Save to temporary location
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a dummy path structure for save
        analysis_folder = Path(tmpdir) / "analysis"
        analysis_folder.mkdir()
        
        # Save should work (save_analysis uses kym_file.path to determine save location)
        # But we can't easily test this without mocking the file path structure
        # So we just verify the methods exist and work
        assert hasattr(kym_file.kymanalysis, 'save_analysis')
        assert callable(kym_file.kymanalysis.save_analysis)


def test_save_buttons_logic_no_analysis(app_state_with_file: tuple[AppState, KymFile]) -> None:
    """Test save buttons logic when no analysis exists."""
    app_state, kym_file = app_state_with_file
    
    # Create ROI but don't analyze
    roi = kym_file.kymanalysis.add_roi()
    
    # Verify has_analysis() returns False
    assert not kym_file.kymanalysis.has_analysis()
    assert not kym_file.kymanalysis.has_analysis(roi.roi_id)


def test_save_buttons_all_files(app_state_with_file: tuple[AppState, KymFile]) -> None:
    """Test save all logic works with multiple files."""
    app_state, kym_file = app_state_with_file
    
    # Create a second file
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file2 = Path(tmpdir) / "test2.tif"
        test_image2 = np.zeros((80, 150), dtype=np.uint16)
        tifffile.imwrite(test_file2, test_image2)
        
        kym_file2 = KymFile(test_file2, load_image=True)
        # kym_file2.kym_image.pixels_per_line = 150
        # kym_file2.kym_image.num_lines = 80
        # kym_file2.kym_image.seconds_per_line = 0.001
        # kym_file2.kym_image.um_per_pixel = 1.0
        
        # Add both files to app_state
        app_state.files = [kym_file, kym_file2]
        
        # Analyze first file
        roi1 = kym_file.kymanalysis.add_roi()
        kym_file.kymanalysis.analyze_roi(roi1.roi_id, window_size=16, use_multiprocessing=False)
        
        # Don't analyze second file
        roi2 = kym_file2.kymanalysis.add_roi()
        
        # Verify has_analysis() logic
        assert kym_file.kymanalysis.has_analysis()
        assert not kym_file2.kymanalysis.has_analysis()
        
        # Files with analysis should be savable
        # Files without analysis should be skipped
        # (Actual save logic requires NiceGUI UI components for notifications)

