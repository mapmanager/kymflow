"""Tests for KymAnalysis class."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest

from kymflow.core.kym_file import KymFile
from kymflow.core.kym_analysis import KymAnalysis
from kymflow.core.metadata import AnalysisParameters
from kymflow.core.utils.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)


@pytest.mark.requires_data
def test_kymanalysis_initialization(test_data_dir: Path) -> None:
    """Test that KymAnalysis initializes correctly with a KymFile."""
    if not test_data_dir.exists():
        pytest.skip("Test data directory does not exist")
    
    # Find a test file
    tif_files = list(test_data_dir.glob("*.tif"))
    if not tif_files:
        pytest.skip("No test TIFF files found")
    
    kym_file = KymFile(tif_files[0], load_image=False)
    kym_analysis = kym_file.kymanalysis
    
    assert kym_analysis is not None
    assert kym_analysis.kym_file == kym_file
    assert kym_analysis.num_rois == 0  # Should start empty


def test_kymanalysis_add_roi() -> None:
    """Test adding ROIs to KymAnalysis."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a minimal TIFF file for testing
        test_file = Path(tmpdir) / "test.tif"
        # Create a simple 100x100 test image
        test_image = np.zeros((100, 100), dtype=np.uint16)
        import tifffile
        tifffile.imwrite(test_file, test_image)
        
        kym_file = KymFile(test_file, load_image=False)
        # Set header values (kym_file should provide these, but in tests we need to set them)
        kym_file._header.pixels_per_line = 100
        kym_file._header.num_lines = 100
        kym_analysis = kym_file.kymanalysis
        
        # Add an ROI
        roi = kym_analysis.add_roi(left=10, top=20, right=50, bottom=80, note="Test ROI")
        
        assert roi.roi_id == 1
        assert roi.left == 10
        assert roi.top == 20
        assert roi.right == 50
        assert roi.bottom == 80
        assert roi.note == "Test ROI"
        assert roi.algorithm == ""  # Not analyzed yet
        assert roi.analyzed_at is None
        
        # Verify ROI is in the collection
        assert kym_analysis.num_rois == 1
        assert kym_analysis.get_roi(1) == roi


def test_kymanalysis_roi_coordinates_clamped() -> None:
    """Test that ROI coordinates are clamped to image bounds."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.tif"
        test_image = np.zeros((100, 200), dtype=np.uint16)  # 100 lines, 200 pixels
        import tifffile
        tifffile.imwrite(test_file, test_image)
        
        kym_file = KymFile(test_file, load_image=False)
        # Manually set dimensions since we don't have a header
        kym_file._header.pixels_per_line = 200
        kym_file._header.num_lines = 100
        
        kym_analysis = kym_file.kymanalysis
        
        # Try to add ROI outside bounds
        roi = kym_analysis.add_roi(left=-10, top=-5, right=250, bottom=150)
        
        # Coordinates should be clamped
        assert roi.left >= 0
        assert roi.top >= 0
        assert roi.right <= 200
        assert roi.bottom <= 100


def test_kymanalysis_delete_roi() -> None:
    """Test deleting ROIs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.tif"
        test_image = np.zeros((100, 100), dtype=np.uint16)
        import tifffile
        tifffile.imwrite(test_file, test_image)
        
        kym_file = KymFile(test_file, load_image=False)
        # Set header values (kym_file should provide these, but in tests we need to set them)
        kym_file._header.pixels_per_line = 100
        kym_file._header.num_lines = 100
        kym_analysis = kym_file.kymanalysis
        
        # Add multiple ROIs
        roi1 = kym_analysis.add_roi(10, 10, 50, 50)
        roi2 = kym_analysis.add_roi(60, 60, 90, 90)
        
        assert kym_analysis.num_rois == 2
        
        # Delete one ROI
        kym_analysis.delete_roi(roi1.roi_id)
        
        assert kym_analysis.num_rois == 1
        assert kym_analysis.get_roi(roi1.roi_id) is None
        assert kym_analysis.get_roi(roi2.roi_id) is not None


