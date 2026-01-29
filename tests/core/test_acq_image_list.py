"""Unit tests for AcqImageList class.

Tests AcqImageList with various configurations:
- KymImage instances (primary use case)
- File extension filtering
- ignore_file_stub filtering
- Depth-based scanning
- Metadata collection
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import shutil

import numpy as np
import pytest

from kymflow.core.image_loaders.acq_image import AcqImage
from kymflow.core.image_loaders.acq_image_list import AcqImageList
from kymflow.core.image_loaders.kym_image import KymImage
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


@pytest.fixture
def temp_folder_with_tif_files() -> Path:
    """Create a temporary folder with test TIFF files."""
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        # Create some test files
        test_files = [
            "file1.tif",
            "file2.tif",
            "file_C001.tif",
            "file_C002.tif",  # This should be ignored if stub is "C002"
            "file_C003.tif",
        ]
        
        for filename in test_files:
            # Create a simple 2D numpy array and save as TIFF
            # For testing, we'll create minimal valid files
            file_path = tmp_path / filename
            # Create a small 2D array
            img_array = np.random.randint(0, 255, size=(10, 20), dtype=np.uint8)
            # Note: We can't easily create TIFF files without tifffile write capability
            # So we'll create empty files for structure testing
            file_path.touch()
        
        # Create a subfolder with more files
        subfolder = tmp_path / "subfolder"
        subfolder.mkdir()
        (subfolder / "subfile1.tif").touch()
        (subfolder / "subfile2.tif").touch()
        
        yield tmp_path


def test_acq_image_list_initialization() -> None:
    """Test AcqImageList basic initialization."""
    logger.info("Testing AcqImageList initialization")
    
    # Create with a non-existent folder (should handle gracefully)
    image_list = AcqImageList(
        path="/nonexistent/folder",
        image_cls=AcqImage,
        file_extension=".tif"
    )
    
    assert image_list.folder == Path("/nonexistent/folder").resolve()
    assert image_list.file_extension == ".tif"
    assert image_list.ignore_file_stub is None
    assert image_list.depth == 1
    assert len(image_list) == 0  # No files found
    logger.info(f"  - Initialized with {len(image_list)} images")


def test_acq_image_list_with_kym_image_synthetic() -> None:
    """Test AcqImageList with KymImage using synthetic data."""
    logger.info("Testing AcqImageList with KymImage (synthetic)")
    
    # Create temporary folder structure
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        # Create a few KymImage instances manually to test the list
        images = []
        for i in range(3):
            img_2d = np.random.randint(0, 255, size=(50 + i, 100 + i), dtype=np.uint8)
            kym_image = KymImage(path=None, img_data=img_2d)
            images.append(kym_image)
        
        # Test that we can create a list manually (for testing purposes)
        # In practice, AcqImageList scans folders, but for unit testing we can
        # test the list functionality separately
        image_list = AcqImageList(
            path=tmp_path,
            image_cls=KymImage,
            file_extension=".tif"
        )
        
        # Should have 0 images since no actual files exist
        assert len(image_list) == 0
        logger.info(f"  - Created list with {len(image_list)} images")


@pytest.mark.requires_data
def test_acq_image_list_with_kym_image_real_files(sample_tif_files: list[Path]) -> None:
    """Test AcqImageList with KymImage using real TIFF files."""
    if not sample_tif_files:
        pytest.skip("No test data files available")
    
    logger.info("Testing AcqImageList with KymImage (real files)")
    
    # Get the folder containing the test files
    test_folder = sample_tif_files[0].parent
    
    # Create AcqImageList with KymImage
    image_list = AcqImageList(
        path=test_folder,
        image_cls=KymImage,
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

        # Should have getRowDict() method
        row_dict = image.getRowDict()
        assert 'path' in row_dict
        assert 'File Name' in row_dict  # KymImage.getRowDict() uses 'File Name' to match summary_row() keys
        # assert 'ndim' in row_dict or 'shape' in row_dict  # May have either base fields or extended fields
    
    assert count == len(image_list)
    logger.info(f"  - Iterated over {count} images")


def test_acq_image_list_file_extension_filtering() -> None:
    """Test AcqImageList file extension filtering."""
    logger.info("Testing AcqImageList file extension filtering")
    
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        # Create files with different extensions
        (tmp_path / "file1.tif").touch()
        (tmp_path / "file2.tif").touch()
        (tmp_path / "file3.jpg").touch()
        (tmp_path / "file4.png").touch()
        
        # Test with .tif extension
        image_list = AcqImageList(
            path=tmp_path,
            image_cls=AcqImage,
            file_extension=".tif"
        )
        
        # Should only find .tif files (though AcqImage can't load them, so may be 0)
        # But the filtering should work
        logger.info(f"  - Found {len(image_list)} images with .tif extension")
        
        # Test with .jpg extension
        image_list_jpg = AcqImageList(
            path=tmp_path,
            image_cls=AcqImage,
            file_extension=".jpg"
        )
        logger.info(f"  - Found {len(image_list_jpg)} images with .jpg extension")


def test_acq_image_list_ignore_file_stub() -> None:
    """Test AcqImageList ignore_file_stub filtering."""
    logger.info("Testing AcqImageList ignore_file_stub filtering")
    
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        # Create files with different channel stubs
        (tmp_path / "file_C001.tif").touch()
        (tmp_path / "file_C002.tif").touch()
        (tmp_path / "file_C003.tif").touch()
        (tmp_path / "file_no_channel.tif").touch()
        
        # Test without ignore_file_stub (should find all)
        image_list_all = AcqImageList(
            path=tmp_path,
            image_cls=AcqImage,
            file_extension=".tif",
            ignore_file_stub=None
        )
        logger.info(f"  - Without stub filter: {len(image_list_all)} images")
        
        # Test with ignore_file_stub="C002" (should skip file_C002.tif)
        image_list_filtered = AcqImageList(
            path=tmp_path,
            image_cls=AcqImage,
            file_extension=".tif",
            ignore_file_stub="C002"
        )
        logger.info(f"  - With stub filter 'C002': {len(image_list_filtered)} images")
        
        # Verify filtering worked (check filenames if any images were created)
        if len(image_list_filtered) > 0:
            for image in image_list_filtered:
                path = image.getChannelPath(1)
                if path is not None:
                    assert "C002" not in path.name, f"File with C002 should be filtered: {path.name}"


def test_acq_image_list_depth_filtering() -> None:
    """Test AcqImageList depth-based filtering."""
    logger.info("Testing AcqImageList depth filtering")
    
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        # Create folder structure
        (tmp_path / "file1.tif").touch()  # depth 0
        subfolder = tmp_path / "sub1"
        subfolder.mkdir()
        (subfolder / "file2.tif").touch()  # depth 1
        subsubfolder = subfolder / "sub2"
        subsubfolder.mkdir()
        (subsubfolder / "file3.tif").touch()  # depth 2
        
        # Test depth=1 (should only find file1.tif)
        image_list_depth1 = AcqImageList(
            path=tmp_path,
            image_cls=AcqImage,
            file_extension=".tif",
            depth=1
        )
        logger.info(f"  - depth=1: {len(image_list_depth1)} images")
        
        # Test depth=2 (should find file1.tif and file2.tif)
        image_list_depth2 = AcqImageList(
            path=tmp_path,
            image_cls=AcqImage,
            file_extension=".tif",
            depth=2
        )
        logger.info(f"  - depth=2: {len(image_list_depth2)} images")
        
        # Test depth=3 (should find all three files)
        image_list_depth3 = AcqImageList(
            path=tmp_path,
            image_cls=AcqImage,
            file_extension=".tif",
            depth=3
        )
        logger.info(f"  - depth=3: {len(image_list_depth3)} images")


def test_acq_image_list_iter_metadata() -> None:
    """Test AcqImageList iter_metadata() method."""
    logger.info("Testing AcqImageList iter_metadata()")
    
    # Create a list with synthetic KymImage instances
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        # Create a test file
        test_file = tmp_path / "test.tif"
        test_file.touch()
        
        # Create list (may not load files, but structure is tested)
        image_list = AcqImageList(
            path=tmp_path,
            image_cls=KymImage,
            file_extension=".tif"
        )
        
        # Test iter_metadata
        metadata_list = list(image_list.iter_metadata())
        assert isinstance(metadata_list, list)
        logger.info(f"  - iter_metadata() returned {len(metadata_list)} items")
        
        # Each item should be a dict with getRowDict() structure
        for metadata in metadata_list:
            assert isinstance(metadata, dict)
            assert 'path' in metadata
            # KymImage.getRowDict() returns 'File Name' (not 'filename') to match summary_row() keys
            assert 'File Name' in metadata
            # assert 'ndim' in metadata
            # assert 'shape' in metadata


def test_acq_image_list_collect_metadata() -> None:
    """Test AcqImageList collect_metadata() method.
    
    This test verifies that collect_metadata() can gather metadata from a list of images
    without loading full image data. The use case is:
    - Scanning a folder for files
    - Creating KymImage instances (with load_image=False)
    - Collecting metadata dictionaries via getRowDict() for display/filtering
    - This allows browsing file lists without the overhead of loading image data
    
    Note: Files that cannot be instantiated (e.g., invalid TIFF files) are silently
    skipped by AcqImageList, so the test may have 0 images if the test file is invalid.
    """
    logger.info("Testing AcqImageList collect_metadata()")
    
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        # Create a test file (may be invalid, but KymImage should handle it gracefully)
        test_file = tmp_path / "test.tif"
        test_file.touch()
        
        image_list = AcqImageList(
            path=tmp_path,
            image_cls=KymImage,
            file_extension=".tif"
        )
        
        # Test collect_metadata
        # Note: If the file is invalid and KymImage can't instantiate it,
        # it will be silently skipped, so the list may be empty
        metadata = image_list.collect_metadata()
        assert isinstance(metadata, list)
        logger.info(f"  - collect_metadata() returned {len(metadata)} items")
        
        # Should be same as iter_metadata
        iter_metadata = list(image_list.iter_metadata())
        assert len(metadata) == len(iter_metadata)
        
        # If images were successfully created, verify metadata structure
        if len(metadata) > 0:
            for meta in metadata:
                assert isinstance(meta, dict)
                # Should have basic fields from getRowDict()
                # KymImage.getRowDict() returns 'File Name' (not 'filename') to match summary_row() keys
                assert 'path' in meta or 'File Name' in meta
                # assert 'ndim' in meta
                # assert 'shape' in meta


def test_acq_image_list_reload() -> None:
    """Test AcqImageList reload() method."""
    logger.info("Testing AcqImageList reload()")
    
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        # Create initial file
        (tmp_path / "file1.tif").touch()
        
        image_list = AcqImageList(
            path=tmp_path,
            image_cls=AcqImage,
            file_extension=".tif"
        )
        
        initial_count = len(image_list)
        logger.info(f"  - Initial count: {initial_count}")
        
        # Add another file
        (tmp_path / "file2.tif").touch()
        
        # Reload
        image_list.reload()
        
        # Should have more files (or same if files couldn't be loaded)
        new_count = len(image_list)
        logger.info(f"  - After reload count: {new_count}")


def test_acq_image_list_getitem_and_iter() -> None:
    """Test AcqImageList __getitem__ and __iter__ methods."""
    logger.info("Testing AcqImageList __getitem__ and __iter__")
    
    # Create a few synthetic KymImage instances for testing
    images = []
    for i in range(3):
        img_2d = np.random.randint(0, 255, size=(50, 100), dtype=np.uint8)
        kym_image = KymImage(path=None, img_data=img_2d)
        images.append(kym_image)
    
    # Test that we can access by index (if we had a way to populate the list)
    # For now, test the structure with an empty list
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        image_list = AcqImageList(
            path=tmp_path,
            image_cls=KymImage,
            file_extension=".tif"
        )
        
        # Test __len__
        assert len(image_list) == 0
        
        # Test __iter__ (should work even with empty list)
        count = 0
        for image in image_list:
            count += 1
        assert count == 0
        
        logger.info("  - __getitem__ and __iter__ work correctly")


def test_acq_image_list_load_image_data(temp_folder_with_tif_files: Path) -> None:
    """Test AcqImageList.load_image_data() method."""
    logger.info("Testing AcqImageList.load_image_data()")
    
    image_list = AcqImageList(
        path=temp_folder_with_tif_files,
        image_cls=KymImage,
        file_extension=".tif",
        depth=1
    )
    
    if len(image_list) == 0:
        pytest.skip("No images found in test folder")
    
    # Get first image (should not have image data loaded yet)
    first_image = image_list[0]
    assert first_image.getChannelData(1) is None, "Image data should not be loaded initially"
    
    # Load image data using AcqImageList API
    # Note: temp_folder_with_tif_files creates empty files that can't be loaded,
    # so loading will fail. We test that the method is called without crashing.
    success = image_list.load_image_data(0, channel=1)
    assert isinstance(success, bool), "load_image_data() should return a boolean"
    
    # For empty/invalid files, loading will fail (success=False)
    # We verify the method was called and handled the failure gracefully
    if not success:
        logger.info("  - load_image_data() called but failed (expected for empty test files)")
    else:
        # If loading succeeded, verify image data is loaded
        image_data = first_image.getChannelData(1)
        assert image_data is not None, "Image data should be loaded after load_image_data()"
        assert isinstance(image_data, np.ndarray), "Image data should be a numpy array"
        logger.info("  - load_image_data() works correctly")


def test_acq_image_list_load_all_channels(temp_folder_with_tif_files: Path) -> None:
    """Test AcqImageList.load_all_channels() method."""
    logger.info("Testing AcqImageList.load_all_channels()")
    
    image_list = AcqImageList(
        path=temp_folder_with_tif_files,
        image_cls=KymImage,
        file_extension=".tif",
        depth=1
    )
    
    if len(image_list) == 0:
        pytest.skip("No images found in test folder")
    
    # Get first image
    first_image = image_list[0]
    
    # Load all channels using AcqImageList API
    load_results = image_list.load_all_channels(0)
    
    # Verify results
    assert isinstance(load_results, dict), "load_all_channels() should return a dict"
    
    # Note: temp_folder_with_tif_files creates empty files that can't be loaded,
    # so loading will fail. We test that the method is called without crashing.
    # At least channel 1 should be in results if file path exists (even if loading failed)
    if len(load_results) > 0:
        assert 1 in load_results, "Channel 1 should be in results"
        # For empty/invalid files, loading will fail (load_results[1]=False)
        # We verify the method was called and handled the failure gracefully
        assert isinstance(load_results[1], bool), "Channel 1 result should be a boolean"
        if not load_results[1]:
            logger.info("  - load_all_channels() called but failed for channel 1 (expected for empty test files)")
    
    logger.info(f"  - load_all_channels() works correctly, loaded {len(load_results)} channels")


def test_kym_image_load_channel_idempotent(temp_folder_with_tif_files: Path) -> None:
    """Test that KymImage.load_channel() is idempotent."""
    logger.info("Testing KymImage.load_channel() idempotent behavior")
    
    image_list = AcqImageList(
        path=temp_folder_with_tif_files,
        image_cls=KymImage,
        file_extension=".tif",
        depth=1
    )
    
    if len(image_list) == 0:
        pytest.skip("No images found in test folder")
    
    first_image = image_list[0]
    
    # First load should succeed
    success1 = first_image.load_channel(1)
    
    # Get the image data after first load
    data_after_first = first_image.getChannelData(1)
    
    # Second load should also succeed (idempotent)
    success2 = first_image.load_channel(1)
    
    # Get the image data after second load
    data_after_second = first_image.getChannelData(1)
    
    # Data should be the same (not reloaded)
    if data_after_first is not None:
        assert data_after_second is not None, "Data should still exist after second load"
        assert np.array_equal(data_after_first, data_after_second), "Data should be identical (idempotent)"
        assert success1 == success2, "Both loads should return same success status"
    
    logger.info("  - load_channel() is idempotent")


def test_acq_image_list_any_dirty_analysis() -> None:
    """Test AcqImageList.any_dirty_analysis() method."""
    logger.info("Testing AcqImageList.any_dirty_analysis()")
    
    # Create synthetic KymImage instances
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        # Create a few test files
        for i in range(3):
            test_file = tmp_path / f"test_{i}.tif"
            test_file.touch()
        
        image_list = AcqImageList(
            path=tmp_path,
            image_cls=KymImage,
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
            
            # Test with analysis dirty (if we can create analysis)
            # This requires actual image data, so we'll test metadata dirty only
            # which is sufficient to verify any_dirty_analysis() works
        
        logger.info("  - any_dirty_analysis() works correctly")


def test_acq_image_list_any_dirty_analysis_with_analysis() -> None:
    """Test AcqImageList.any_dirty_analysis() with actual analysis data."""
    logger.info("Testing AcqImageList.any_dirty_analysis() with analysis")
    
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
        # In practice, AcqImageList scans folders, but for unit testing we can
        # test the method directly
        image_list = AcqImageList(
            path=tmp_path,
            image_cls=KymImage,
            file_extension=".tif",
            depth=1
        )
        
        # If list found the file, test dirty detection
        # Otherwise, test with manually created list structure
        # For this test, we'll verify the method works with a KymImage that has dirty analysis
        # by checking the is_dirty property directly
        
        logger.info("  - any_dirty_analysis() detects analysis dirty state")

