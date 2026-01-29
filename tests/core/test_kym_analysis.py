"""Tests for KymAnalysis class."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pytest

from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.image_loaders.roi import RoiBounds
from kymflow.core.utils.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)


@pytest.mark.requires_data
def test_kymanalysis_initialization(test_data_dir: Path) -> None:
    """Test that KymAnalysis initializes correctly with a KymImage."""
    if not test_data_dir.exists():
        pytest.skip("Test data directory does not exist")
    
    # Find a test file
    tif_files = list(test_data_dir.glob("*.tif"))
    if not tif_files:
        pytest.skip("No test TIFF files found")
    
    kym_image = KymImage(tif_files[0], load_image=False)
    kym_analysis = kym_image.get_kym_analysis()
    
    assert kym_analysis is not None
    assert kym_analysis.acq_image == kym_image
    assert kym_analysis.num_rois == 0  # Should start empty


def test_kymanalysis_add_roi() -> None:
    """Test adding ROIs to KymAnalysis."""
    # Create a simple 100x100 test image
    test_image = np.zeros((100, 100), dtype=np.uint16)
    
    kym_image = KymImage(img_data=test_image, load_image=False)
    
    # Add an ROI
    bounds = RoiBounds(dim0_start=20, dim0_stop=80, dim1_start=10, dim1_stop=50)
    roi = kym_image.rois.create_roi(bounds=bounds, note="Test ROI")
    
    assert roi.id == 1
    assert roi.bounds.dim0_start == 20
    assert roi.bounds.dim0_stop == 80
    assert roi.bounds.dim1_start == 10
    assert roi.bounds.dim1_stop == 50
    assert roi.note == "Test ROI"
    
    # Verify ROI is in the collection
    assert kym_image.rois.numRois() == 1
    assert kym_image.rois.get(1) == roi


def test_kymanalysis_roi_coordinates_clamped() -> None:
    """Test that ROI coordinates are clamped to image bounds."""
    test_image = np.zeros((100, 200), dtype=np.uint16)  # 100 lines, 200 pixels
    
    kym_image = KymImage(img_data=test_image, load_image=False)
    
    # Try to add ROI outside bounds
    bounds = RoiBounds(dim0_start=-5, dim0_stop=150, dim1_start=-10, dim1_stop=250)
    roi = kym_image.rois.create_roi(bounds=bounds)
    
    # Coordinates should be clamped
    assert roi.bounds.dim0_start >= 0
    assert roi.bounds.dim0_stop <= 100
    assert roi.bounds.dim1_start >= 0
    assert roi.bounds.dim1_stop <= 200


def test_kymanalysis_delete_roi() -> None:
    """Test deleting ROIs."""
    test_image = np.zeros((100, 100), dtype=np.uint16)
    
    kym_image = KymImage(img_data=test_image, load_image=False)
    
    # Add multiple ROIs
    bounds1 = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi1 = kym_image.rois.create_roi(bounds=bounds1)
    bounds2 = RoiBounds(dim0_start=60, dim0_stop=90, dim1_start=60, dim1_stop=90)
    roi2 = kym_image.rois.create_roi(bounds=bounds2)
    
    assert kym_image.rois.numRois() == 2
    
    # Delete one ROI
    kym_image.rois.delete(roi1.id)
    
    assert kym_image.rois.numRois() == 1
    assert kym_image.rois.get(roi1.id) is None
    assert kym_image.rois.get(roi2.id) is not None


def test_kymanalysis_edit_roi_coordinates_invalidates_analysis() -> None:
    """Test that editing ROI coordinates invalidates analysis."""
    test_image = np.zeros((100, 100), dtype=np.uint16)
    
    kym_image = KymImage(img_data=test_image, load_image=True)
    kym_analysis = kym_image.get_kym_analysis()
    
    # Add and analyze ROI
    bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi = kym_image.rois.create_roi(bounds=bounds)
    kym_analysis.analyze_roi(roi.id, window_size=16, use_multiprocessing=False)
    
    # Verify analysis exists
    assert kym_analysis.has_analysis(roi.id)
    meta = kym_analysis.get_analysis_metadata(roi.id)
    assert meta is not None
    assert meta.analyzed_at is not None
    assert meta.algorithm == "mpRadon"
    
    # Edit coordinates - should invalidate analysis
    new_bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=15, dim1_stop=50)
    kym_image.rois.edit_roi(roi.id, bounds=new_bounds)
    
    assert roi.bounds.dim1_start == 15
    # Analysis should be stale after coordinate change
    assert kym_analysis.is_stale(roi.id) is True
    # Metadata may still exist but is stale
    assert not kym_analysis.has_analysis(roi.id) or kym_analysis.is_stale(roi.id)


def test_kymanalysis_edit_roi_note_preserves_analysis() -> None:
    """Test that editing ROI note does NOT invalidate analysis."""
    test_image = np.zeros((100, 100), dtype=np.uint16)
    
    kym_image = KymImage(img_data=test_image, load_image=True)
    kym_analysis = kym_image.get_kym_analysis()
    
    # Add and analyze ROI
    bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi = kym_image.rois.create_roi(bounds=bounds, note="Original note")
    kym_analysis.analyze_roi(roi.id, window_size=16, use_multiprocessing=False)
    
    original_meta = kym_analysis.get_analysis_metadata(roi.id)
    assert original_meta is not None
    original_analyzed_at = original_meta.analyzed_at
    
    # Edit note - should preserve analysis
    kym_image.rois.edit_roi(roi.id, note="Updated note")
    
    assert roi.note == "Updated note"
    # Analysis should still be valid (not stale)
    assert kym_analysis.is_stale(roi.id) is False
    meta = kym_analysis.get_analysis_metadata(roi.id)
    assert meta is not None
    assert meta.analyzed_at == original_analyzed_at  # Analysis preserved
    assert meta.algorithm == "mpRadon"
    assert kym_analysis.has_analysis(roi.id)


@pytest.mark.requires_data
def test_kymanalysis_save_and_load_analysis(test_data_dir: Path) -> None:
    """Test saving and loading analysis with ROIs."""
    if not test_data_dir.exists():
        pytest.skip("Test data directory does not exist")
    
    tif_files = list(test_data_dir.glob("*.tif"))
    if not tif_files:
        pytest.skip("No test TIFF files found")
    
    kym_image = KymImage(tif_files[0], load_image=True)
    
    # Set up header if missing
    # if not kym_file.pixels_per_line:
    #     kym_file.pixels_per_line = 100
    #     kym_file.num_lines = 100
    # if not kym_file.seconds_per_line:
    #     kym_file.seconds_per_line = 0.001
    # if not kym_file.um_per_pixel:
    #     kym_file.um_per_pixel = 1.0
    
    kym_analysis = kym_image.get_kym_analysis()
    
    # Add and analyze ROI
    bounds1 = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi1 = kym_image.rois.create_roi(bounds=bounds1, note="ROI 1")
    kym_analysis.analyze_roi(roi1.id, window_size=16, use_multiprocessing=False)
    
    # Save metadata (ROIs are saved in metadata.json)
    saved_metadata = kym_image.save_metadata()
    assert saved_metadata is True
    
    # Save analysis (analysis metadata is saved in analysis JSON)
    saved_analysis = kym_analysis.save_analysis()
    assert saved_analysis is True
    
    # Create new KymImage to test loading
    kym_image2 = KymImage(tif_files[0], load_image=False)
    
    # Load metadata first (this loads ROIs)
    # IMPORTANT: Load metadata BEFORE accessing kymanalysis, because
    # KymAnalysis.__init__() auto-loads analysis and reconciles to existing ROIs
    loaded_metadata = kym_image2.load_metadata()
    assert loaded_metadata is True
    assert kym_image2.rois.numRois() == 1
    loaded_roi = kym_image2.rois.get(roi1.id)
    assert loaded_roi is not None
    assert loaded_roi.note == "ROI 1"
    
    # Now access kymanalysis - it will auto-load analysis and reconcile to loaded ROIs
    kym_analysis2 = kym_image2.get_kym_analysis()
    
    # Analysis metadata should be loaded (auto-loaded by KymAnalysis.__init__)
    assert kym_analysis2.has_analysis(roi1.id)
    meta = kym_analysis2.get_analysis_metadata(roi1.id)
    assert meta is not None
    assert meta.analyzed_at is not None


def test_kymanalysis_multi_roi_analysis() -> None:
    """Test analyzing multiple ROIs and retrieving data."""
    test_image = np.zeros((100, 100), dtype=np.uint16)
    
    kym_image = KymImage(img_data=test_image, load_image=True)
    kym_analysis = kym_image.get_kym_analysis()
    
    # Add and analyze multiple ROIs
    bounds1 = RoiBounds(dim0_start=10, dim0_stop=30, dim1_start=10, dim1_stop=30)
    roi1 = kym_image.rois.create_roi(bounds=bounds1, note="ROI 1")
    bounds2 = RoiBounds(dim0_start=50, dim0_stop=70, dim1_start=50, dim1_stop=70)
    roi2 = kym_image.rois.create_roi(bounds=bounds2, note="ROI 2")
    
    kym_analysis.analyze_roi(roi1.id, window_size=16, use_multiprocessing=False)
    kym_analysis.analyze_roi(roi2.id, window_size=16, use_multiprocessing=False)
    
    # Check that both have analysis
    assert kym_analysis.has_analysis(roi1.id)
    assert kym_analysis.has_analysis(roi2.id)
    
    # Get analysis for specific ROI
    roi1_df = kym_analysis.get_analysis(roi_id=roi1.id)
    assert roi1_df is not None
    assert all(roi1_df['roi_id'] == roi1.id)
    
    # Get all analysis
    all_df = kym_analysis.get_analysis()
    assert all_df is not None
    assert len(all_df[all_df['roi_id'] == roi1.id]) > 0
    assert len(all_df[all_df['roi_id'] == roi2.id]) > 0


def test_kymanalysis_get_analysis_value() -> None:
    """Test getting analysis values for a specific ROI."""
    test_image = np.zeros((100, 100), dtype=np.uint16)
    
    kym_image = KymImage(img_data=test_image, load_image=True)
    kym_analysis = kym_image.get_kym_analysis()
    
    # Add and analyze ROI
    bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi = kym_image.rois.create_roi(bounds=bounds)
    kym_analysis.analyze_roi(roi.id, window_size=16, use_multiprocessing=False)
    
    # Get analysis values
    time_values = kym_analysis.get_analysis_value(roi.id, "time")
    velocity_values = kym_analysis.get_analysis_value(roi.id, "velocity")
    
    assert time_values is not None
    assert velocity_values is not None
    assert len(time_values) == len(velocity_values)


def test_kymanalysis_dirty_flag() -> None:
    """Test that dirty flag is set correctly."""
    test_image = np.zeros((100, 100), dtype=np.uint16)
    
    kym_image = KymImage(img_data=test_image, load_image=False)
    kym_analysis = kym_image.get_kym_analysis()
    
    # Initially should not be dirty (if no analysis loaded)
    # Adding ROI doesn't set dirty flag (ROIs are separate from analysis)
    bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    kym_image.rois.create_roi(bounds=bounds)
    # Dirty flag is only set when analysis is performed or modified
    
    # After analyzing, should be dirty
    kym_image.get_img_slice(channel=1)
    
    roi = kym_image.rois.get(1)
    assert roi is not None
    kym_analysis.analyze_roi(roi.id, window_size=16, use_multiprocessing=False)
    assert kym_analysis.is_dirty is True
    
    # After saving, should not be dirty
    saved = kym_analysis.save_analysis()
    if saved:
        assert kym_analysis.is_dirty is False


def test_kymanalysis_metadata_only_dirty() -> None:
    """Test that metadata-only changes mark analysis as dirty and can be saved."""
    test_image = np.zeros((100, 100), dtype=np.uint16)
    
    kym_image = KymImage(img_data=test_image, load_image=False)
    kym_analysis = kym_image.get_kym_analysis()
    
    # Initially should not be dirty
    assert kym_analysis.is_dirty is False
    
    # Update experiment metadata - should mark as dirty
    kym_image.update_experiment_metadata(species="mouse", region="cortex")
    assert kym_image.is_metadata_dirty is True
    assert kym_analysis.is_dirty is True
    
    # Update header metadata - should still be dirty
    kym_image.update_header(voxels=[0.001, 0.284])
    assert kym_image.is_metadata_dirty is True
    assert kym_analysis.is_dirty is True
    
    # Save analysis (even without analysis data) - should save metadata and clear dirty
    with TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.tif"
        kym_image._file_path_dict[1] = test_file
        
        saved = kym_analysis.save_analysis()
        assert saved is True
        assert kym_image.is_metadata_dirty is False
        assert kym_analysis.is_dirty is False
        
        # Verify metadata was saved
        metadata_file = test_file.with_suffix('.json')
        assert metadata_file.exists()
        
        import json
        with open(metadata_file, 'r') as f:
            data = json.load(f)
        assert data["experiment_metadata"]["species"] == "mouse"
        assert data["experiment_metadata"]["region"] == "cortex"



