"""Tests for GUI task functions."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

import numpy as np
import pytest
import tifffile

from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.image_loaders.roi import RoiBounds
from kymflow.core.state import TaskState
from kymflow.gui.tasks import run_batch_flow_analysis, run_flow_analysis


@pytest.fixture
def sample_kym_file() -> KymImage:
    """Create a sample KymImage for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.tif"
        # Create a small test image
        test_image = np.zeros((100, 200), dtype=np.uint16)
        tifffile.imwrite(test_file, test_image)
        
        kym_file = KymImage(test_file, load_image=True)
        # kym_file.pixels_per_line = 200
        # kym_file.num_lines = 100
        # kym_file.seconds_per_line = 0.001
        # kym_file.um_per_pixel = 1.0
        
        return kym_file


def test_run_flow_analysis_requires_roi_id(sample_kym_file: KymImage) -> None:
    """Test that run_flow_analysis requires roi_id parameter."""
    task_state = TaskState()
    
    # Attempt to run analysis without roi_id (should raise TypeError)
    # roi_id is now a required parameter, so this should fail at call time
    with pytest.raises(TypeError, match="missing.*required.*argument.*roi_id"):
        run_flow_analysis(
            sample_kym_file,
            task_state,
            window_size=16,
        )


def test_run_flow_analysis_fails_with_invalid_roi_id(sample_kym_file: KymImage) -> None:
    """Test that run_flow_analysis fails gracefully when ROI doesn't exist."""
    task_state = TaskState()
    
    # Test that passing invalid roi_id (ROI doesn't exist) fails gracefully
    # Create an ROI first to ensure the file can have ROIs
    bounds = RoiBounds(dim0_start=0, dim0_stop=100, dim1_start=0, dim1_stop=200)
    roi = sample_kym_file.rois.create_roi(bounds=bounds)
    valid_roi_id = roi.id
    
    # Now test with invalid ROI ID (non-existent)
    invalid_roi_id = 99999
    run_flow_analysis(
        sample_kym_file,
        task_state,
        window_size=16,
        roi_id=invalid_roi_id,
    )
    
    # Wait for error to be set
    timeout = 5.0
    start_time = time.time()
    while task_state.running and (time.time() - start_time) < timeout:
        time.sleep(0.1)
    
    # Check that error message indicates ROI not found
    assert not task_state.running
    assert "not found" in task_state.message or "Error" in task_state.message


def test_run_flow_analysis_uses_provided_roi_id(sample_kym_file: KymImage) -> None:
    """Test that run_flow_analysis uses the provided roi_id."""
    task_state = TaskState()
    result_received = {"success": False}
    
    def on_result(success: bool) -> None:
        result_received["success"] = success
    
    # Create an ROI with specific coordinates
    bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi = sample_kym_file.rois.create_roi(bounds=bounds, note="Test ROI")
    roi_id = roi.id
    
    # Run analysis with provided roi_id
    run_flow_analysis(
        sample_kym_file,
        task_state,
        window_size=16,
        roi_id=roi_id,
        on_result=on_result,
    )
    
    # Wait for analysis to complete
    timeout = 10.0
    start_time = time.time()
    while task_state.running and (time.time() - start_time) < timeout:
        time.sleep(0.1)
    
    # Check that only one ROI exists (no new one created)
    roi_ids = sample_kym_file.rois.get_roi_ids()
    assert len(roi_ids) == 1
    assert roi_ids[0] == roi_id
    
    # Check that analysis was performed on the correct ROI
    assert task_state.message == "Done"
    assert sample_kym_file.get_kym_analysis().has_analysis(roi_id)


def test_run_batch_flow_analysis_skips_files_without_rois(sample_kym_file: KymImage) -> None:
    """Test that run_batch_flow_analysis skips files without ROIs."""
    # Create a second file
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file2 = Path(tmpdir) / "test2.tif"
        test_image2 = np.zeros((80, 150), dtype=np.uint16)
        tifffile.imwrite(test_file2, test_image2)
        
        kym_file2 = KymImage(test_file2, load_image=True)
        
        # Create ROI for first file only
        bounds1 = RoiBounds(dim0_start=0, dim0_stop=100, dim1_start=0, dim1_stop=200)
        roi1 = sample_kym_file.rois.create_roi(bounds=bounds1)
        
        # Second file has no ROI
        assert sample_kym_file.rois.numRois() == 1
        assert kym_file2.rois.numRois() == 0
        
        files = [sample_kym_file, kym_file2]
        per_file_task = TaskState()
        overall_task = TaskState()
        
        file_completed = {"count": 0}
        
        def on_file_complete(kf: KymImage) -> None:
            file_completed["count"] += 1
        
        def on_batch_complete(cancelled: bool) -> None:
            pass
        
        # Run batch analysis
        run_batch_flow_analysis(
            files,
            per_file_task,
            overall_task,
            window_size=16,
            on_file_complete=on_file_complete,
            on_batch_complete=on_batch_complete,
        )
        
        # Wait for batch to complete
        timeout = 20.0
        start_time = time.time()
        while overall_task.running and (time.time() - start_time) < timeout:
            time.sleep(0.1)
        
        # Check that no new ROIs were created
        assert sample_kym_file.rois.numRois() == 1  # Still only the one we created
        assert kym_file2.rois.numRois() == 0  # Still no ROI (was skipped)
        
        # Check that only the first file was analyzed (second was skipped)
        assert sample_kym_file.get_kym_analysis().has_analysis(roi1.id)
        assert not kym_file2.get_kym_analysis().has_analysis()  # No analysis for skipped file
        
        # Check that completion callback was only called once (for the file with ROI)
        assert file_completed["count"] == 1


def test_run_flow_analysis_cancellation(sample_kym_file: KymImage) -> None:
    """Test that cancellation works with ROI-based analysis."""
    task_state = TaskState()
    
    # Create ROI
    bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi = sample_kym_file.rois.create_roi(bounds=bounds)
    
    # Start analysis
    run_flow_analysis(
        sample_kym_file,
        task_state,
        window_size=16,
        roi_id=roi.id,
    )
    
    # Wait a bit for analysis to start
    time.sleep(0.5)
    
    # Cancel the analysis
    if task_state.running:
        task_state.request_cancel()
    
    # Wait for cancellation to complete
    timeout = 5.0
    start_time = time.time()
    while task_state.running and (time.time() - start_time) < timeout:
        time.sleep(0.1)
    
    # Check that analysis was cancelled
    assert not task_state.running
    assert "Cancelled" in task_state.message or task_state.message == "Done"

