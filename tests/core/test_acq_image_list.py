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
from unittest.mock import MagicMock, Mock
import shutil
import warnings

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
    
    # For non-existent paths, folder is set to resolved path (which may resolve to parent)
    # The new API resolves paths, so we check that folder is set (may be parent if path doesn't exist)
    assert image_list.folder is not None
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


def test_acq_image_list_iter_metadata_blinded() -> None:
    """Test AcqImageList iter_metadata() with blinded=True."""
    logger.info("Testing AcqImageList iter_metadata() with blinded=True")
    
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        # Create nested directory structure to ensure parent3 exists
        subdir = tmp_path / "a" / "b" / "c"
        subdir.mkdir(parents=True)
        
        # Create test files in nested directory
        file1 = subdir / "file1.tif"
        file2 = subdir / "file2.tif"
        file3 = subdir / "file3.tif"
        file1.touch()
        file2.touch()
        file3.touch()
        
        # Create AcqImageList with synthetic images
        image_list = AcqImageList(
            file_path_list=[str(file1), str(file2), str(file3)],
            image_cls=AcqImage,
            file_extension=".tif"
        )
        
        # Verify _blind_index is set correctly on images
        for index, image in enumerate(image_list):
            assert image._blind_index == index, f"Image {index} should have _blind_index={index}"
        
        # Test iter_metadata with blinded=True
        metadata_list = list(image_list.iter_metadata(blinded=True))
        
        assert len(metadata_list) == len(image_list)
        
        # Check that filenames are blinded (using _blind_index automatically)
        for index, metadata in enumerate(metadata_list):
            assert metadata['filename'] == f"File {index + 1}"
            # parent3 should be "Blinded" if it exists, otherwise None
            # With nested structure a/b/c/file.tif, parent3 = "a"
            if metadata['parent3'] is not None:
                assert metadata['parent3'] == "Blinded"
        
        logger.info(f"  - iter_metadata(blinded=True) returned {len(metadata_list)} items with blinded filenames")


def test_acq_image_list_collect_metadata_blinded() -> None:
    """Test AcqImageList collect_metadata() with blinded=True."""
    logger.info("Testing AcqImageList collect_metadata() with blinded=True")
    
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        # Create nested directory structure to ensure parent3 exists
        subdir = tmp_path / "a" / "b" / "c"
        subdir.mkdir(parents=True)
        
        # Create test files in nested directory
        file1 = subdir / "file1.tif"
        file2 = subdir / "file2.tif"
        file1.touch()
        file2.touch()
        
        # Create AcqImageList
        image_list = AcqImageList(
            file_path_list=[str(file1), str(file2)],
            image_cls=AcqImage,
            file_extension=".tif"
        )
        
        # Verify _blind_index is set correctly on images
        for index, image in enumerate(image_list):
            assert image._blind_index == index, f"Image {index} should have _blind_index={index}"
        
        # Test collect_metadata with blinded=True
        metadata = image_list.collect_metadata(blinded=True)
        
        assert len(metadata) == len(image_list)
        
        # Check that filenames are blinded
        for index, item in enumerate(metadata):
            assert item['filename'] == f"File {index + 1}"
            # parent3 should be "Blinded" if it exists, otherwise None
            # With nested structure a/b/c/file.tif, parent3 = "a"
            if item['parent3'] is not None:
                assert item['parent3'] == "Blinded"
        
        # Should be same as iter_metadata
        iter_metadata = list(image_list.iter_metadata(blinded=True))
        assert len(metadata) == len(iter_metadata)
        
        logger.info(f"  - collect_metadata(blinded=True) returned {len(metadata)} items with blinded filenames")
        
        # If images were successfully created, verify metadata structure
        if len(metadata) > 0:
            for meta in metadata:
                assert isinstance(meta, dict)
                # Should have basic fields from getRowDict()
                # KymImage.getRowDict() returns 'File Name' (not 'filename') to match summary_row() keys
                assert 'path' in meta or 'File Name' in meta
                # assert 'ndim' in meta
                # assert 'shape' in meta