def test_kymanalysis_edit_roi_coordinates_invalidates_analysis() -> None:
    """Test that editing ROI coordinates invalidates analysis."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.tif"
        test_image = np.zeros((100, 100), dtype=np.uint16)
        import tifffile
        tifffile.imwrite(test_file, test_image)
        
        kym_file = KymFile(test_file, load_image=True)
        kym_file._header.pixels_per_line = 100
        kym_file._header.num_lines = 100
        kym_file._header.seconds_per_line = 0.001
        kym_file._header.um_per_pixel = 1.0
        
        kym_analysis = kym_file.kymanalysis
        
        # Add and analyze ROI
        roi = kym_analysis.add_roi(10, 10, 50, 50)
        kym_analysis.analyze_roi(roi.roi_id, window_size=16, use_multiprocessing=False)
        
        # Verify analysis exists
        assert roi.analyzed_at is not None
        assert roi.algorithm == "mpRadon"
        
        # Edit coordinates - should invalidate analysis
        kym_analysis.edit_roi(roi.roi_id, left=15)
        
        assert roi.left == 15
        assert roi.analyzed_at is None  # Analysis invalidated
        assert roi.algorithm == ""
        assert not kym_analysis.has_analysis(roi.roi_id)


def test_kymanalysis_edit_roi_note_preserves_analysis() -> None:
    """Test that editing ROI note does NOT invalidate analysis."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.tif"
        test_image = np.zeros((100, 100), dtype=np.uint16)
        import tifffile
        tifffile.imwrite(test_file, test_image)
        
        kym_file = KymFile(test_file, load_image=True)
        kym_file._header.pixels_per_line = 100
        kym_file._header.num_lines = 100
        kym_file._header.seconds_per_line = 0.001
        kym_file._header.um_per_pixel = 1.0
        
        kym_analysis = kym_file.kymanalysis
        
        # Add and analyze ROI
        roi = kym_analysis.add_roi(10, 10, 50, 50, note="Original note")
        kym_analysis.analyze_roi(roi.roi_id, window_size=16, use_multiprocessing=False)
        
        original_analyzed_at = roi.analyzed_at
        
        # Edit note - should preserve analysis
        kym_analysis.edit_roi(roi.roi_id, note="Updated note")
        
        assert roi.note == "Updated note"
        assert roi.analyzed_at == original_analyzed_at  # Analysis preserved
        assert roi.algorithm == "mpRadon"
        assert kym_analysis.has_analysis(roi.roi_id)


@pytest.mark.requires_data
def test_kymanalysis_save_and_load_analysis(test_data_dir: Path) -> None:
    """Test saving and loading analysis with ROIs."""
    if not test_data_dir.exists():
        pytest.skip("Test data directory does not exist")
    
    tif_files = list(test_data_dir.glob("*.tif"))
    if not tif_files:
        pytest.skip("No test TIFF files found")
    
    kym_file = KymFile(tif_files[0], load_image=True)
    
    # Set up header if missing
    if not kym_file.pixels_per_line:
        kym_file._header.pixels_per_line = 100
        kym_file._header.num_lines = 100
    if not kym_file._header.seconds_per_line:
        kym_file._header.seconds_per_line = 0.001
    if not kym_file._header.um_per_pixel:
        kym_file._header.um_per_pixel = 1.0
    
    kym_analysis = kym_file.kymanalysis
    
    # Add and analyze ROI
    roi1 = kym_analysis.add_roi(10, 10, 50, 50, note="ROI 1")
    kym_analysis.analyze_roi(roi1.roi_id, window_size=16, use_multiprocessing=False)
    
    # Save analysis
    saved = kym_analysis.save_analysis()
    assert saved is True
    
    # Create new KymFile and KymAnalysis to test loading
    kym_file2 = KymFile(tif_files[0], load_image=False)
    kym_analysis2 = kym_file2.kymanalysis
    
    # Should have loaded ROI
    assert kym_analysis2.num_rois == 1
    loaded_roi = kym_analysis2.get_roi(roi1.roi_id)
    assert loaded_roi is not None
    assert loaded_roi.note == "ROI 1"
    assert loaded_roi.analyzed_at is not None
    assert kym_analysis2.has_analysis(roi1.roi_id)


