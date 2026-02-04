"""Tests for KymAnalysis class."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd
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
    
    # Verify accepted field is loaded (defaults to True if not in JSON)
    assert kym_analysis2.get_accepted() is True


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


def test_kymanalysis_velocity_event_add() -> None:
    """Test adding velocity events."""
    test_image = np.zeros((100, 100), dtype=np.uint16)
    kym_image = KymImage(img_data=test_image, load_image=False)
    kym_image.update_header(shape=(100, 100), ndim=2, voxels=[0.001, 0.284])
    
    kym_analysis = kym_image.get_kym_analysis()
    
    # Add ROI
    bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi = kym_image.rois.create_roi(bounds=bounds)
    
    # Add velocity event
    event_id = kym_analysis.add_velocity_event(roi.id, t_start=0.5, t_end=1.0)
    assert event_id is not None
    assert isinstance(event_id, str)  # Should be UUID
    
    # Verify event was added
    events = kym_analysis.get_velocity_events(roi.id)
    assert events is not None
    assert len(events) == 1
    assert events[0].t_start == 0.5
    assert events[0].t_end == 1.0
    assert events[0].event_type == "User Added"
    
    # Add another event without end time
    event_id2 = kym_analysis.add_velocity_event(roi.id, t_start=2.0, t_end=None)
    assert event_id2 is not None
    events = kym_analysis.get_velocity_events(roi.id)
    assert len(events) == 2
    assert events[1].t_end is None


def test_kymanalysis_velocity_event_delete() -> None:
    """Test deleting velocity events."""
    test_image = np.zeros((100, 100), dtype=np.uint16)
    kym_image = KymImage(img_data=test_image, load_image=False)
    kym_image.update_header(shape=(100, 100), ndim=2, voxels=[0.001, 0.284])
    
    kym_analysis = kym_image.get_kym_analysis()
    
    bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi = kym_image.rois.create_roi(bounds=bounds)
    
    # Add two events
    event_id1 = kym_analysis.add_velocity_event(roi.id, t_start=0.5, t_end=1.0)
    event_id2 = kym_analysis.add_velocity_event(roi.id, t_start=2.0, t_end=3.0)
    
    assert kym_analysis.num_velocity_events(roi.id) == 2
    
    # Delete first event
    deleted = kym_analysis.delete_velocity_event(event_id1)
    assert deleted is True
    assert kym_analysis.num_velocity_events(roi.id) == 1
    
    # Try to delete non-existent event
    deleted = kym_analysis.delete_velocity_event("non-existent-uuid")
    assert deleted is False


def test_kymanalysis_velocity_event_update_field() -> None:
    """Test updating velocity event fields."""
    test_image = np.zeros((100, 100), dtype=np.uint16)
    kym_image = KymImage(img_data=test_image, load_image=False)
    kym_image.update_header(shape=(100, 100), ndim=2, voxels=[0.001, 0.284])
    
    kym_analysis = kym_image.get_kym_analysis()
    
    bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi = kym_image.rois.create_roi(bounds=bounds)
    
    # Add event
    event_id = kym_analysis.add_velocity_event(roi.id, t_start=0.5, t_end=1.0)
    
    # Update user_type
    from kymflow.core.analysis.velocity_events.velocity_events import UserType
    updated_id = kym_analysis.update_velocity_event_field(event_id, "user_type", UserType.TRUE_STALL.value)
    assert updated_id == event_id  # UUID doesn't change
    
    events = kym_analysis.get_velocity_events(roi.id)
    assert events[0].user_type == UserType.TRUE_STALL
    
    # Update t_start
    updated_id = kym_analysis.update_velocity_event_field(event_id, "t_start", 0.6)
    assert updated_id == event_id
    events = kym_analysis.get_velocity_events(roi.id)
    assert events[0].t_start == 0.6
    
    # Update t_end
    updated_id = kym_analysis.update_velocity_event_field(event_id, "t_end", 1.1)
    assert updated_id == event_id
    events = kym_analysis.get_velocity_events(roi.id)
    assert events[0].t_end == 1.1


def test_kymanalysis_velocity_event_update_range() -> None:
    """Test updating velocity event time range."""
    test_image = np.zeros((100, 100), dtype=np.uint16)
    kym_image = KymImage(img_data=test_image, load_image=False)
    kym_image.update_header(shape=(100, 100), ndim=2, voxels=[0.001, 0.284])
    
    kym_analysis = kym_image.get_kym_analysis()
    
    bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi = kym_image.rois.create_roi(bounds=bounds)
    
    # Add event
    event_id = kym_analysis.add_velocity_event(roi.id, t_start=0.5, t_end=1.0)
    
    # Update both t_start and t_end atomically
    updated_id = kym_analysis.update_velocity_event_range(event_id, t_start=0.6, t_end=1.1)
    assert updated_id == event_id
    
    events = kym_analysis.get_velocity_events(roi.id)
    assert events[0].t_start == 0.6
    assert events[0].t_end == 1.1


def test_kymanalysis_velocity_event_get_report() -> None:
    """Test getting velocity report."""
    test_image = np.zeros((100, 100), dtype=np.uint16)
    kym_image = KymImage(img_data=test_image, load_image=False)
    kym_image.update_header(shape=(100, 100), ndim=2, voxels=[0.001, 0.284])
    
    kym_analysis = kym_image.get_kym_analysis()
    
    bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi = kym_image.rois.create_roi(bounds=bounds)
    
    # Add event
    kym_analysis.add_velocity_event(roi.id, t_start=0.5, t_end=1.0)
    
    # Get report for specific ROI
    report = kym_analysis.get_velocity_report(roi_id=roi.id)
    assert len(report) == 1
    assert report[0]["roi_id"] == roi.id
    assert report[0]["event_id"] is not None
    assert report[0]["t_start"] == 0.5
    assert report[0]["t_end"] == 1.0
    
    # Get report for all ROIs
    report_all = kym_analysis.get_velocity_report(roi_id=None)
    assert len(report_all) == 1


def test_kymanalysis_velocity_event_remove() -> None:
    """Test removing velocity events by type."""
    test_image = np.zeros((100, 100), dtype=np.uint16)
    kym_image = KymImage(img_data=test_image, load_image=False)
    kym_image.update_header(shape=(100, 100), ndim=2, voxels=[0.001, 0.284])
    
    kym_analysis = kym_image.get_kym_analysis()
    
    bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi = kym_image.rois.create_roi(bounds=bounds)
    
    # Add user-added event
    kym_analysis.add_velocity_event(roi.id, t_start=0.5, t_end=1.0)
    
    # Simulate auto-detected event (would normally come from run_velocity_event_analysis)
    from kymflow.core.analysis.velocity_events.velocity_events import VelocityEvent, UserType
    auto_event = VelocityEvent(
        event_type="baseline_drop",
        i_start=100,
        t_start=1.0,
        i_end=200,
        t_end=2.0,
        user_type=UserType.UNREVIEWED,
    )
    if roi.id not in kym_analysis._velocity_events:
        kym_analysis._velocity_events[roi.id] = []
    kym_analysis._velocity_events[roi.id].append(auto_event)
    
    assert kym_analysis.num_velocity_events(roi.id) == 2
    
    # Remove only auto-detected events (keeps user-added)
    kym_analysis.remove_velocity_event(roi.id, "auto_detected")
    assert kym_analysis.num_velocity_events(roi.id) == 1  # User-added event remains
    
    # Remove all events
    kym_analysis.remove_velocity_event(roi.id, "_remove_all")
    assert kym_analysis.num_velocity_events(roi.id) == 0


def test_kymanalysis_total_num_velocity_events() -> None:
    """Test total_num_velocity_events() across all ROIs."""
    test_image = np.zeros((100, 100), dtype=np.uint16)
    kym_image = KymImage(img_data=test_image, load_image=False)
    kym_image.update_header(shape=(100, 100), ndim=2, voxels=[0.001, 0.284])
    
    kym_analysis = kym_image.get_kym_analysis()
    
    # Add two ROIs
    bounds1 = RoiBounds(dim0_start=10, dim0_stop=30, dim1_start=10, dim1_stop=30)
    roi1 = kym_image.rois.create_roi(bounds=bounds1)
    bounds2 = RoiBounds(dim0_start=50, dim0_stop=70, dim1_start=50, dim1_stop=70)
    roi2 = kym_image.rois.create_roi(bounds=bounds2)
    
    # Add events to both ROIs
    kym_analysis.add_velocity_event(roi1.id, t_start=0.5, t_end=1.0)
    kym_analysis.add_velocity_event(roi1.id, t_start=2.0, t_end=3.0)
    kym_analysis.add_velocity_event(roi2.id, t_start=1.0, t_end=2.0)
    
    assert kym_analysis.total_num_velocity_events() == 3
    assert kym_analysis.num_velocity_events(roi1.id) == 2
    assert kym_analysis.num_velocity_events(roi2.id) == 1


def test_kymanalysis_has_v0_flow_analysis() -> None:
    """Test has_v0_flow_analysis() method."""
    test_image = np.zeros((100, 100), dtype=np.uint16)
    kym_image = KymImage(img_data=test_image, load_image=False)
    kym_image.update_header(shape=(100, 100), ndim=2, voxels=[0.001, 0.284])
    
    kym_analysis = kym_image.get_kym_analysis()
    
    bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi = kym_image.rois.create_roi(bounds=bounds)
    
    # Initially should be False
    assert kym_analysis.has_v0_flow_analysis(roi.id) is False
    
    # Analyze with regular algorithm
    kym_analysis.analyze_roi(roi.id, window_size=16, use_multiprocessing=False)
    assert kym_analysis.has_v0_flow_analysis(roi.id) is False
    
    # Manually set v0 algorithm (simulating import)
    from kymflow.core.image_loaders.kym_analysis import RoiAnalysisMetadata
    from datetime import datetime, timezone
    kym_analysis._analysis_metadata[roi.id] = RoiAnalysisMetadata(
        roi_id=roi.id,
        algorithm="mpRadon_v0",
        window_size=16,
        analyzed_at=datetime.now(timezone.utc).isoformat(),
        roi_revision_at_analysis=roi.revision,
    )
    assert kym_analysis.has_v0_flow_analysis(roi.id) is True


def test_kymanalysis_accepted_default_value() -> None:
    """Test that accepted defaults to True for new KymAnalysis instances."""
    test_image = np.zeros((100, 100), dtype=np.uint16)
    kym_image = KymImage(img_data=test_image, load_image=False)
    kym_analysis = kym_image.get_kym_analysis()
    
    # Default value should be True
    assert kym_analysis.get_accepted() is True


def test_kymanalysis_accepted_get_set() -> None:
    """Test get_accepted() and set_accepted() methods."""
    test_image = np.zeros((100, 100), dtype=np.uint16)
    kym_image = KymImage(img_data=test_image, load_image=False)
    kym_analysis = kym_image.get_kym_analysis()
    
    # Initially True
    assert kym_analysis.get_accepted() is True
    
    # Set to False
    kym_analysis.set_accepted(False)
    assert kym_analysis.get_accepted() is False
    assert kym_analysis.is_dirty is True
    
    # Set back to True
    kym_analysis.set_accepted(True)
    assert kym_analysis.get_accepted() is True
    assert kym_analysis.is_dirty is True


def test_kymanalysis_accepted_save_and_load() -> None:
    """Test that accepted is saved and loaded from JSON."""
    test_image = np.zeros((100, 100), dtype=np.uint16)
    kym_image = KymImage(img_data=test_image, load_image=False)
    kym_analysis = kym_image.get_kym_analysis()
    
    # Set accepted to False
    kym_analysis.set_accepted(False)
    assert kym_analysis.get_accepted() is False
    
    # Save analysis
    with TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.tif"
        kym_image._file_path_dict[1] = test_file
        
        saved = kym_analysis.save_analysis()
        assert saved is True
        
        # Verify accepted is in JSON
        import json
        json_path = kym_analysis._get_save_paths()[1]
        assert json_path.exists()
        
        with open(json_path, 'r') as f:
            data = json.load(f)
        assert data["accepted"] is False
        
        # Create new instance and load
        kym_image2 = KymImage(test_file, load_image=False)
        kym_analysis2 = kym_image2.get_kym_analysis()
        
        # Should load False from JSON
        assert kym_analysis2.get_accepted() is False


def test_kymanalysis_accepted_load_defaults_to_true() -> None:
    """Test that loading old JSON without accepted field defaults to True."""
    test_image = np.zeros((100, 100), dtype=np.uint16)
    kym_image = KymImage(img_data=test_image, load_image=False)
    kym_analysis = kym_image.get_kym_analysis()
    
    # Need to make it dirty to save (set accepted or add some metadata change)
    # Since we want to test default value, we'll save with accepted=True first
    kym_analysis.set_accepted(True)  # This makes it dirty
    
    # Save analysis (will include accepted=True)
    with TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.tif"
        kym_image._file_path_dict[1] = test_file
        
        saved = kym_analysis.save_analysis()
        assert saved is True
        
        # Manually remove accepted from JSON to simulate old format
        import json
        json_path = kym_analysis._get_save_paths()[1]
        with open(json_path, 'r') as f:
            data = json.load(f)
        del data["accepted"]
        with open(json_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        # Create new instance and load
        kym_image2 = KymImage(test_file, load_image=False)
        kym_analysis2 = kym_image2.get_kym_analysis()
        
        # Should default to True when missing from JSON
        assert kym_analysis2.get_accepted() is True


def test_kymanalysis_round_trip_with_accepted_edit() -> None:
    """Test complete round-trip: analyze → save → load → edit accepted → save → load.
    
    This test verifies that:
    1. CSV and JSON are saved separately (CSV when df exists, JSON when dirty)
    2. Editing accepted after analysis only updates JSON (not CSV)
    3. All data persists correctly through multiple save/load cycles
    """
    test_image = np.zeros((100, 100), dtype=np.uint16)
    kym_image = KymImage(img_data=test_image, load_image=True)
    kym_analysis = kym_image.get_kym_analysis()
    
    # Add and analyze ROI (creates CSV data)
    bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi = kym_image.rois.create_roi(bounds=bounds, note="Test ROI")
    kym_analysis.analyze_roi(roi.id, window_size=16, use_multiprocessing=False)
    
    # Verify analysis exists
    assert kym_analysis.has_analysis(roi.id)
    assert kym_analysis.get_accepted() is True  # Default
    assert kym_analysis.is_dirty is True
    
    # Get original analysis data
    original_df = kym_analysis.get_analysis(roi.id)
    assert original_df is not None
    assert len(original_df) > 0
    
    with TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.tif"
        kym_image._file_path_dict[1] = test_file
        
        # First save: should save both CSV and JSON
        saved = kym_analysis.save_analysis()
        assert saved is True
        assert kym_analysis.is_dirty is False
        
        csv_path, json_path = kym_analysis._get_save_paths()
        assert csv_path.exists(), "CSV should be saved when df exists"
        assert json_path.exists(), "JSON should be saved when dirty"
        
        # Verify JSON contains accepted=True
        import json
        with open(json_path, 'r') as f:
            json_data = json.load(f)
        assert json_data["accepted"] is True
        
        # Load and verify round-trip
        kym_image2 = KymImage(test_file, load_image=False)
        kym_image2.load_metadata()  # Load ROIs first
        kym_analysis2 = kym_image2.get_kym_analysis()
        
        assert kym_analysis2.has_analysis(roi.id)
        assert kym_analysis2.get_accepted() is True
        loaded_df = kym_analysis2.get_analysis(roi.id)
        assert loaded_df is not None
        assert len(loaded_df) == len(original_df)
        
        # Now edit accepted (should only update JSON, not CSV)
        kym_analysis2.set_accepted(False)
        assert kym_analysis2.get_accepted() is False
        assert kym_analysis2.is_dirty is True
        
        # Save again - should only update JSON (CSV already exists and hasn't changed)
        saved2 = kym_analysis2.save_analysis()
        assert saved2 is True
        assert kym_analysis2.is_dirty is False
        
        # Verify CSV still exists and is unchanged
        assert csv_path.exists(), "CSV should still exist after editing accepted"
        csv_path2, json_path2 = kym_analysis2._get_save_paths()
        assert csv_path2 == csv_path  # Same path
        
        # Verify JSON was updated with accepted=False
        with open(json_path2, 'r') as f:
            json_data2 = json.load(f)
        assert json_data2["accepted"] is False
        # Verify other data is still there
        assert "analysis_metadata" in json_data2
        assert "velocity_events" in json_data2
        
        # Final round-trip: load again and verify everything persisted
        kym_image3 = KymImage(test_file, load_image=False)
        kym_image3.load_metadata()
        kym_analysis3 = kym_image3.get_kym_analysis()
        
        assert kym_analysis3.has_analysis(roi.id)
        assert kym_analysis3.get_accepted() is False, "accepted=False should persist"
        
        # Verify CSV data is still intact
        final_df = kym_analysis3.get_analysis(roi.id)
        assert final_df is not None
        assert len(final_df) == len(original_df), "CSV data should be unchanged"
        
        # Verify analysis metadata is still there
        meta = kym_analysis3.get_analysis_metadata(roi.id)
        assert meta is not None
        assert meta.algorithm == "mpRadon"


def test_kymanalysis_save_json_only_when_dirty_no_df() -> None:
    """Test that JSON can be saved even when there's no CSV data (e.g., only accepted changed)."""
    test_image = np.zeros((100, 100), dtype=np.uint16)
    kym_image = KymImage(img_data=test_image, load_image=False)
    kym_analysis = kym_image.get_kym_analysis()
    
    # No analysis data, but we can still save accepted
    assert kym_analysis._df is None or len(kym_analysis._df) == 0
    kym_analysis.set_accepted(False)
    assert kym_analysis.is_dirty is True
    
    with TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.tif"
        kym_image._file_path_dict[1] = test_file
        
        # Save - should save JSON even without CSV
        saved = kym_analysis.save_analysis()
        assert saved is True
        
        csv_path, json_path = kym_analysis._get_save_paths()
        # CSV should not exist (no df data)
        assert not csv_path.exists() or csv_path.stat().st_size == 0
        # JSON should exist (dirty flag was set)
        assert json_path.exists()
        
        # Verify JSON contains accepted
        import json
        with open(json_path, 'r') as f:
            json_data = json.load(f)
        assert json_data["accepted"] is False