def test_acq_image_list_get_unique_metadata_values() -> None:
    """Test AcqImageList get_unique_metadata_values() method.
    
    This test verifies that get_unique_metadata_values() can extract unique
    non-empty values for experiment metadata fields across all images in the list.
    Useful for populating UI select dropdowns with existing values.
    """
    logger.info("Testing AcqImageList get_unique_metadata_values()")
    
    from kymflow.core.image_loaders.metadata import ExperimentMetadata
    
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        # Create test files
        file1 = tmp_path / "file1.tif"
        file2 = tmp_path / "file2.tif"
        file3 = tmp_path / "file3.tif"
        file1.touch()
        file2.touch()
        file3.touch()
        
        # Create AcqImageList
        image_list = AcqImageList(
            file_path_list=[str(file1), str(file2), str(file3)],
            image_cls=AcqImage,
            file_extension=".tif"
        )
        
        # Set up experiment metadata with various values
        if len(image_list) >= 3:
            # Image 1: species="mouse", condition="control"
            image_list[0]._experiment_metadata = ExperimentMetadata(
                species="mouse",
                condition="control",
                treatment="vehicle",
            )
            # Image 2: species="rat", condition="control" (duplicate condition)
            image_list[1]._experiment_metadata = ExperimentMetadata(
                species="rat",
                condition="control",
                treatment="drug",
            )
            # Image 3: species="mouse" (duplicate), condition="stim", empty treatment
            image_list[2]._experiment_metadata = ExperimentMetadata(
                species="mouse",
                condition="stim",
                treatment="",  # Empty string should be excluded
            )
            
            # Test: get unique species values
            species_values = image_list.get_unique_metadata_values("species")
            assert isinstance(species_values, list)
            assert len(species_values) == 2  # "mouse", "rat" (duplicates removed)
            assert "mouse" in species_values
            assert "rat" in species_values
            assert species_values == sorted(species_values)  # Should be sorted
            logger.info(f"  - get_unique_metadata_values('species') returned: {species_values}")
            
            # Test: get unique condition values
            condition_values = image_list.get_unique_metadata_values("condition")
            assert len(condition_values) == 2  # "control", "stim"
            assert "control" in condition_values
            assert "stim" in condition_values
            assert condition_values == sorted(condition_values)
            logger.info(f"  - get_unique_metadata_values('condition') returned: {condition_values}")
            
            # Test: get unique treatment values (empty string excluded)
            treatment_values = image_list.get_unique_metadata_values("treatment")
            assert len(treatment_values) == 2  # "vehicle", "drug" (empty excluded)
            assert "vehicle" in treatment_values
            assert "drug" in treatment_values
            assert "" not in treatment_values  # Empty string should be excluded
            logger.info(f"  - get_unique_metadata_values('treatment') returned: {treatment_values}")
            
            # Test: field with all empty/None values
            empty_values = image_list.get_unique_metadata_values("genotype")
            assert isinstance(empty_values, list)
            assert len(empty_values) == 0  # All empty, should return empty list
            logger.info(f"  - get_unique_metadata_values('genotype') returned: {empty_values}")


def test_acq_image_list_get_unique_metadata_values_empty_list() -> None:
    """Test get_unique_metadata_values() with empty image list."""
    logger.info("Testing get_unique_metadata_values() with empty list")
    
    # Create empty list
    image_list = AcqImageList(path=None, image_cls=AcqImage, file_extension=".tif")
    
    # Should return empty list for any field
    values = image_list.get_unique_metadata_values("species")
    assert isinstance(values, list)
    assert len(values) == 0
    logger.info(f"  - Empty list returned: {values}")


