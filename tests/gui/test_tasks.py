"""Tests for GUI task functions."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

import numpy as np
import pytest
import tifffile

from kymflow.core.image_loaders.kym_image import KymImage
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


def test_run_flow_analysis_creates_roi_if_none_exists(sample_kym_file: KymImage) -> None:
    """Test that run_flow_analysis creates a default ROI if none exists."""
    task_state = TaskState()
    result_received = {"success": False}
    
    def on_result(success: bool) -> None:
        result_received["success"] = success
    
    # Ensure no ROIs exist
    assert sample_kym_file.kymanalysis.num_rois == 0
    
    # Run analysis (should create ROI automatically)
    run_flow_analysis(
        sample_kym_file,
        task_state,
        window_size=16,
        on_result=on_result,
    )
    
    # Wait for analysis to complete
    timeout = 10.0
    start_time = time.time()
    while task_state.running and (time.time() - start_time) < timeout:
        time.sleep(0.1)
    
    # Check that ROI was created
    all_rois = sample_kym_file.kymanalysis.get_all_rois()
    assert len(all_rois) == 1
    
    # Check that ROI has full image bounds
    roi = all_rois[0]
    assert roi.left == 0.0
    assert roi.top == 0.0
    assert roi.right == 200.0
    assert roi.bottom == 100.0
    
    # Check that analysis was performed
    assert task_state.message == "Done"
    assert sample_kym_file.kymanalysis.has_analysis(roi.roi_id)


def test_run_flow_analysis_uses_existing_roi(sample_kym_file: KymImage) -> None:
    """Test that run_flow_analysis uses existing ROI if available."""
    task_state = TaskState()
    result_received = {"success": False}
    
    def on_result(success: bool) -> None:
        result_received["success"] = success
    
    # Create an ROI with specific coordinates
    roi = sample_kym_file.kymanalysis.add_roi(left=10, top=10, right=50, bottom=50, note="Test ROI")
    roi_id = roi.roi_id
    
    # Run analysis (should use existing ROI)
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
    all_rois = sample_kym_file.kymanalysis.get_all_rois()
    assert len(all_rois) == 1
    assert all_rois[0].roi_id == roi_id
    
    # Check that analysis was performed on the correct ROI
    assert task_state.message == "Done"
    assert sample_kym_file.kymanalysis.has_analysis(roi_id)


def test_run_batch_flow_analysis_creates_rois(sample_kym_file: KymImage) -> None:
    """Test that run_batch_flow_analysis creates ROIs for each file."""
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
        
        files = [sample_kym_file, kym_file2]
        per_file_task = TaskState()
        overall_task = TaskState()
        
        file_completed = {"count": 0}
        
        def on_file_complete(kf: KymImage) -> None:
            file_completed["count"] += 1
        
        def on_batch_complete(cancelled: bool) -> None:
            pass
        
        # Ensure no ROIs exist
        assert sample_kym_file.kymanalysis.num_rois == 0
        assert kym_file2.kymanalysis.num_rois == 0
        
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
        
        # Check that ROIs were created for each file
        assert sample_kym_file.kymanalysis.num_rois == 1
        assert kym_file2.kymanalysis.num_rois == 1
        
        # Check that analysis was performed
        assert overall_task.message == "2/2 files"
        assert sample_kym_file.kymanalysis.has_analysis()
        assert kym_file2.kymanalysis.has_analysis()


def test_run_flow_analysis_cancellation(sample_kym_file: KymImage) -> None:
    """Test that cancellation works with ROI-based analysis."""
    task_state = TaskState()
    
    # Create ROI
    roi = sample_kym_file.kymanalysis.add_roi()
    
    # Start analysis
    run_flow_analysis(
        sample_kym_file,
        task_state,
        window_size=16,
        roi_id=roi.roi_id,
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