def test_kymanalysis_multi_roi_analysis() -> None:
    """Test analyzing multiple ROIs and retrieving data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.tif"
        test_image = np.zeros((100, 100), dtype=np.uint16)
        import tifffile
        tifffile.imwrite(test_file, test_image)
        
        kym_file = KymFile(test_file, load_image=True)
        kym_file._header.pixels_per_line = 100
        kym_file._header.num_lines = 100
        kym_file._header.seconds_per_line = 0.001
        kym_file._header.um_per_pixel = 1.0
        
        kym_analysis = kym_file.kymanalysis
        
        # Add and analyze multiple ROIs
        roi1 = kym_analysis.add_roi(10, 10, 30, 30, note="ROI 1")
        roi2 = kym_analysis.add_roi(50, 50, 70, 70, note="ROI 2")
        
        kym_analysis.analyze_roi(roi1.roi_id, window_size=16, use_multiprocessing=False)
        kym_analysis.analyze_roi(roi2.roi_id, window_size=16, use_multiprocessing=False)
        
        # Check that both have analysis
        assert kym_analysis.has_analysis(roi1.roi_id)
        assert kym_analysis.has_analysis(roi2.roi_id)
        
        # Get analysis for specific ROI
        roi1_df = kym_analysis.get_analysis(roi_id=roi1.roi_id)
        assert roi1_df is not None
        assert all(roi1_df['roi_id'] == roi1.roi_id)
        
        # Get all analysis
        all_df = kym_analysis.get_analysis()
        assert all_df is not None
        assert len(all_df[all_df['roi_id'] == roi1.roi_id]) > 0
        assert len(all_df[all_df['roi_id'] == roi2.roi_id]) > 0


def test_kymanalysis_get_analysis_value() -> None:
    """Test getting analysis values for a specific ROI."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.tif"
        test_image = np.zeros((100, 100), dtype=np.uint16)
        import tifffile
        tifffile.imwrite(test_file, test_image)
        
        kym_file = KymFile(test_file, load_image=True)
        kym_file._header.pixels_per_line = 100
        kym_file._header.num_lines = 100
        kym_file._header.seconds_per_line = 0.001
        kym_file._header.um_per_pixel = 1.0
        
        kym_analysis = kym_file.kymanalysis
        
        # Add and analyze ROI
        roi = kym_analysis.add_roi(10, 10, 50, 50)
        kym_analysis.analyze_roi(roi.roi_id, window_size=16, use_multiprocessing=False)
        
        # Get analysis values
        time_values = kym_analysis.get_analysis_value(roi.roi_id, "time")
        velocity_values = kym_analysis.get_analysis_value(roi.roi_id, "velocity")
        
        assert time_values is not None
        assert velocity_values is not None
        assert len(time_values) == len(velocity_values)


def test_kymanalysis_dirty_flag() -> None:
    """Test that dirty flag is set correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.tif"
        test_image = np.zeros((100, 100), dtype=np.uint16)
        import tifffile
        tifffile.imwrite(test_file, test_image)
        
        kym_file = KymFile(test_file, load_image=False)
        # Set header values (kym_file should provide these, but in tests we need to set them)
        kym_file._header.pixels_per_line = 100
        kym_file._header.num_lines = 100
        kym_analysis = kym_file.kymanalysis
        
        # Initially should not be dirty (if no analysis loaded)
        # After adding ROI, should be dirty
        kym_analysis.add_roi(10, 10, 50, 50)
        assert kym_analysis._dirty is True
        
        # After saving, should not be dirty
        kym_analysis.save_analysis()  # May fail if no analysis, but should clear dirty if it succeeds
        # Actually, save_analysis returns False if no analysis, so dirty might stay True
        
        # After analyzing, should be dirty
        kym_file._header.pixels_per_line = 100
        kym_file._header.num_lines = 100
        kym_file._header.seconds_per_line = 0.001
        kym_file._header.um_per_pixel = 1.0
        kym_file.get_img_channel(channel=1)
        
        kym_analysis.analyze_roi(1, window_size=16, use_multiprocessing=False)
        assert kym_analysis._dirty is True
        
        # After saving, should not be dirty
        saved = kym_analysis.save_analysis()
        if saved:
            assert kym_analysis._dirty is False


def test_analysis_parameters_has_same_coordinates() -> None:
    """Test that has_same_coordinates() method works correctly."""
    # Create ROIs with same coordinates but different IDs/notes
    roi1 = AnalysisParameters(roi_id=1, left=10, top=20, right=50, bottom=80, note="ROI 1")
    roi2 = AnalysisParameters(roi_id=2, left=10, top=20, right=50, bottom=80, note="ROI 2")
    
    # Same coordinates should return True
    assert roi1.has_same_coordinates(roi2) is True
    assert roi2.has_same_coordinates(roi1) is True  # Should be symmetric
    
    # Different coordinates should return False
    roi3 = AnalysisParameters(roi_id=1, left=15, top=20, right=50, bottom=80, note="ROI 1")
    assert roi1.has_same_coordinates(roi3) is False
    
    # Test with different top coordinate
    roi4 = AnalysisParameters(roi_id=1, left=10, top=25, right=50, bottom=80, note="ROI 1")
    assert roi1.has_same_coordinates(roi4) is False
    
    # Test with different right coordinate
    roi5 = AnalysisParameters(roi_id=1, left=10, top=20, right=55, bottom=80, note="ROI 1")
    assert roi1.has_same_coordinates(roi5) is False
    
    # Test with different bottom coordinate
    roi6 = AnalysisParameters(roi_id=1, left=10, top=20, right=50, bottom=85, note="ROI 1")
    assert roi1.has_same_coordinates(roi6) is False
    
    # Test that __eq__ still works for full comparison
    assert roi1 != roi2  # Different IDs/notes
    roi1_copy = AnalysisParameters(roi_id=1, left=10, top=20, right=50, bottom=80, note="ROI 1")
    assert roi1 == roi1_copy  # All fields same