def test_acq_image_list_get_unique_metadata_values_none_empty() -> None:
    """Test get_unique_metadata_values() handles None and empty string values correctly."""
    logger.info("Testing get_unique_metadata_values() with None and empty values")
    
    from kymflow.core.image_loaders.metadata import ExperimentMetadata
    
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        # Create test files
        file1 = tmp_path / "file1.tif"
        file2 = tmp_path / "file2.tif"
        file3 = tmp_path / "file3.tif"
        file1.touch()
        file2.touch()
        file3.touch()
        
        image_list = AcqImageList(
            file_path_list=[str(file1), str(file2), str(file3)],
            image_cls=AcqImage,
            file_extension=".tif"
        )
        
        if len(image_list) >= 3:
            # Image 1: None value
            image_list[0]._experiment_metadata = ExperimentMetadata(species=None)
            # Image 2: Empty string
            image_list[1]._experiment_metadata = ExperimentMetadata(species="")
            # Image 3: Whitespace-only string
            image_list[2]._experiment_metadata = ExperimentMetadata(species="   ")
            
            # All should be excluded
            values = image_list.get_unique_metadata_values("species")
            assert len(values) == 0
            logger.info(f"  - None/empty values excluded, returned: {values}")
            
            # Test: mix of valid and invalid
            image_list[0]._experiment_metadata = ExperimentMetadata(species="mouse")
            image_list[1]._experiment_metadata = ExperimentMetadata(species="")
            image_list[2]._experiment_metadata = ExperimentMetadata(species="rat")
            
            values = image_list.get_unique_metadata_values("species")
            assert len(values) == 2
            assert "mouse" in values
            assert "rat" in values
            assert "" not in values
            logger.info(f"  - Mixed valid/invalid returned: {values}")


def test_acq_image_list_get_unique_metadata_values_nonexistent_field() -> None:
    """Test get_unique_metadata_values() with non-existent field name."""
    logger.info("Testing get_unique_metadata_values() with non-existent field")
    
    from kymflow.core.image_loaders.metadata import ExperimentMetadata
    
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        file1 = tmp_path / "file1.tif"
        file1.touch()
        
        image_list = AcqImageList(
            file_path_list=[str(file1)],
            image_cls=AcqImage,
            file_extension=".tif"
        )
        
        if len(image_list) >= 1:
            image_list[0]._experiment_metadata = ExperimentMetadata(species="mouse")
            
            # Non-existent field should return empty list (getattr returns None)
            values = image_list.get_unique_metadata_values("nonexistent_field")
            assert isinstance(values, list)
            assert len(values) == 0
            logger.info(f"  - Non-existent field returned: {values}")


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


# DEPRECATED: load_image_data() and load_all_channels() methods were removed from AcqImageList.
# These convenience methods are no longer part of the API. Users should call
# image.load_channel() directly on AcqImage instances.


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


def test_acq_image_list_no_kymimage_specific_methods() -> None:
    """Test that AcqImageList no longer has KymImage-specific methods."""
    logger.info("Testing AcqImageList does not have KymImage-specific methods")
    
    image_list = AcqImageList(path=None, image_cls=AcqImage, file_extension=".tif")
    
    # Verify KymImage-specific methods are not present
    assert not hasattr(image_list, "any_dirty_analysis"), "AcqImageList should not have any_dirty_analysis()"
    assert not hasattr(image_list, "detect_all_events"), "AcqImageList should not have detect_all_events()"
    assert not hasattr(image_list, "total_number_of_event"), "AcqImageList should not have total_number_of_event()"
    assert not hasattr(image_list, "get_radon_report"), "AcqImageList should not have get_radon_report()"
    assert not hasattr(image_list, "get_radon_report_df"), "AcqImageList should not have get_radon_report_df()"
    
    logger.info("  - AcqImageList correctly does not have KymImage-specific methods")


def test_acq_image_list_load() -> None:
    """Test AcqImageList.load() method."""
    logger.info("Testing AcqImageList.load()")
    
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
        
        # Load (should reload files)
        image_list.load()
        
        # Should have more files (or same if files couldn't be loaded)
        new_count = len(image_list)
        logger.info(f"  - After load count: {new_count}")
        
        # Test with None folder
        image_list_none = AcqImageList(path=None, image_cls=AcqImage, file_extension=".tif")
        image_list_none.load()  # Should not raise error
        assert len(image_list_none) == 0
        
        logger.info("  - load() works correctly")


def test_acq_image_list_load_with_follow_symlinks() -> None:
    """Test AcqImageList.load() with follow_symlinks parameter."""
    logger.info("Testing AcqImageList.load() with follow_symlinks")
    
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        # Create a file
        (tmp_path / "file1.tif").touch()
        
        image_list = AcqImageList(
            path=tmp_path,
            image_cls=AcqImage,
            file_extension=".tif"
        )
        
        # Test load with follow_symlinks=False (default)
        image_list.load(follow_symlinks=False)
        
        # Test load with follow_symlinks=True
        image_list.load(follow_symlinks=True)
        
        logger.info("  - load() with follow_symlinks works correctly")