def test_kymanalysis_accepted_in_getRowDict() -> None:
    """Test that accepted is included in KymImage.getRowDict()."""
    test_image = np.zeros((100, 100), dtype=np.uint16)
    kym_image = KymImage(img_data=test_image, load_image=False)
    kym_analysis = kym_image.get_kym_analysis()
    
    # Default should be True
    row_dict = kym_image.getRowDict()
    assert "accepted" in row_dict
    assert row_dict["accepted"] is True
    
    # Set to False and verify it's in row dict
    kym_analysis.set_accepted(False)
    row_dict = kym_image.getRowDict()
    assert row_dict["accepted"] is False
    
    # Set back to True
    kym_analysis.set_accepted(True)
    row_dict = kym_image.getRowDict()
    assert row_dict["accepted"] is True


def test_kymanalysis_create_empty_velocity_df() -> None:
    """Test that _create_empty_velocity_df() creates DataFrame with correct columns and dtypes."""
    test_image = np.zeros((100, 100), dtype=np.uint16)
    kym_image = KymImage(img_data=test_image, load_image=False)
    kym_analysis = kym_image.get_kym_analysis()
    
    # Create empty DataFrame
    empty_df = kym_analysis._create_empty_velocity_df()
    
    # Verify it's a DataFrame
    assert isinstance(empty_df, pd.DataFrame)
    
    # Verify it has 0 rows
    assert len(empty_df) == 0
    
    # Verify all expected columns exist
    expected_columns = [
        "roi_id", "channel", "time", "velocity", "parentFolder", "file",
        "algorithm", "delx", "delt", "numLines", "pntsPerLine",
        "cleanVelocity", "absVelocity"
    ]
    assert list(empty_df.columns) == expected_columns
    
    # Verify dtypes
    assert empty_df["roi_id"].dtype == "int64"
    assert empty_df["channel"].dtype == "int64"
    assert empty_df["time"].dtype == "float64"
    assert empty_df["velocity"].dtype == "float64"
    assert empty_df["parentFolder"].dtype == "string" or empty_df["parentFolder"].dtype == "object"
    assert empty_df["file"].dtype == "string" or empty_df["file"].dtype == "object"
    assert empty_df["algorithm"].dtype == "string" or empty_df["algorithm"].dtype == "object"
    assert empty_df["delx"].dtype == "float64"
    assert empty_df["delt"].dtype == "float64"
    assert empty_df["numLines"].dtype == "int64"
    assert empty_df["pntsPerLine"].dtype == "int64"
    assert empty_df["cleanVelocity"].dtype == "float64"
    assert empty_df["absVelocity"].dtype == "float64"


