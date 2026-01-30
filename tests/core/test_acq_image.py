"""Unit tests for AcqImage class.

Tests AcqImage with various data sources:
- TIFF files from test data directory
- Synthetic 2D numpy arrays
- Synthetic 3D numpy arrays
- Synthetic 4D numpy arrays (should raise error)
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from kymflow.core.image_loaders.acq_image import AcqImage
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


@pytest.mark.requires_data
def test_acq_image_from_tif_path_without_loading(sample_tif_files: list[Path]) -> None:
    """Test AcqImage initialization with TIFF path but without loading image data.
    
    Note: AcqImage base class no longer loads files - that's done by derived classes like KymImage.
    This test verifies that path is stored but image data is not loaded.
    """
    if not sample_tif_files:
        pytest.skip("No test data files available")
    
    logger.info("Testing AcqImage with TIFF path (no loading in base class)")
    
    for tif_file in sample_tif_files:
        logger.info(f"Testing with file: {tif_file.name}")
        
        acqImage = AcqImage(path=tif_file)
        
        # Path should be stored in _file_path_dict
        assert acqImage.getChannelPath(1) == Path(tif_file)
        logger.info(f"  - Path: {acqImage.getChannelPath(1)}")
        
        # Image data should not be loaded (base class doesn't load files)
        assert acqImage.getChannelData(1) is None
        logger.info("  - Image data not loaded (as expected - base class doesn't load files)")
        
        # Shape should be None when image is not loaded
        assert acqImage.img_shape is None
        logger.info("  - Shape is None (as expected)")
        
        # header.voxels and header.labels should be set to None
        assert acqImage.header.voxels is None
        assert acqImage.header.labels is None


def test_acq_image_from_synthetic_2d() -> None:
    """Test AcqImage with synthetic 2D numpy array."""
    logger.info("Testing AcqImage with synthetic 2D data")
    
    # Create a 2D synthetic image
    img_2d = np.random.randint(0, 255, size=(100, 200), dtype=np.uint8)
    logger.info(f"== Created 2D array with shape: {img_2d.shape}")
    
    acqImage = AcqImage(path=None, img_data=img_2d)
    
    # Image data should be set
    channel_data = acqImage.getChannelData(1)
    assert channel_data is not None
    logger.info(f"  - Image data shape: {channel_data.shape}")
    
    # Shape should be 3D (2D gets converted to 3D)
    assert acqImage.img_shape is not None
    assert len(acqImage.img_shape) == 2
    assert acqImage.img_shape == (100, 200)  #
    logger.info(f"  - Shape after conversion: {acqImage.img_shape}")
    
    # Properties should work
    assert acqImage.img_shape[0] == 100
    assert acqImage.img_shape[1] == 200
    logger.info(f"  - img_shape: {acqImage.img_shape}")
    
    # Header should be created from image data
    assert acqImage.header.voxels is not None
    assert acqImage.header.labels is not None
    assert len(acqImage.header.voxels) == acqImage.img_ndim
    assert len(acqImage.header.labels) == acqImage.img_ndim
    assert acqImage.header.voxels[0] == 1.0
    assert acqImage.header.voxels[1] == 1.0
    assert acqImage.header.labels[0] == ""
    assert acqImage.header.labels[1] == ""
    logger.info(f"  - header.voxels: {acqImage.header.voxels}, header.labels: {acqImage.header.labels}")


def test_acq_image_from_synthetic_3d() -> None:
    """Test AcqImage with synthetic 3D numpy array."""
    logger.info("Testing AcqImage with synthetic 3D data")
    
    # Create a 3D synthetic image (z, y, x)
    img_3d = np.random.randint(0, 255, size=(10, 100, 200), dtype=np.uint8)
    logger.info(f"== Created 3D array with shape: {img_3d.shape}")
    
    acqImage = AcqImage(path=None, img_data=img_3d)
    
    # Image data should be set
    channel_data = acqImage.getChannelData(1)
    assert channel_data is not None
    logger.info(f"  - Image data shape: {channel_data.shape}")
    
    # Shape should be 3D
    assert acqImage.img_shape is not None
    assert len(acqImage.img_shape) == 3
    assert acqImage.img_shape == (10, 100, 200)  # Should remain 3D
    logger.info(f"  - Shape: {acqImage.img_shape}")
    
    # Properties should work
    assert acqImage.img_shape[0] == 10
    assert acqImage.img_shape[1] == 100
    assert acqImage.img_shape[2] == 200
    logger.info(f"  - img_shape: {acqImage.img_shape}")
    
    # Header should be created from image data
    assert acqImage.header.voxels is not None
    assert acqImage.header.labels is not None
    assert len(acqImage.header.voxels) == acqImage.img_ndim
    assert len(acqImage.header.labels) == acqImage.img_ndim
    assert acqImage.header.voxels[0] == 1.0
    assert acqImage.header.voxels[1] == 1.0
    assert acqImage.header.voxels[2] == 1.0
    assert acqImage.header.labels[0] == ""
    assert acqImage.header.labels[1] == ""
    assert acqImage.header.labels[2] == ""
    logger.info(f"  - header.voxels: {acqImage.header.voxels}, header.labels: {acqImage.header.labels}")


def test_acq_image_from_synthetic_4d_raises_error() -> None:
    """Test that AcqImage raises ValueError for 4D numpy arrays when passed via img_data."""
    logger.info("Testing AcqImage with synthetic 4D data (should raise error)")
    
    # Create a 4D synthetic image
    img_4d = np.random.randint(0, 255, size=(5, 10, 100, 200), dtype=np.uint8)
    logger.info(f"==Created 4D array with shape: {img_4d.shape}")
    
    # Test passing 4D data directly via img_data - this should raise ValueError
    with pytest.raises(ValueError, match="Image data must be 2D or 3D"):
        _ = AcqImage(path=None, img_data=img_4d)  # Should raise ValueError
        logger.info("  - ValueError raised as expected")


def test_acq_image_no_path_no_data() -> None:
    """Test that AcqImage raises ValueError when neither path nor image data is provided."""
    logger.info("Testing AcqImage with no path and no image data (should raise ValueError)")
    
    # Should raise ValueError when both path and img_data are None
    with pytest.raises(ValueError, match="Either path or img_data must be provided"):
        _ = AcqImage(path=None, img_data=None)
        logger.info("  - ValueError raised as expected")

def test_acq_image_properties_with_loaded_data() -> None:
    """Test AcqImage properties when image data is loaded."""
    logger.info("Testing AcqImage properties with loaded data")
    
    # Create 3D synthetic image
    img_3d = np.random.randint(0, 255, size=(5, 50, 100), dtype=np.uint8)
    logger.info(f"== Created 3D array with shape: {img_3d.shape}")
    
    acq = AcqImage(path=None, img_data=img_3d)
    logger.info(f"  created AcqImage: {acq}")
    
    # Test shape property
    assert acq.img_shape == (5, 50, 100)
    logger.info(f"  - img_shape: {acq.img_shape}")
    
    # Test x_pixels, y_pixels, z_pixels properties
    assert acq.img_shape[0] == 5
    assert acq.img_shape[1] == 50
    assert acq.img_shape[2] == 100
    logger.info(f"  - img_shape: {acq.img_shape}")
    
    # Test header.voxels and header.labels properties
    assert acq.header.voxels is not None
    assert acq.header.voxels == [1.0, 1.0, 1.0]
    assert acq.header.labels == ["", "", ""]
    logger.info(f"  - header.voxels: {acq.header.voxels}, header.labels: {acq.header.labels}")


def test_get_channel_keys_no_channels() -> None:
    """Test getChannelKeys() when no channels exist."""
    logger.info("Testing getChannelKeys() with no channels")
    
    # Create AcqImage with path but don't load (base class doesn't load files)
    # Note: Even without loaded data, getChannelKeys() returns [1] because the path
    # is stored in _file_path_dict with channel 1 as the default (hypothetical channel)
    acq = AcqImage(path=Path("/fake/path.tif"))
    
    # Returns [1] because path is stored with default channel 1, even if not loaded
    keys = acq.getChannelKeys()
    assert keys == [1]
    logger.info(f"  - Channel keys: {keys}")


def test_get_channel_keys_single_channel() -> None:
    """Test getChannelKeys() with a single channel."""
    logger.info("Testing getChannelKeys() with single channel")
    
    # Create 2D synthetic image
    img_2d = np.random.randint(0, 255, size=(100, 200), dtype=np.uint8)
    acq = AcqImage(path=None, img_data=img_2d)
    
    # Should return list with channel 1
    keys = acq.getChannelKeys()
    assert keys == [1]
    logger.info(f"  - Channel keys: {keys}")


def test_get_channel_keys_multiple_channels() -> None:
    """Test getChannelKeys() with multiple channels."""
    logger.info("Testing getChannelKeys() with multiple channels")
    
    # Create 2D synthetic image for first channel
    img_2d_1 = np.random.randint(0, 255, size=(100, 200), dtype=np.uint8)
    acq = AcqImage(path=None, img_data=img_2d_1)
    
    # Add second channel
    img_2d_2 = np.random.randint(0, 255, size=(100, 200), dtype=np.uint8)
    acq.addColorChannel(2, img_2d_2)
    
    # Add third channel
    img_2d_3 = np.random.randint(0, 255, size=(100, 200), dtype=np.uint8)
    acq.addColorChannel(3, img_2d_3)
    
    # Should return list with channels 1, 2, 3
    keys = acq.getChannelKeys()
    assert set(keys) == {1, 2, 3}
    assert len(keys) == 3
    logger.info(f"  - Channel keys: {keys}")


@pytest.mark.requires_data
def test_get_channel_keys_after_loading(data_dir: Path) -> None:
    """Test getChannelKeys() after adding image data.
    
    Note: AcqImage base class no longer loads files - that's done by derived classes.
    This test verifies getChannelKeys() works with manually added data.
    """
    logger.info("Testing getChannelKeys() after adding image data")
    
    # Create synthetic image
    img_2d = np.random.randint(0, 255, size=(100, 200), dtype=np.uint8)
    acq = AcqImage(path=None, img_data=img_2d)
    
    # Should have at least channel 1
    keys = acq.getChannelKeys()
    assert 1 in keys
    assert len(keys) >= 1
    logger.info(f"  - Channel keys: {keys}")


def test_acq_image_header_property() -> None:
    """Test header property access."""
    logger.info("Testing AcqImage header property")
    
    # Create 2D synthetic image
    img_2d = np.random.randint(0, 255, size=(100, 200), dtype=np.uint8)
    acq = AcqImage(path=None, img_data=img_2d)
    
    # Header should be accessible
    assert acq.header is not None
    assert acq.header.shape == (100, 200)
    assert acq.header.ndim == 2
    assert acq.header.voxels == [1.0, 1.0]
    assert acq.header.labels == ["", ""]
    logger.info(f"  - header.shape: {acq.header.shape}")
    logger.info(f"  - header.ndim: {acq.header.ndim}")


def test_acq_image_getRowDict_with_path() -> None:
    """Test getRowDict() with a path that has parent folders."""
    logger.info("Testing AcqImage getRowDict() with path")
    
    # Create a path with multiple parent folders
    # Use a temporary path structure for testing
    test_path = Path("/a/b/c/test_file.tif")
    
    # Create AcqImage with path (but no data)
    acq = AcqImage(path=test_path)
    
    # Get row dict
    row_dict = acq.getRowDict()
    
    # Check file info
    assert row_dict['path'] == str(test_path)
    assert row_dict['filename'] == "test_file.tif"
    
    # Check parent folders (from path parts: /a/b/c/test_file.tif)
    # parts[-1] = test_file.tif, parts[-2] = c, parts[-3] = b, parts[-4] = a
    assert row_dict['parent1'] == "c"
    assert row_dict['parent2'] == "b"
    assert row_dict['parent3'] == "a"
    
    # Check header fields
    assert row_dict['ndim'] is None  # No data loaded
    assert row_dict['shape'] is None
    assert row_dict['voxels'] is None
    assert row_dict['voxels_units'] is None
    assert row_dict['labels'] is None
    assert row_dict['physical_size'] is None
    
    logger.info(f"  - getRowDict(): {row_dict}")


def test_acq_image_getRowDict_with_data() -> None:
    """Test getRowDict() with image data loaded."""
    logger.info("Testing AcqImage getRowDict() with data")
    
    # Create 2D synthetic image
    img_2d = np.random.randint(0, 255, size=(50, 75), dtype=np.uint8)
    acq = AcqImage(path=None, img_data=img_2d)
    
    # Get row dict
    row_dict = acq.getRowDict()
    
    # Check file info (no path, so should be None)
    assert row_dict['path'] is None
    assert row_dict['filename'] is None
    assert row_dict['parent1'] is None
    assert row_dict['parent2'] is None
    assert row_dict['parent3'] is None
    
    # Check header fields (should be populated from data)
    assert row_dict['ndim'] == 2
    assert row_dict['shape'] == (50, 75)
    assert row_dict['voxels'] == [1.0, 1.0]
    assert row_dict['voxels_units'] == ["px", "px"]
    assert row_dict['labels'] == ["", ""]
    assert row_dict['physical_size'] == [50.0, 75.0]
    
    logger.info(f"  - getRowDict(): {row_dict}")


def test_acq_image_getRowDict_shallow_path() -> None:
    """Test getRowDict() with a path that has fewer than 3 parent folders."""
    logger.info("Testing AcqImage getRowDict() with shallow path")
    
    # Create a path with only 1 parent folder
    test_path = Path("/a/test_file.tif")
    acq = AcqImage(path=test_path)
    
    row_dict = acq.getRowDict()
    
    # Should have parent1, but parent2 and parent3 should be None
    assert row_dict['parent1'] == "a"
    assert row_dict['parent2'] is None
    assert row_dict['parent3'] is None
    
    logger.info(f"  - getRowDict() with shallow path: parent1={row_dict['parent1']}, parent2={row_dict['parent2']}, parent3={row_dict['parent3']}")


def test_acq_image_metadata_dirty_flag() -> None:
    """Test that metadata dirty flag is set correctly."""
    logger.info("Testing AcqImage metadata dirty flag")
    
    test_image = np.zeros((100, 200), dtype=np.uint8)
    acq = AcqImage(path=None, img_data=test_image)
    
    # Initially should not be dirty
    assert acq.is_metadata_dirty is False
    
    # Update experiment metadata - should mark as dirty
    acq.update_experiment_metadata(species="mouse")
    assert acq.is_metadata_dirty is True
    
    # Update header - should still be dirty
    acq.update_header(voxels=[0.001, 0.284])
    assert acq.is_metadata_dirty is True
    
    # Clear dirty flag
    acq.clear_metadata_dirty()
    assert acq.is_metadata_dirty is False
    
    logger.info("  - Metadata dirty flag works correctly")


def test_acq_image_save_metadata_clears_dirty() -> None:
    """Test that save_metadata() clears dirty flag."""
    logger.info("Testing AcqImage save_metadata() clears dirty flag")
    
    from tempfile import TemporaryDirectory
    
    with TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.tif"
        test_image = np.zeros((100, 200), dtype=np.uint8)
        acq = AcqImage(path=test_file, img_data=test_image)
        
        # Update metadata
        acq.update_experiment_metadata(species="mouse", region="cortex")
        assert acq.is_metadata_dirty is True
        
        # Save metadata
        saved = acq.save_metadata()
        assert saved is True
        assert acq.is_metadata_dirty is False
        
        logger.info("  - save_metadata() clears dirty flag correctly")


def test_acq_image_get_dim_arange() -> None:
    """Test get_dim_arange() method for physical unit arrays."""
    logger.info("Testing AcqImage get_dim_arange()")
    
    # Create 2D image with voxel sizes
    test_image = np.zeros((100, 200), dtype=np.uint8)
    acq = AcqImage(path=None, img_data=test_image)
    acq.update_header(voxels=[0.001, 0.284])  # time, space in seconds and microns
    
    # Test dim=0 (time dimension)
    dim0_arange = acq.get_dim_arange(0)
    assert len(dim0_arange) == 100
    assert dim0_arange[0] == 0.0
    assert dim0_arange[1] == 0.001
    assert dim0_arange[99] == 0.099
    
    # Test dim=1 (space dimension)
    dim1_arange = acq.get_dim_arange(1)
    assert len(dim1_arange) == 200
    assert dim1_arange[0] == 0.0
    assert dim1_arange[1] == 0.284
    assert dim1_arange[199] == pytest.approx(199 * 0.284)
    
    # Test error cases
    with pytest.raises(ValueError, match="Cannot get arange for dimension"):
        acq.get_dim_arange(2)  # Invalid dimension
    
    # Test with None shape (need to provide a dummy path since AcqImage requires path or img_data)
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as tmpdir:
        dummy_path = Path(tmpdir) / "dummy.tif"
        dummy_path.touch()
        acq2 = AcqImage(path=dummy_path, img_data=None)
        with pytest.raises(ValueError, match="Cannot get arange for dimension"):
            acq2.get_dim_arange(0)
    
    logger.info("  - get_dim_arange() works correctly")


def test_acq_image_get_image_bounds() -> None:
    """Test get_image_bounds() method."""
    logger.info("Testing AcqImage get_image_bounds()")
    
    # Test 2D image
    test_image_2d = np.zeros((100, 200), dtype=np.uint8)
    acq_2d = AcqImage(path=None, img_data=test_image_2d)
    acq_2d.update_header(shape=(100, 200), ndim=2)
    
    bounds_2d = acq_2d.get_image_bounds()
    assert bounds_2d.width == 200
    assert bounds_2d.height == 100
    assert bounds_2d.num_slices == 1
    
    # Test 3D image
    test_image_3d = np.zeros((50, 100, 200), dtype=np.uint8)
    acq_3d = AcqImage(path=None, img_data=test_image_3d)
    acq_3d.update_header(shape=(50, 100, 200), ndim=3)
    
    bounds_3d = acq_3d.get_image_bounds()
    assert bounds_3d.width == 200
    assert bounds_3d.height == 100
    assert bounds_3d.num_slices == 50
    
    # Test error cases (need to provide a dummy path since AcqImage requires path or img_data)
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as tmpdir:
        dummy_path = Path(tmpdir) / "dummy.tif"
        dummy_path.touch()
        acq_no_shape = AcqImage(path=dummy_path, img_data=None)
        with pytest.raises(ValueError, match="Cannot determine image bounds"):
            acq_no_shape.get_image_bounds()
    
    logger.info("  - get_image_bounds() works correctly")


def test_acq_image_img_num_slices() -> None:
    """Test img_num_slices property."""
    logger.info("Testing AcqImage img_num_slices property")
    
    # Test 2D image
    test_image_2d = np.zeros((100, 200), dtype=np.uint8)
    acq_2d = AcqImage(path=None, img_data=test_image_2d)
    assert acq_2d.img_num_slices == 1
    
    # Test 3D image
    test_image_3d = np.zeros((50, 100, 200), dtype=np.uint8)
    acq_3d = AcqImage(path=None, img_data=test_image_3d)
    assert acq_3d.img_num_slices == 50
    
    # Test with None shape (need to provide a dummy path since AcqImage requires path or img_data)
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as tmpdir:
        dummy_path = Path(tmpdir) / "dummy.tif"
        dummy_path.touch()
        acq_no_shape = AcqImage(path=dummy_path, img_data=None)
        assert acq_no_shape.img_num_slices is None
    
    logger.info("  - img_num_slices property works correctly")


def test_acq_image_get_roi_physical_coords() -> None:
    """Test get_roi_physical_coords() method."""
    logger.info("Testing AcqImage get_roi_physical_coords()")
    
    from kymflow.core.image_loaders.roi import RoiBounds
    
    # Create image with voxel sizes
    test_image = np.zeros((100, 200), dtype=np.uint8)
    acq = AcqImage(path=None, img_data=test_image)
    acq.update_header(voxels=[0.001, 0.284])  # time, space
    
    # Create ROI
    bounds = RoiBounds(dim0_start=10, dim0_stop=50, dim1_start=20, dim1_stop=80)
    roi = acq.rois.create_roi(bounds=bounds)
    
    # Get physical coordinates
    physical_coords = acq.get_roi_physical_coords(roi.id)
    assert physical_coords.dim0_start == pytest.approx(10 * 0.001)
    assert physical_coords.dim0_stop == pytest.approx(50 * 0.001)
    assert physical_coords.dim1_start == pytest.approx(20 * 0.284)
    assert physical_coords.dim1_stop == pytest.approx(80 * 0.284)
    
    # Test error cases
    with pytest.raises(ValueError, match="ROI.*not found"):
        acq.get_roi_physical_coords(999)
    
    # Note: When img_data is provided, addColorChannel() automatically calls
    # init_defaults_from_shape() which sets voxels=[1.0, 1.0] by default.
    # To test the None voxels case, we need to manually clear voxels after creation.
    acq_no_voxels = AcqImage(path=None, img_data=test_image)
    acq_no_voxels._header.voxels = None  # Manually clear voxels to test error case
    acq_no_voxels.rois.create_roi(bounds=bounds)
    with pytest.raises(ValueError, match="header.voxels is None"):
        acq_no_voxels.get_roi_physical_coords(1)
    
    acq_incomplete_voxels = AcqImage(path=None, img_data=test_image)
    acq_incomplete_voxels.update_header(voxels=[0.001])  # Only one dimension
    acq_incomplete_voxels.rois.create_roi(bounds=bounds)
    with pytest.raises(ValueError, match="need at least 2 for 2D coordinates"):
        acq_incomplete_voxels.get_roi_physical_coords(1)
    
    logger.info("  - get_roi_physical_coords() works correctly")