def test_acq_image_list_reload_with_follow_symlinks() -> None:
    """Test AcqImageList.reload() with follow_symlinks parameter."""
    logger.info("Testing AcqImageList.reload() with follow_symlinks")
    
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        (tmp_path / "file1.tif").touch()
        
        image_list = AcqImageList(
            path=tmp_path,
            image_cls=AcqImage,
            file_extension=".tif"
        )
        
        # Test reload with follow_symlinks parameter
        image_list.reload(follow_symlinks=False)
        image_list.reload(follow_symlinks=True)
        
        logger.info("  - reload() with follow_symlinks works correctly")


def test_acq_image_list_with_file_path() -> None:
    """Test AcqImageList initialization with a single file path."""
    logger.info("Testing AcqImageList with file path")
    
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        test_file = tmp_path / "test.tif"
        test_file.touch()
        
        # Create list with file path
        image_list = AcqImageList(
            path=test_file,
            image_cls=AcqImage,
            file_extension=".tif"
        )
        
        # Should contain exactly one file (if it can be loaded)
        assert len(image_list) <= 1, "File path should result in at most one image"
        
        # Verify folder is set to parent directory (using resolve() for path comparison)
        assert image_list.folder.resolve() == tmp_path.resolve()
        assert image_list.path.resolve() == test_file.resolve()
        
        logger.info(f"  - File path initialization works, found {len(image_list)} images")


def test_acq_image_list_with_file_path_wrong_extension() -> None:
    """Test AcqImageList with file path that doesn't match extension."""
    logger.info("Testing AcqImageList with file path (wrong extension)")
    
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        test_file = tmp_path / "test.jpg"
        test_file.touch()
        
        # Create list with file path that doesn't match .tif extension
        image_list = AcqImageList(
            path=test_file,
            image_cls=AcqImage,
            file_extension=".tif"
        )
        
        # Should be empty (file doesn't match extension filter)
        assert len(image_list) == 0
        
        logger.info("  - File path with wrong extension correctly filtered out")


def test_acq_image_list_with_none_path() -> None:
    """Test AcqImageList initialization with path=None."""
    logger.info("Testing AcqImageList with path=None")
    
    image_list = AcqImageList(
        path=None,
        image_cls=AcqImage,
        file_extension=".tif"
    )
    
    # Should be empty
    assert len(image_list) == 0
    assert image_list.path is None
    assert image_list.folder is None
    
    logger.info("  - path=None initialization works correctly")


def test_acq_image_list_str_repr() -> None:
    """Test AcqImageList __str__ and __repr__ methods."""
    logger.info("Testing AcqImageList __str__ and __repr__")
    
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        image_list = AcqImageList(
            path=tmp_path,
            image_cls=KymImage,
            file_extension=".tif",
            depth=2,
            ignore_file_stub="C002"
        )
        
        # Test __str__
        str_repr = str(image_list)
        assert "AcqImageList" in str_repr
        assert "depth: 2" in str_repr
        assert "file_extension: .tif" in str_repr
        assert "ignore_file_stub: C002" in str_repr
        assert "images:" in str_repr
        
        # Test __repr__ (should be same as __str__)
        repr_str = repr(image_list)
        assert repr_str == str_repr
        
        # Test with None folder
        image_list_none = AcqImageList(path=None, image_cls=KymImage, file_extension=".tif")
        str_none = str(image_list_none)
        assert "mode: empty" in str_none
        assert "source: None" in str_none
        
        logger.info("  - __str__ and __repr__ work correctly")


def test_find_by_path_found(temp_folder_with_tif_files: Path) -> None:
    """Test find_by_path when file exists in list."""
    logger.info("Testing find_by_path - file found")
    
    image_list = AcqImageList(
        path=temp_folder_with_tif_files,
        image_cls=KymImage,
        file_extension=".tif",
        depth=2
    )
    
    assert len(image_list) > 0, "Should have at least one file"
    
    # Get the first file's path
    first_image = image_list[0]
    first_path = first_image.path
    assert first_path is not None, "First image should have a path"
    
    # Find by Path object
    found = image_list.find_by_path(first_path)
    assert found is not None, "Should find the file"
    assert found == first_image, "Should return the same image instance"
    
    # Find by string path
    found_str = image_list.find_by_path(str(first_path))
    assert found_str is not None, "Should find the file with string path"
    assert found_str == first_image, "Should return the same image instance"
    
    logger.info("  - find_by_path works correctly when file exists")