def test_kymanalysis_empty_df_columns_match_schema() -> None:
    """Test that empty DataFrame columns exactly match _make_velocity_df() output."""
    test_image = np.zeros((100, 100), dtype=np.uint16)
    kym_image = KymImage(img_data=test_image, load_image=True)
    kym_analysis = kym_image.get_kym_analysis()
    
    # Create a sample ROI and analyze to get actual schema
    bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi = kym_image.rois.create_roi(bounds=bounds, note="Test ROI")
    kym_analysis.analyze_roi(roi.id, window_size=16, use_multiprocessing=False)
    
    # Get actual DataFrame from analysis
    actual_df = kym_analysis.get_analysis(roi.id)
    assert actual_df is not None
    
    # Create empty DataFrame
    empty_df = kym_analysis._create_empty_velocity_df()
    
    # Verify columns match exactly (order and names)
    assert list(empty_df.columns) == list(actual_df.columns)


def test_kymanalysis_empty_df_has_correct_dtypes() -> None:
    """Test that empty DataFrame has correct dtypes for all columns."""
    test_image = np.zeros((100, 100), dtype=np.uint16)
    kym_image = KymImage(img_data=test_image, load_image=False)
    kym_analysis = kym_image.get_kym_analysis()
    
    empty_df = kym_analysis._create_empty_velocity_df()
    
    # Verify integer columns
    assert empty_df["roi_id"].dtype == "int64"
    assert empty_df["channel"].dtype == "int64"
    assert empty_df["numLines"].dtype == "int64"
    assert empty_df["pntsPerLine"].dtype == "int64"
    
    # Verify float columns
    assert empty_df["time"].dtype == "float64"
    assert empty_df["velocity"].dtype == "float64"
    assert empty_df["delx"].dtype == "float64"
    assert empty_df["delt"].dtype == "float64"
    assert empty_df["cleanVelocity"].dtype == "float64"
    assert empty_df["absVelocity"].dtype == "float64"
    
    # Verify string columns (pandas may use 'object' or 'string' dtype)
    assert empty_df["parentFolder"].dtype in ["string", "object"]
    assert empty_df["file"].dtype in ["string", "object"]
    assert empty_df["algorithm"].dtype in ["string", "object"]


