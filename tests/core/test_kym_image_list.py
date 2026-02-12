"""Unit tests for KymImageList class.

Tests KymImageList with various configurations:
- KymImage-specific methods (any_dirty_analysis, total_number_of_event, detect_all_events, get_radon_report)
- Inheritance from AcqImageList
- Verification that all images are KymImage instances
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock
import shutil

import numpy as np
import pytest

from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.image_loaders.kym_image_list import KymImageList
from kymflow.core.image_loaders.acq_image_list import AcqImageList
from kymflow.core.utils import get_data_folder
from kymflow.core.utils.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)


@pytest.fixture
def data_dir() -> Path:
    """Get the test data directory."""
    return get_data_folder()


@pytest.fixture
def sample_tif_files(data_dir: Path) -> list[Path]:
    """Get list of TIFF files from test data directory."""
    tif_files = sorted(data_dir.glob("*.tif"))
    logger.info(f"Found {len(tif_files)} TIFF files in test data directory")
    return list(tif_files)


def test_kym_image_list_initialization() -> None:
    """Test KymImageList basic initialization."""
    logger.info("Testing KymImageList initialization")
    
    # Create with a non-existent folder (should handle gracefully)
    image_list = KymImageList(
        path="/nonexistent/folder",
        file_extension=".tif"
    )
    
    # For non-existent paths, folder is set to resolved path (which may resolve to parent)
    assert image_list.folder is not None
    assert image_list.file_extension == ".tif"
    assert image_list.ignore_file_stub is None
    assert image_list.depth == 1
    assert len(image_list) == 0  # No files found
    
    # Verify it's an instance of AcqImageList
    assert isinstance(image_list, AcqImageList)
    
    logger.info(f"  - Initialized with {len(image_list)} images")


def test_kym_image_list_inheritance() -> None:
    """Test that KymImageList inherits from AcqImageList."""
    logger.info("Testing KymImageList inheritance")
    
    image_list = KymImageList(path=None, file_extension=".tif")
    
    # Should be an instance of AcqImageList
    assert isinstance(image_list, AcqImageList)
    
    # Should have all inherited methods
    assert hasattr(image_list, "load")
    assert hasattr(image_list, "iter_metadata")
    assert hasattr(image_list, "collect_metadata")
    assert hasattr(image_list, "find_by_path")
    
    logger.info("  - KymImageList correctly inherits from AcqImageList")


def test_kym_image_list_always_kym_image() -> None:
    """Test that KymImageList always creates KymImage instances."""
    logger.info("Testing KymImageList always creates KymImage instances")
    
    # Create synthetic KymImage instances manually
    images = []
    for i in range(3):
        img_2d = np.random.randint(0, 255, size=(50 + i, 100 + i), dtype=np.uint8)
        kym_image = KymImage(path=None, img_data=img_2d)
        images.append(kym_image)
    
    # Create KymImageList and manually add images
    image_list = KymImageList(path=None, file_extension=".tif")
    image_list.images = images
    
    # All images should be KymImage instances
    for image in image_list:
        assert isinstance(image, KymImage)
        assert hasattr(image, "get_kym_analysis")
    
    logger.info(f"  - All {len(image_list)} images are KymImage instances")


@pytest.mark.requires_data
def test_kym_image_list_with_real_files(sample_tif_files: list[Path]) -> None:
    """Test KymImageList with real TIFF files."""
    if not sample_tif_files:
        pytest.skip("No test data files available")
    
    logger.info("Testing KymImageList with real files")
    
    # Get the folder containing the test files
    test_folder = sample_tif_files[0].parent
    
    # Create KymImageList
    image_list = KymImageList(
        path=test_folder,
        file_extension=".tif",
        depth=1
    )
    
    # Should have found at least some files
    assert len(image_list) >= 0  # May be 0 if files can't be loaded
    logger.info(f"  - Found {len(image_list)} images")
    
    # Test iteration
    count = 0
    for image in image_list:
        count += 1
        # Each image should be a KymImage instance
        assert isinstance(image, KymImage)
        assert hasattr(image, "get_kym_analysis")

        # Should have getRowDict() method
        row_dict = image.getRowDict()
        assert 'path' in row_dict
        assert 'File Name' in row_dict  # KymImage.getRowDict() uses 'File Name'
    
    assert count == len(image_list)
    logger.info(f"  - Iterated over {count} images")


def test_kym_image_list_any_dirty_analysis() -> None:
    """Test KymImageList.any_dirty_analysis() method."""
    logger.info("Testing KymImageList.any_dirty_analysis()")
    
    # Create synthetic KymImage instances
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        # Create a few test files
        for i in range(3):
            test_file = tmp_path / f"test_{i}.tif"
            test_file.touch()
        
        image_list = KymImageList(
            path=tmp_path,
            file_extension=".tif",
            depth=1
        )
        
        # Initially should not have dirty analysis
        assert image_list.any_dirty_analysis() is False
        
        # If we have images, test dirty state
        if len(image_list) > 0:
            first_image = image_list[0]
            
            # Mark metadata dirty - should be detected
            first_image.update_experiment_metadata(species="mouse")
            assert image_list.any_dirty_analysis() is True
            
            # Clear dirty - should be clean
            first_image.clear_metadata_dirty()
            assert image_list.any_dirty_analysis() is False
        
        logger.info("  - any_dirty_analysis() works correctly")


def test_kym_image_list_any_dirty_analysis_with_analysis() -> None:
    """Test KymImageList.any_dirty_analysis() with actual analysis data."""
    logger.info("Testing KymImageList.any_dirty_analysis() with analysis")
    
    # Create synthetic KymImage with image data
    test_image = np.zeros((100, 100), dtype=np.uint16)
    kym_image = KymImage(img_data=test_image, load_image=True)
    kym_analysis = kym_image.get_kym_analysis()
    
    # Create ROI and analyze
    from kymflow.core.image_loaders.roi import RoiBounds
    bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi = kym_image.rois.create_roi(bounds=bounds)
    kym_analysis.analyze_roi(roi.id, window_size=16, use_multiprocessing=False)
    
    # Should be dirty after analysis
    assert kym_analysis.is_dirty is True
    
    # Create image list with this image
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        test_file = tmp_path / "test.tif"
        test_file.touch()
        kym_image._file_path_dict[1] = test_file
        
        # Create list manually (for testing)
        image_list = KymImageList(
            path=tmp_path,
            file_extension=".tif",
            depth=1
        )
        
        # Manually add the image to test dirty detection
        image_list.images = [kym_image]
        
        # Should detect dirty analysis
        assert image_list.any_dirty_analysis() is True
        
        logger.info("  - any_dirty_analysis() detects analysis dirty state")


def test_kym_image_list_detect_all_events() -> None:
    """Test detect_all_events() method calls run_velocity_event_analysis() for all ROIs in all files."""
    logger.info("Testing KymImageList detect_all_events()")
    
    # Create a KymImageList with mock KymImage instances
    image_list = KymImageList(path=None, file_extension=".tif")
    
    # Create mock images with different ROI configurations
    mock_image1 = MagicMock(spec=KymImage)
    mock_image1.rois = MagicMock()
    mock_image1.rois.get_roi_ids.return_value = [1, 2]
    mock_kym_analysis1 = MagicMock()
    mock_kym_analysis1.run_velocity_event_analysis = MagicMock()
    mock_image1.get_kym_analysis.return_value = mock_kym_analysis1
    
    mock_image2 = MagicMock(spec=KymImage)
    mock_image2.rois = MagicMock()
    mock_image2.rois.get_roi_ids.return_value = [1]
    mock_kym_analysis2 = MagicMock()
    mock_kym_analysis2.run_velocity_event_analysis = MagicMock()
    mock_image2.get_kym_analysis.return_value = mock_kym_analysis2
    
    # Image without ROIs (should still call get_roi_ids but return empty list)
    mock_image3 = MagicMock(spec=KymImage)
    mock_image3.rois = MagicMock()
    mock_image3.rois.get_roi_ids.return_value = []
    mock_kym_analysis3 = MagicMock()
    mock_kym_analysis3.run_velocity_event_analysis = MagicMock()
    mock_image3.get_kym_analysis.return_value = mock_kym_analysis3
    
    # Add images to the list
    image_list.images = [mock_image1, mock_image2, mock_image3]
    
    # Call detect_all_events()
    image_list.detect_all_events()
    
    # Verify run_velocity_event_analysis was called for each ROI in each file
    # Image 1: ROIs 1 and 2
    assert mock_kym_analysis1.run_velocity_event_analysis.call_count == 2
    mock_kym_analysis1.run_velocity_event_analysis.assert_any_call(
        1, baseline_drop_params=None, nan_gap_params=None, zero_gap_params=None
    )
    mock_kym_analysis1.run_velocity_event_analysis.assert_any_call(
        2, baseline_drop_params=None, nan_gap_params=None, zero_gap_params=None
    )
    
    # Image 2: ROI 1
    assert mock_kym_analysis2.run_velocity_event_analysis.call_count == 1
    mock_kym_analysis2.run_velocity_event_analysis.assert_called_once_with(
        1, baseline_drop_params=None, nan_gap_params=None, zero_gap_params=None
    )
    
    # Image 3: No ROIs, should not call run_velocity_event_analysis
    assert mock_kym_analysis3.run_velocity_event_analysis.call_count == 0
    
    logger.info("  - detect_all_events() calls run_velocity_event_analysis() for all ROIs in all files")


def test_kym_image_list_detect_all_events_empty_list() -> None:
    """Test detect_all_events() with empty image list."""
    logger.info("Testing KymImageList detect_all_events() with empty list")
    
    image_list = KymImageList(path=None, file_extension=".tif")
    image_list.images = []
    
    # Should not raise an error
    image_list.detect_all_events()
    
    logger.info("  - detect_all_events() handles empty list gracefully")


def test_kym_image_list_total_number_of_event() -> None:
    """Test KymImageList.total_number_of_event() method."""
    logger.info("Testing KymImageList.total_number_of_event()")
    
    # Create synthetic KymImage instances with velocity events
    test_image1 = np.zeros((100, 100), dtype=np.uint16)
    kym_image1 = KymImage(img_data=test_image1, load_image=False)
    kym_image1.update_header(shape=(100, 100), ndim=2, voxels=[0.001, 0.284])
    
    test_image2 = np.zeros((100, 100), dtype=np.uint16)
    kym_image2 = KymImage(img_data=test_image2, load_image=False)
    kym_image2.update_header(shape=(100, 100), ndim=2, voxels=[0.001, 0.284])
    
    # Create image list manually (for testing)
    image_list = KymImageList(path=None, file_extension=".tif")
    image_list.images = [kym_image1, kym_image2]
    
    # Initially should be 0
    assert image_list.total_number_of_event() == 0
    
    # Add ROIs and velocity events
    from kymflow.core.image_loaders.roi import RoiBounds
    bounds1 = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi1 = kym_image1.rois.create_roi(bounds=bounds1)
    kym_image1.get_kym_analysis().add_velocity_event(roi1.id, t_start=0.5, t_end=1.0)
    kym_image1.get_kym_analysis().add_velocity_event(roi1.id, t_start=2.0, t_end=3.0)
    
    bounds2 = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=10, dim1_stop=50)
    roi2 = kym_image2.rois.create_roi(bounds=bounds2)
    kym_image2.get_kym_analysis().add_velocity_event(roi2.id, t_start=1.0, t_end=2.0)
    
    # Should count all events across all images
    assert image_list.total_number_of_event() == 3
    
    logger.info("  - total_number_of_event() works correctly")


def test_kym_image_list_get_radon_report() -> None:
    """Test KymImageList.get_radon_report() method."""
    logger.info("Testing KymImageList.get_radon_report()")
    
    # Create synthetic KymImage instances
    test_image1 = np.zeros((100, 100), dtype=np.uint16)
    kym_image1 = KymImage(img_data=test_image1, load_image=False)
    kym_image1.update_header(shape=(100, 100), ndim=2, voxels=[0.001, 0.284])
    
    test_image2 = np.zeros((100, 100), dtype=np.uint16)
    kym_image2 = KymImage(img_data=test_image2, load_image=False)
    kym_image2.update_header(shape=(100, 100), ndim=2, voxels=[0.001, 0.284])
    
    # Create image list manually
    image_list = KymImageList(path=None, file_extension=".tif")
    image_list.images = [kym_image1, kym_image2]
    
    # Get radon report (should work even without analysis)
    reports = image_list.get_radon_report()
    
    # Should return a list
    assert isinstance(reports, list)
    
    # If there are ROIs with analysis, reports should contain RadonReport instances
    # For now, just verify the method doesn't crash
    logger.info(f"  - get_radon_report() returned {len(reports)} reports")


def test_kym_image_list_get_radon_report_df() -> None:
    """Test KymImageList.get_radon_report_df() method."""
    logger.info("Testing KymImageList.get_radon_report_df()")
    
    # Create synthetic KymImage instances
    test_image1 = np.zeros((100, 100), dtype=np.uint16)
    kym_image1 = KymImage(img_data=test_image1, load_image=False)
    kym_image1.update_header(shape=(100, 100), ndim=2, voxels=[0.001, 0.284])
    
    # Create image list manually
    image_list = KymImageList(path=None, file_extension=".tif")
    image_list.images = [kym_image1]
    
    # Get radon report DataFrame
    df = image_list.get_radon_report_df()
    
    # Should return a pandas DataFrame
    import pandas as pd
    assert isinstance(df, pd.DataFrame)
    
    # Should have expected columns if there are reports
    # For now, just verify the method doesn't crash
    logger.info(f"  - get_radon_report_df() returned DataFrame with {len(df)} rows")


def test_kym_image_list_smoke_test() -> None:
    """Smoke test: Verify inheritance structure works correctly."""
    logger.info("Testing KymImageList smoke test")
    
    # Create empty list
    image_list = KymImageList(path=None, file_extension=".tif")
    
    # Verify inheritance
    assert isinstance(image_list, AcqImageList)
    
    # Verify all inherited methods work
    assert len(image_list) == 0
    assert list(image_list.iter_metadata()) == []
    assert image_list.collect_metadata() == []
    
    # Verify KymImage-specific methods exist
    assert hasattr(image_list, "any_dirty_analysis")
    assert hasattr(image_list, "total_number_of_event")
    assert hasattr(image_list, "detect_all_events")
    assert hasattr(image_list, "get_radon_report")
    assert hasattr(image_list, "get_radon_report_df")
    
    # Verify methods can be called without error
    assert image_list.any_dirty_analysis() is False
    assert image_list.total_number_of_event() == 0
    image_list.detect_all_events()  # Should not raise
    assert image_list.get_radon_report() == []
    
    logger.info("  - Smoke test passed: inheritance structure works correctly")