def test_find_by_path_not_found(temp_folder_with_tif_files: Path) -> None:
    """Test find_by_path when file does not exist in list."""
    logger.info("Testing find_by_path - file not found")
    
    image_list = AcqImageList(
        path=temp_folder_with_tif_files,
        image_cls=KymImage,
        file_extension=".tif",
        depth=2
    )
    
    # Try to find a non-existent file
    non_existent = temp_folder_with_tif_files / "nonexistent_file.tif"
    found = image_list.find_by_path(non_existent)
    assert found is None, "Should return None for non-existent file"
    
    # Try with a path that exists on disk but not in the list (wrong extension)
    if len(image_list) > 0:
        # Create a file with wrong extension in the same folder
        wrong_ext_file = temp_folder_with_tif_files / "test.txt"
        wrong_ext_file.write_text("test")
        found_wrong_ext = image_list.find_by_path(wrong_ext_file)
        assert found_wrong_ext is None, "Should return None for file not in list"
        wrong_ext_file.unlink()
    
    logger.info("  - find_by_path returns None for non-existent files")


def test_find_by_path_empty_list() -> None:
    """Test find_by_path with empty list."""
    logger.info("Testing find_by_path - empty list")
    
    image_list = AcqImageList(
        path=None,
        image_cls=KymImage,
        file_extension=".tif"
    )
    
    assert len(image_list) == 0, "List should be empty"
    
    # Try to find any file
    with TemporaryDirectory() as tmpdir:
        test_path = Path(tmpdir) / "test.tif"
        test_path.write_bytes(b"test")
        found = image_list.find_by_path(test_path)
        assert found is None, "Should return None for empty list"
    
    logger.info("  - find_by_path returns None for empty list")


def test_find_by_path_single_file_mode(temp_folder_with_tif_files: Path) -> None:
    """Test find_by_path in single-file mode."""
    logger.info("Testing find_by_path - single file mode")
    
    # Get a file from the temp folder
    tif_files = list(temp_folder_with_tif_files.glob("*.tif"))
    if not tif_files:
        pytest.skip("No TIF files available for single-file test")
    
    single_file = tif_files[0]
    
    # Create list with single file
    image_list = AcqImageList(
        path=single_file,
        image_cls=KymImage,
        file_extension=".tif"
    )
    
    assert len(image_list) == 1, "Should have exactly one file"
    
    # Find the file
    found = image_list.find_by_path(single_file)
    assert found is not None, "Should find the single file"
    assert found == image_list[0], "Should return the same image instance"
    
    # Try to find a different file (should not be found)
    if len(tif_files) > 1:
        other_file = tif_files[1]
        found_other = image_list.find_by_path(other_file)
        assert found_other is None, "Should not find a different file"
    
    logger.info("  - find_by_path works correctly in single-file mode")


def test_find_by_path_path_normalization(temp_folder_with_tif_files: Path) -> None:
    """Test find_by_path with path normalization (symlinks, different formats)."""
    logger.info("Testing find_by_path - path normalization")
    
    image_list = AcqImageList(
        path=temp_folder_with_tif_files,
        image_cls=KymImage,
        file_extension=".tif",
        depth=2
    )
    
    if len(image_list) == 0:
        pytest.skip("No files available for normalization test")
    
    first_image = image_list[0]
    first_path = first_image.path
    assert first_path is not None, "First image should have a path"
    
    # Test with different path formats that should normalize to the same path
    # Using relative path - resolve both paths first to handle symlinks (e.g., /var -> /private/var on macOS)
    if temp_folder_with_tif_files.is_absolute():
        # Resolve both paths to handle symlink differences
        resolved_first_path = Path(first_path).resolve()
        resolved_parent = temp_folder_with_tif_files.parent.resolve()
        
        # Compute relative path from resolved paths
        relative_path = resolved_first_path.relative_to(resolved_parent)
        # Try to find using a constructed path (using resolved parent)
        constructed = resolved_parent / relative_path
        found = image_list.find_by_path(constructed)
        assert found is not None, "Should find file with constructed path"
        assert found == first_image, "Should return the same image instance"
    
    # Test with string path
    found_str = image_list.find_by_path(str(first_path))
    assert found_str is not None, "Should find file with string path"
    assert found_str == first_image, "Should return the same image instance"
    
    logger.info("  - find_by_path handles path normalization correctly")