def test_kymanalysis_no_analysis_df_stays_none() -> None:
    """Test that _df remains None if no analysis ever run."""
    test_image = np.zeros((100, 100), dtype=np.uint16)
    kym_image = KymImage(img_data=test_image, load_image=False)
    kym_analysis = kym_image.get_kym_analysis()
    
    # Add ROI but don't analyze
    bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    kym_image.rois.create_roi(bounds=bounds, note="Test ROI")
    
    # Verify _df is still None (should not create empty DataFrame)
    assert kym_analysis._df is None


def test_kymanalysis_empty_df_after_delete_all_rois() -> None:
    """Test that deleting all ROIs creates empty DataFrame with correct columns."""
    test_image = np.zeros((100, 100), dtype=np.uint16)
    kym_image = KymImage(img_data=test_image, load_image=True)
    kym_analysis = kym_image.get_kym_analysis()
    
    # Add and analyze ROI
    bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi = kym_image.rois.create_roi(bounds=bounds, note="Test ROI")
    kym_analysis.analyze_roi(roi.id, window_size=16, use_multiprocessing=False)
    
    # Verify analysis exists
    assert kym_analysis.has_analysis(roi.id)
    assert kym_analysis._df is not None
    assert len(kym_analysis._df) > 0
    
    # Delete the ROI (this should invalidate analysis)
    kym_image.rois.delete(roi.id)
    kym_analysis.invalidate(roi.id)
    
    # Verify _df is now empty DataFrame (not None) with correct columns
    assert kym_analysis._df is not None
    assert len(kym_analysis._df) == 0
    
    # Verify it has correct columns
    expected_columns = [
        "roi_id", "channel", "time", "velocity", "parentFolder", "file",
        "algorithm", "delx", "delt", "numLines", "pntsPerLine",
        "cleanVelocity", "absVelocity"
    ]
    assert list(kym_analysis._df.columns) == expected_columns


def test_kymanalysis_remove_roi_data_preserves_other_rois() -> None:
    """Test that removing one ROI doesn't affect other ROIs' data."""
    test_image = np.zeros((100, 100), dtype=np.uint16)
    kym_image = KymImage(img_data=test_image, load_image=True)
    kym_analysis = kym_image.get_kym_analysis()
    
    # Create and analyze two ROIs
    bounds1 = RoiBounds(dim0_start=10, dim0_stop=30, dim1_start=10, dim1_stop=30)
    roi1 = kym_image.rois.create_roi(bounds=bounds1, note="ROI 1")
    kym_analysis.analyze_roi(roi1.id, window_size=16, use_multiprocessing=False)
    
    bounds2 = RoiBounds(dim0_start=50, dim0_stop=70, dim1_start=50, dim1_stop=70)
    roi2 = kym_image.rois.create_roi(bounds=bounds2, note="ROI 2")
    kym_analysis.analyze_roi(roi2.id, window_size=16, use_multiprocessing=False)
    
    # Verify both ROIs have analysis
    assert kym_analysis.has_analysis(roi1.id)
    assert kym_analysis.has_analysis(roi2.id)
    
    # Get data for both ROIs
    df1_before = kym_analysis.get_analysis(roi1.id)
    df2_before = kym_analysis.get_analysis(roi2.id)
    assert df1_before is not None
    assert df2_before is not None
    assert len(df1_before) > 0
    assert len(df2_before) > 0
    
    # Remove ROI1 data
    kym_analysis._remove_roi_data_from_df(roi1.id)
    
    # Verify ROI2 data is still intact
    df2_after = kym_analysis.get_analysis(roi2.id)
    assert df2_after is not None
    assert len(df2_after) == len(df2_before)
    assert list(df2_after["roi_id"].unique()) == [roi2.id]
    
    # Verify ROI1 data is gone
    df1_after = kym_analysis.get_analysis(roi1.id)
    assert df1_after is None or len(df1_after) == 0


def test_kymanalysis_save_empty_df() -> None:
    """Test that saving empty DataFrame (0 rows) writes CSV with correct columns."""
    test_image = np.zeros((100, 100), dtype=np.uint16)
    kym_image = KymImage(img_data=test_image, load_image=True)
    kym_analysis = kym_image.get_kym_analysis()
    
    # Add and analyze ROI, then delete it to get empty DataFrame
    bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi = kym_image.rois.create_roi(bounds=bounds, note="Test ROI")
    kym_analysis.analyze_roi(roi.id, window_size=16, use_multiprocessing=False)
    
    # Delete ROI to create empty DataFrame
    kym_image.rois.delete(roi.id)
    kym_analysis.invalidate(roi.id)
    
    # Verify we have empty DataFrame
    assert kym_analysis._df is not None
    assert len(kym_analysis._df) == 0
    assert kym_analysis.is_dirty is True
    
    # Save analysis
    with TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.tif"
        kym_image._file_path_dict[1] = test_file
        
        saved = kym_analysis.save_analysis()
        assert saved is True
        
        # Verify CSV file exists
        csv_path, json_path = kym_analysis._get_save_paths()
        assert csv_path.exists(), "CSV file should exist even when empty"
        
        # Verify CSV has header row
        with open(csv_path, 'r') as f:
            lines = f.readlines()
            assert len(lines) > 0, "CSV should have at least header row"
            header = lines[0].strip()
            expected_columns = [
                "roi_id", "channel", "time", "velocity", "parentFolder", "file",
                "algorithm", "delx", "delt", "numLines", "pntsPerLine",
                "cleanVelocity", "absVelocity"
            ]
            for col in expected_columns:
                assert col in header, f"Header should contain column: {col}"
        
        # Verify we can read it back as empty DataFrame
        loaded_df = pd.read_csv(csv_path)
        assert len(loaded_df) == 0
        assert list(loaded_df.columns) == expected_columns