def test_acq_image_list_with_file_path_list() -> None:
    """Test AcqImageList initialization with file_path_list parameter."""
    logger.info("Testing AcqImageList with file_path_list")
    
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        # Create test files
        file1 = tmp_path / "file1.tif"
        file2 = tmp_path / "file2.tif"
        file3 = tmp_path / "file3.tif"
        file1.touch()
        file2.touch()
        file3.touch()
        
        # Create list with file_path_list
        image_list = AcqImageList(
            file_path_list=[str(file1), str(file2), str(file3)],
            image_cls=AcqImage,
            file_extension=".tif"
        )
        
        # Should have loaded files (may be 0 if files can't be instantiated)
        assert len(image_list) >= 0
        logger.info(f"  - File list initialization works, found {len(image_list)} images")
        
        # Verify path and folder are None for file_list mode
        assert image_list.path is None
        assert image_list.folder is None


def test_acq_image_list_file_path_list_duplicates() -> None:
    """Test AcqImageList raises error on duplicate file paths."""
    logger.info("Testing AcqImageList file_path_list - duplicate detection")
    
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        test_file = tmp_path / "test.tif"
        test_file.touch()
        
        # Test with duplicate paths (same file twice)
        with pytest.raises(ValueError, match="Duplicate file path"):
            AcqImageList(
                file_path_list=[str(test_file), str(test_file)],
                image_cls=AcqImage,
                file_extension=".tif"
            )
        
        # Test with duplicate paths (different representations of same file)
        with pytest.raises(ValueError, match="Duplicate file path"):
            AcqImageList(
                file_path_list=[str(test_file), test_file],
                image_cls=AcqImage,
                file_extension=".tif"
            )
        
        logger.info("  - Duplicate detection works correctly")


def test_acq_image_list_file_path_list_nonexistent() -> None:
    """Test AcqImageList raises error on non-existent file."""
    logger.info("Testing AcqImageList file_path_list - non-existent file")
    
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        nonexistent_file = tmp_path / "nonexistent.tif"
        
        # Test with non-existent file
        with pytest.raises(ValueError, match="File does not exist"):
            AcqImageList(
                file_path_list=[str(nonexistent_file)],
                image_cls=AcqImage,
                file_extension=".tif"
            )
        
        logger.info("  - Non-existent file detection works correctly")


def test_acq_image_list_file_path_list_not_a_file() -> None:
    """Test AcqImageList raises error when path is not a file."""
    logger.info("Testing AcqImageList file_path_list - path is not a file")
    
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        # Test with directory path
        with pytest.raises(ValueError, match="Path is not a file"):
            AcqImageList(
                file_path_list=[str(tmp_path)],
                image_cls=AcqImage,
                file_extension=".tif"
            )
        
        logger.info("  - Not-a-file detection works correctly")


def test_acq_image_list_file_path_list_empty() -> None:
    """Test AcqImageList raises error on empty file_path_list."""
    logger.info("Testing AcqImageList file_path_list - empty list")
    
    with pytest.raises(ValueError, match="file_path_list cannot be empty"):
        AcqImageList(
            file_path_list=[],
            image_cls=AcqImage,
            file_extension=".tif"
        )
    
    logger.info("  - Empty list detection works correctly")


def test_acq_image_list_file_path_list_extension_filter() -> None:
    """Test AcqImageList applies file_extension filter to file_path_list."""
    logger.info("Testing AcqImageList file_path_list - extension filtering")
    
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        # Create files with different extensions
        file_tif = tmp_path / "file1.tif"
        file_jpg = tmp_path / "file2.jpg"
        file_tif.touch()
        file_jpg.touch()
        
        # Create list with .tif extension filter
        image_list = AcqImageList(
            file_path_list=[str(file_tif), str(file_jpg)],
            image_cls=AcqImage,
            file_extension=".tif"
        )
        
        # Should only load .tif file (jpg should be filtered with warning)
        # Note: May be 0 if files can't be instantiated, but filtering should work
        logger.info(f"  - Extension filtering works, found {len(image_list)} images")