def test_kymanalysis_save_empty_csv_has_header() -> None:
    """Test that empty CSV has header row with all column names."""
    test_image = np.zeros((100, 100), dtype=np.uint16)
    kym_image = KymImage(img_data=test_image, load_image=True)
    kym_analysis = kym_image.get_kym_analysis()
    
    # Create empty DataFrame by analyzing then deleting
    bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi = kym_image.rois.create_roi(bounds=bounds, note="Test ROI")
    kym_analysis.analyze_roi(roi.id, window_size=16, use_multiprocessing=False)
    kym_image.rois.delete(roi.id)
    kym_analysis.invalidate(roi.id)
    
    with TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.tif"
        kym_image._file_path_dict[1] = test_file
        
        kym_analysis.save_analysis()
        
        csv_path, _ = kym_analysis._get_save_paths()
        assert csv_path.exists()
        
        # Read CSV file and check header
        with open(csv_path, 'r') as f:
            first_line = f.readline().strip()
            expected_columns = [
                "roi_id", "channel", "time", "velocity", "parentFolder", "file",
                "algorithm", "delx", "delt", "numLines", "pntsPerLine",
                "cleanVelocity", "absVelocity"
            ]
            header_cols = first_line.split(',')
            assert len(header_cols) == len(expected_columns)
            for col in expected_columns:
                assert col in header_cols, f"Header missing column: {col}"


def test_kymanalysis_save_empty_csv_file_exists() -> None:
    """Test that empty CSV file is created and exists on disk after save."""
    test_image = np.zeros((100, 100), dtype=np.uint16)
    kym_image = KymImage(img_data=test_image, load_image=True)
    kym_analysis = kym_image.get_kym_analysis()
    
    # Create empty DataFrame
    bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi = kym_image.rois.create_roi(bounds=bounds, note="Test ROI")
    kym_analysis.analyze_roi(roi.id, window_size=16, use_multiprocessing=False)
    kym_image.rois.delete(roi.id)
    kym_analysis.invalidate(roi.id)
    
    with TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.tif"
        kym_image._file_path_dict[1] = test_file
        
        kym_analysis.save_analysis()
        
        csv_path, _ = kym_analysis._get_save_paths()
        assert csv_path.exists(), "Empty CSV file should exist after save"
        assert csv_path.is_file(), "CSV path should be a file"


def test_kymanalysis_load_empty_csv() -> None:
    """Test that loading an empty CSV creates empty DataFrame with correct columns."""
    test_image = np.zeros((100, 100), dtype=np.uint16)
    kym_image = KymImage(img_data=test_image, load_image=True)
    kym_analysis = kym_image.get_kym_analysis()
    
    # Create empty DataFrame and save it
    bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi = kym_image.rois.create_roi(bounds=bounds, note="Test ROI")
    kym_analysis.analyze_roi(roi.id, window_size=16, use_multiprocessing=False)
    kym_image.rois.delete(roi.id)
    kym_analysis.invalidate(roi.id)
    
    with TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.tif"
        kym_image._file_path_dict[1] = test_file
        
        # Save empty DataFrame
        kym_image.save_metadata()
        kym_analysis.save_analysis()
        
        # Create new instance and load
        kym_image2 = KymImage(test_file, load_image=False)
        kym_image2.load_metadata()
        kym_analysis2 = kym_image2.get_kym_analysis()
        
        # Verify empty DataFrame was loaded
        assert kym_analysis2._df is not None
        assert len(kym_analysis2._df) == 0
        
        # Verify columns are correct
        expected_columns = [
            "roi_id", "channel", "time", "velocity", "parentFolder", "file",
            "algorithm", "delx", "delt", "numLines", "pntsPerLine",
            "cleanVelocity", "absVelocity"
        ]
        assert list(kym_analysis2._df.columns) == expected_columns


def test_kymanalysis_load_empty_csv_preserves_schema() -> None:
    """Test that loading empty CSV preserves all column names.
    
    Note: When pandas reads an empty CSV, it cannot infer dtypes from data
    and may default to 'object' dtype. This is expected behavior. The important
    thing is that all columns exist and the DataFrame structure is correct.
    When actual data is added, dtypes will be correct.
    """
    test_image = np.zeros((100, 100), dtype=np.uint16)
    kym_image = KymImage(img_data=test_image, load_image=True)
    kym_analysis = kym_image.get_kym_analysis()
    
    # Create and save empty DataFrame
    bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi = kym_image.rois.create_roi(bounds=bounds, note="Test ROI")
    kym_analysis.analyze_roi(roi.id, window_size=16, use_multiprocessing=False)
    kym_image.rois.delete(roi.id)
    kym_analysis.invalidate(roi.id)
    
    with TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.tif"
        kym_image._file_path_dict[1] = test_file
        
        kym_image.save_metadata()
        kym_analysis.save_analysis()
        
        # Load and verify schema
        kym_image2 = KymImage(test_file, load_image=False)
        kym_image2.load_metadata()
        kym_analysis2 = kym_image2.get_kym_analysis()
        
        # Verify DataFrame exists and is empty
        assert kym_analysis2._df is not None
        assert len(kym_analysis2._df) == 0
        
        # Verify all expected columns exist (this is what matters for schema preservation)
        expected_columns = [
            "roi_id", "channel", "time", "velocity", "parentFolder", "file",
            "algorithm", "delx", "delt", "numLines", "pntsPerLine",
            "cleanVelocity", "absVelocity"
        ]
        assert list(kym_analysis2._df.columns) == expected_columns
        
        # Note: Dtypes may be 'object' when loading empty CSV (pandas behavior),
        # but this is acceptable - when data is added, dtypes will be correct