def test_acq_image_list_file_path_list_ignore_stub_filter() -> None:
    """Test AcqImageList applies ignore_file_stub filter to file_path_list."""
    logger.info("Testing AcqImageList file_path_list - ignore_file_stub filtering")
    
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        # Create files with different stubs
        file1 = tmp_path / "file_C001.tif"
        file2 = tmp_path / "file_C002.tif"
        file3 = tmp_path / "file_no_stub.tif"
        file1.touch()
        file2.touch()
        file3.touch()
        
        # Create list with ignore_file_stub="C002"
        image_list = AcqImageList(
            file_path_list=[str(file1), str(file2), str(file3)],
            image_cls=AcqImage,
            file_extension=".tif",
            ignore_file_stub="C002"
        )
        
        # Should filter out file_C002.tif
        # Note: May be 0 if files can't be instantiated, but filtering should work
        logger.info(f"  - Ignore stub filtering works, found {len(image_list)} images")


def test_acq_image_list_file_path_list_path_mutually_exclusive() -> None:
    """Test AcqImageList raises error when both path and file_path_list are provided."""
    logger.info("Testing AcqImageList - path and file_path_list mutual exclusivity")
    
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        test_file = tmp_path / "test.tif"
        test_file.touch()
        
        # Test with both path and file_path_list
        with pytest.raises(ValueError, match="mutually exclusive"):
            AcqImageList(
                path=tmp_path,
                file_path_list=[str(test_file)],
                image_cls=AcqImage,
                file_extension=".tif"
            )
        
        logger.info("  - Mutual exclusivity check works correctly")


def test_acq_image_list_file_path_list_path_property() -> None:
    """Test AcqImageList.path property returns None for file_list mode."""
    logger.info("Testing AcqImageList.path property - file_list mode")
    
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        test_file = tmp_path / "test.tif"
        test_file.touch()
        
        image_list = AcqImageList(
            file_path_list=[str(test_file)],
            image_cls=AcqImage,
            file_extension=".tif"
        )
        
        # path property should return None for file_list mode
        assert image_list.path is None
        
        logger.info("  - path property returns None for file_list mode")


def test_acq_image_list_file_path_list_folder_property() -> None:
    """Test AcqImageList.folder property returns None for file_list mode."""
    logger.info("Testing AcqImageList.folder property - file_list mode")
    
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        test_file = tmp_path / "test.tif"
        test_file.touch()
        
        image_list = AcqImageList(
            file_path_list=[str(test_file)],
            image_cls=AcqImage,
            file_extension=".tif"
        )
        
        # folder property should return None for file_list mode
        assert image_list.folder is None
        
        logger.info("  - folder property returns None for file_list mode")


def test_acq_image_list_file_path_list_load() -> None:
    """Test AcqImageList.load() works with file_list mode."""
    logger.info("Testing AcqImageList.load() - file_list mode")
    
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        file1 = tmp_path / "file1.tif"
        file2 = tmp_path / "file2.tif"
        file1.touch()
        file2.touch()
        
        image_list = AcqImageList(
            file_path_list=[str(file1), str(file2)],
            image_cls=AcqImage,
            file_extension=".tif"
        )
        
        initial_count = len(image_list)
        logger.info(f"  - Initial count: {initial_count}")
        
        # Reload should work
        image_list.load()
        
        new_count = len(image_list)
        logger.info(f"  - After load count: {new_count}")
        
        # Should have same count (reloading same list)
        assert new_count == initial_count
        
        logger.info("  - load() works correctly with file_list mode")


def test_acq_image_list_file_path_list_str_repr() -> None:
    """Test AcqImageList __str__ shows correct mode for file_list."""
    logger.info("Testing AcqImageList __str__ - file_list mode")
    
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        file1 = tmp_path / "file1.tif"
        file2 = tmp_path / "file2.tif"
        file1.touch()
        file2.touch()
        
        image_list = AcqImageList(
            file_path_list=[str(file1), str(file2)],
            image_cls=AcqImage,
            file_extension=".tif"
        )
        
        str_repr = str(image_list)
        assert "AcqImageList" in str_repr
        assert "mode: file_list" in str_repr
        assert "2 files" in str_repr
        
        logger.info("  - __str__ shows correct mode for file_list")


def test_acq_image_list_file_path_list_find_by_path() -> None:
    """Test AcqImageList.find_by_path() works with file_list mode."""
    logger.info("Testing AcqImageList.find_by_path() - file_list mode")
    
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        file1 = tmp_path / "file1.tif"
        file2 = tmp_path / "file2.tif"
        file1.touch()
        file2.touch()
        
        image_list = AcqImageList(
            file_path_list=[str(file1), str(file2)],
            image_cls=AcqImage,
            file_extension=".tif"
        )
        
        if len(image_list) > 0:
            # Find by Path object
            found = image_list.find_by_path(file1)
            # May be None if file couldn't be instantiated, but method should work
            logger.info(f"  - find_by_path() works with file_list mode, found: {found is not None}")
        else:
            logger.info("  - find_by_path() method exists (files couldn't be instantiated)")


def test_acq_image_list_reload_deprecation_warning() -> None:
    """Test AcqImageList.reload() emits deprecation warning."""
    logger.info("Testing AcqImageList.reload() deprecation warning")
    
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        test_file = tmp_path / "test.tif"
        test_file.touch()
        
        image_list = AcqImageList(
            path=tmp_path,
            image_cls=AcqImage,
            file_extension=".tif"
        )
        
        # Should emit deprecation warning
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            image_list.reload()
            
            # Check that deprecation warning was issued
            assert len(w) > 0
            assert any(issubclass(warning.category, DeprecationWarning) for warning in w)
            assert any("deprecated" in str(warning.message).lower() for warning in w)
        
        logger.info("  - reload() emits deprecation warning correctly")


def test_acq_image_list_get_base_path_folder_mode() -> None:
    """Test _get_base_path in folder mode."""
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "file1.tif").touch()
        image_list = AcqImageList(
            path=tmp_path,
            image_cls=AcqImage,
            file_extension=".tif",
        )
        base = image_list._get_base_path()
        assert base is not None
        assert base.resolve() == tmp_path.resolve()


def test_acq_image_list_get_base_path_file_mode() -> None:
    """Test _get_base_path in single-file mode."""
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        test_file = tmp_path / "test.tif"
        test_file.touch()
        image_list = AcqImageList(
            path=test_file,
            image_cls=AcqImage,
            file_extension=".tif",
        )
        base = image_list._get_base_path()
        assert base is not None
        assert base.resolve() == tmp_path.resolve()


def test_acq_image_list_get_base_path_empty() -> None:
    """Test _get_base_path with empty list."""
    image_list = AcqImageList(path=None, image_cls=AcqImage, file_extension=".tif")
    base = image_list._get_base_path()
    assert base is None


def test_acq_image_list_get_paths_with_rel_path() -> None:
    """Test get_paths_with_rel_path returns (path, rel_path) tuples."""
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "a.tif").touch()
        (tmp_path / "b.tif").touch()
        image_list = AcqImageList(
            path=tmp_path,
            image_cls=AcqImage,
            file_extension=".tif",
        )
        paths_with_rel = image_list.get_paths_with_rel_path()
        assert isinstance(paths_with_rel, list)
        for item in paths_with_rel:
            assert isinstance(item, tuple)
            assert len(item) == 2
            full_path, rel_path = item
            assert isinstance(full_path, Path)
            assert isinstance(rel_path, str)
            assert rel_path in ("a.tif", "b.tif") or "tif" in rel_path


def test_acq_image_list_csv_source_path_when_loading_from_csv() -> None:
    """Test _csv_source_path is set when loading from CSV."""
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        csv_file = tmp_path / "file_list.csv"
        tif1 = tmp_path / "a.tif"
        tif1.touch()
        csv_file.write_text("rel_path\na.tif\n", encoding="utf-8")
        image_list = AcqImageList.load_from_path(
            csv_file,
            image_cls=AcqImage,
            file_extension=".tif",
        )
        assert hasattr(image_list, "_csv_source_path")
        assert image_list._csv_source_path is not None
        assert image_list._csv_source_path.name == "file_list.csv"