def test_kymanalysis_csv_overwrite_not_append() -> None:
    """Test that saving empty DataFrame overwrites previous CSV (not append)."""
    test_image = np.zeros((100, 100), dtype=np.uint16)
    kym_image = KymImage(img_data=test_image, load_image=True)
    kym_analysis = kym_image.get_kym_analysis()
    
    with TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.tif"
        kym_image._file_path_dict[1] = test_file
        
        # Step 1: Analyze ROI and save (CSV has data)
        bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
        roi = kym_image.rois.create_roi(bounds=bounds, note="Test ROI")
        kym_analysis.analyze_roi(roi.id, window_size=16, use_multiprocessing=False)
        
        kym_image.save_metadata()
        kym_analysis.save_analysis()
        
        csv_path, _ = kym_analysis._get_save_paths()
        assert csv_path.exists()
        
        # Get file size with data
        file_size_with_data = csv_path.stat().st_size
        assert file_size_with_data > 0
        
        # Read and verify it has data
        df_with_data = pd.read_csv(csv_path)
        assert len(df_with_data) > 0
        
        # Step 2: Delete ROI and save empty (should overwrite)
        kym_image.rois.delete(roi.id)
        kym_analysis.invalidate(roi.id)
        kym_analysis.save_analysis()
        
        # Verify file size is smaller (only header now)
        file_size_empty = csv_path.stat().st_size
        assert file_size_empty < file_size_with_data, "Empty CSV should be smaller than CSV with data"
        
        # Verify content doesn't contain old data
        df_empty = pd.read_csv(csv_path)
        assert len(df_empty) == 0, "Loaded CSV should be empty"
        
        # Verify no old ROI data
        if len(df_empty) == 0:
            # Good, it's empty
            pass
        else:
            # If somehow not empty, verify no old roi_id
            assert roi.id not in df_empty["roi_id"].values, "Old ROI data should not be present"


def test_kymanalysis_save_empty_df_overwrites_previous() -> None:
    """CRITICAL: Test round-trip scenario - analyze → save → delete all ROIs → save → load."""
    test_image = np.zeros((100, 100), dtype=np.uint16)
    kym_image = KymImage(img_data=test_image, load_image=True)
    kym_analysis = kym_image.get_kym_analysis()
    
    with TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.tif"
        kym_image._file_path_dict[1] = test_file
        
        # Step 1: Analyze ROI → save (CSV has data)
        bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
        roi = kym_image.rois.create_roi(bounds=bounds, note="Test ROI")
        kym_analysis.analyze_roi(roi.id, window_size=16, use_multiprocessing=False)
        
        kym_image.save_metadata()
        saved1 = kym_analysis.save_analysis()
        assert saved1 is True
        
        csv_path, json_path = kym_analysis._get_save_paths()
        assert csv_path.exists()
        file_size_with_data = csv_path.stat().st_size
        assert file_size_with_data > 0, "CSV should have data"
        
        # Step 2: Delete all ROIs → save (CSV should be empty with correct columns)
        kym_image.rois.delete(roi.id)
        kym_analysis.invalidate(roi.id)
        
        assert kym_analysis._df is not None
        assert len(kym_analysis._df) == 0
        
        saved2 = kym_analysis.save_analysis()
        assert saved2 is True
        
        # Verify file exists but only has header
        assert csv_path.exists()
        file_size_empty = csv_path.stat().st_size
        assert file_size_empty < file_size_with_data, "Empty CSV should be smaller"
        
        # Step 3: Load → verify empty DataFrame with correct columns (not old data)
        kym_image2 = KymImage(test_file, load_image=False)
        kym_image2.load_metadata()
        kym_analysis2 = kym_image2.get_kym_analysis()
        
        # CRITICAL: Verify empty DataFrame, not old data
        assert kym_analysis2._df is not None
        assert len(kym_analysis2._df) == 0, "Loaded DataFrame should be empty, not contain old ROI data"
        
        # Verify correct columns
        expected_columns = [
            "roi_id", "channel", "time", "velocity", "parentFolder", "file",
            "algorithm", "delx", "delt", "numLines", "pntsPerLine",
            "cleanVelocity", "absVelocity"
        ]
        assert list(kym_analysis2._df.columns) == expected_columns
        
        # Verify no old ROI data
        if len(kym_analysis2._df) > 0:
            assert roi.id not in kym_analysis2._df["roi_id"].values, "Old ROI data should not be present"


def test_kymanalysis_round_trip_delete_all_rois() -> None:
    """Test full round-trip: create ROI → analyze → save → load → delete all ROIs → save → load."""
    test_image = np.zeros((100, 100), dtype=np.uint16)
    kym_image = KymImage(img_data=test_image, load_image=True)
    kym_analysis = kym_image.get_kym_analysis()
    
    with TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.tif"
        kym_image._file_path_dict[1] = test_file
        
        # Create ROI → analyze → save
        bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
        roi = kym_image.rois.create_roi(bounds=bounds, note="Test ROI")
        kym_analysis.analyze_roi(roi.id, window_size=16, use_multiprocessing=False)
        
        kym_image.save_metadata()
        kym_analysis.save_analysis()
        
        # Load → verify data exists
        kym_image2 = KymImage(test_file, load_image=False)
        kym_image2.load_metadata()
        kym_analysis2 = kym_image2.get_kym_analysis()
        
        assert kym_analysis2.has_analysis(roi.id)
        assert kym_analysis2._df is not None
        assert len(kym_analysis2._df) > 0
        
        # Delete all ROIs → save
        kym_image2.rois.delete(roi.id)
        kym_analysis2.invalidate(roi.id)
        kym_analysis2.save_analysis()
        
        # Load again → verify empty DataFrame with correct columns
        kym_image3 = KymImage(test_file, load_image=False)
        kym_image3.load_metadata()
        kym_analysis3 = kym_image3.get_kym_analysis()
        
        assert kym_analysis3._df is not None
        assert len(kym_analysis3._df) == 0
        
        expected_columns = [
            "roi_id", "channel", "time", "velocity", "parentFolder", "file",
            "algorithm", "delx", "delt", "numLines", "pntsPerLine",
            "cleanVelocity", "absVelocity"
        ]
        assert list(kym_analysis3._df.columns) == expected_columns


def test_kymanalysis_round_trip_delete_then_reanalyze() -> None:
    """Test: Delete all ROIs → save empty → add new ROI → analyze → save → load."""
    test_image = np.zeros((100, 100), dtype=np.uint16)
    kym_image = KymImage(img_data=test_image, load_image=True)
    kym_analysis = kym_image.get_kym_analysis()
    
    with TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.tif"
        kym_image._file_path_dict[1] = test_file
        
        # Create, analyze, and delete ROI
        bounds1 = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
        roi1 = kym_image.rois.create_roi(bounds=bounds1, note="ROI 1")
        kym_analysis.analyze_roi(roi1.id, window_size=16, use_multiprocessing=False)
        kym_image.save_metadata()
        kym_analysis.save_analysis()
        
        # Delete all ROIs → save empty
        kym_image.rois.delete(roi1.id)
        kym_analysis.invalidate(roi1.id)
        kym_analysis.save_analysis()
        
        # Add new ROI → analyze
        bounds2 = RoiBounds(dim0_start=20, dim0_stop=60, dim1_start=20, dim1_stop=60)
        roi2 = kym_image.rois.create_roi(bounds=bounds2, note="ROI 2")
        kym_analysis.analyze_roi(roi2.id, window_size=16, use_multiprocessing=False)
        kym_image.save_metadata()
        kym_analysis.save_analysis()
        
        # Load → verify new data (not empty, has correct ROI data)
        kym_image2 = KymImage(test_file, load_image=False)
        kym_image2.load_metadata()
        kym_analysis2 = kym_image2.get_kym_analysis()
        
        assert kym_analysis2._df is not None
        assert len(kym_analysis2._df) > 0, "Should have new ROI data, not empty"
        assert kym_analysis2.has_analysis(roi2.id)
        
        # Verify it's ROI2's data, not ROI1's
        df_loaded = kym_analysis2.get_analysis(roi2.id)
        assert df_loaded is not None
        assert len(df_loaded) > 0
        assert roi2.id in df_loaded["roi_id"].values
        assert roi1.id not in df_loaded["roi_id"].values


def test_kymanalysis_round_trip_multiple_rois_delete_one() -> None:
    """Test: Multiple ROIs → analyze all → delete one → save → load."""
    test_image = np.zeros((100, 100), dtype=np.uint16)
    kym_image = KymImage(img_data=test_image, load_image=True)
    kym_analysis = kym_image.get_kym_analysis()
    
    with TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.tif"
        kym_image._file_path_dict[1] = test_file
        
        # Create and analyze two ROIs
        bounds1 = RoiBounds(dim0_start=10, dim0_stop=30, dim1_start=10, dim1_stop=30)
        roi1 = kym_image.rois.create_roi(bounds=bounds1, note="ROI 1")
        kym_analysis.analyze_roi(roi1.id, window_size=16, use_multiprocessing=False)
        
        bounds2 = RoiBounds(dim0_start=50, dim0_stop=70, dim1_start=50, dim1_stop=70)
        roi2 = kym_image.rois.create_roi(bounds=bounds2, note="ROI 2")
        kym_analysis.analyze_roi(roi2.id, window_size=16, use_multiprocessing=False)
        
        kym_image.save_metadata()
        kym_analysis.save_analysis()
        
        # Delete one ROI
        kym_image.rois.delete(roi1.id)
        kym_analysis.invalidate(roi1.id)
        kym_analysis.save_analysis()
        
        # Load → verify remaining ROI data intact
        kym_image2 = KymImage(test_file, load_image=False)
        kym_image2.load_metadata()
        kym_analysis2 = kym_image2.get_kym_analysis()
        
        assert kym_analysis2._df is not None
        assert kym_analysis2.has_analysis(roi2.id)
        assert not kym_analysis2.has_analysis(roi1.id)
        
        # Verify ROI2 data is present
        df2 = kym_analysis2.get_analysis(roi2.id)
        assert df2 is not None
        assert len(df2) > 0
        assert roi2.id in df2["roi_id"].values
        
        # Verify ROI1 data is gone
        df1 = kym_analysis2.get_analysis(roi1.id)
        assert df1 is None or len(df1) == 0


def test_kymanalysis_round_trip_delete_all_then_add_roi() -> None:
    """Test: Delete all ROIs → save empty → add ROI → analyze → verify DataFrame transitions."""
    test_image = np.zeros((100, 100), dtype=np.uint16)
    kym_image = KymImage(img_data=test_image, load_image=True)
    kym_analysis = kym_image.get_kym_analysis()
    
    with TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.tif"
        kym_image._file_path_dict[1] = test_file
        
        # Create, analyze, delete all, save empty
        bounds1 = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
        roi1 = kym_image.rois.create_roi(bounds=bounds1, note="ROI 1")
        kym_analysis.analyze_roi(roi1.id, window_size=16, use_multiprocessing=False)
        kym_image.rois.delete(roi1.id)
        kym_analysis.invalidate(roi1.id)
        kym_image.save_metadata()
        kym_analysis.save_analysis()
        
        # Verify DataFrame is empty
        assert kym_analysis._df is not None
        assert len(kym_analysis._df) == 0
        
        # Add ROI → analyze → verify DataFrame transitions from empty to populated
        bounds2 = RoiBounds(dim0_start=20, dim0_stop=60, dim1_start=20, dim1_stop=60)
        roi2 = kym_image.rois.create_roi(bounds=bounds2, note="ROI 2")
        kym_analysis.analyze_roi(roi2.id, window_size=16, use_multiprocessing=False)
        
        # Verify DataFrame now has data
        assert kym_analysis._df is not None
        assert len(kym_analysis._df) > 0
        assert kym_analysis.has_analysis(roi2.id)

