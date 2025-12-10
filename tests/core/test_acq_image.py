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

from kymflow.core.image_loaders.acq_image import AcqImage, AcqImageHeader
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
@pytest.mark.skip(reason="no way of currently testing this")
def test_acq_image_from_tif_path_without_loading(sample_tif_files: list[Path]) -> None:
    """Test AcqImage initialization with TIFF path but without loading image data."""
    if not sample_tif_files:
        pytest.skip("No test data files available")
    
    logger.info("Testing AcqImage with TIFF path (load_image=False)")
    
    for tif_file in sample_tif_files:
        logger.info(f"Testing with file: {tif_file.name}")
        
        acq = AcqImage(path=tif_file, load_image=False)
        
        # Path should be set
        assert acq.path == Path(tif_file)
        logger.info(f"  - Path: {acq.path}")
        
        # Image data should not be loaded
        assert acq.img_data is None
        logger.info("  - Image data not loaded (as expected)")
        
        # Shape should be None when image is not loaded
        assert acq.shape is None
        logger.info("  - Shape is None (as expected)")
        
        # Header should be attempted to load (may fail if TIFF doesn't have proper description)
        assert acq.header is not None
        logger.info(f"  - Header: x_pixels={acq.header.x_pixels}, y_pixels={acq.header.y_pixels}, z_pixels={acq.header.z_pixels}")


@pytest.mark.requires_data
def test_acq_image_from_tif_path_with_loading(sample_tif_files: list[Path]) -> None:
    """Test AcqImage initialization with TIFF path and loading image data."""
    if not sample_tif_files:
        pytest.skip("No test data files available")
    
    logger.info("Testing AcqImage with TIFF path (load_image=True)")
    
    for tif_file in sample_tif_files:
        logger.info(f"Testing with file: {tif_file.name}")
        
        acq = AcqImage(path=tif_file, load_image=True)
        
        # Path should be set
        assert acq.path == Path(tif_file)
        logger.info(f"  - Path: {acq.path}")
        
        # Image data should be loaded
        assert acq.img_data is not None
        logger.info(f"  - Image data loaded, dtype: {acq.img_data.dtype}")
        
        # Shape should be available
        assert acq.shape is not None
        assert len(acq.shape) == 3  # Should always be 3D after loading
        logger.info(f"  - Shape: {acq.shape}")
        
        # Properties should work
        assert acq.x_pixels > 0
        assert acq.y_pixels > 0
        assert acq.z_pixels > 0
        logger.info(f"  - x_pixels: {acq.x_pixels}, y_pixels: {acq.y_pixels}, z_pixels: {acq.z_pixels}")
        
        # Header should be loaded
        assert acq.header is not None
        logger.info(f"  - Header: x_pixels={acq.header.x_pixels}, y_pixels={acq.header.y_pixels}, z_pixels={acq.header.z_pixels}")


def test_acq_image_from_synthetic_2d() -> None:
    """Test AcqImage with synthetic 2D numpy array."""
    logger.info("Testing AcqImage with synthetic 2D data")
    
    # Create a 2D synthetic image
    img_2d = np.random.randint(0, 255, size=(100, 200), dtype=np.uint8)
    logger.info(f"== Created 2D array with shape: {img_2d.shape}")
    
    acq = AcqImage(path=None, img_data=img_2d, load_image=False)
    
    # Image data should be set
    assert acq.img_data is not None
    logger.info(f"  - Image data shape: {acq.img_data.shape}")
    
    # Shape should be 3D (2D gets converted to 3D)
    assert acq.shape is not None
    assert len(acq.shape) == 3
    assert acq.shape == (1, 100, 200)  # Should have z=1, y=100, x=200
    logger.info(f"  - Shape after conversion: {acq.shape}")
    
    # Properties should work
    assert acq.x_pixels == 100
    assert acq.y_pixels == 200
    assert acq.z_pixels == 1
    logger.info(f"  - x_pixels: {acq.x_pixels}, y_pixels: {acq.y_pixels}, z_pixels: {acq.z_pixels}")
    
    # Header should be created from image data
    assert acq.header is not None
    assert acq.header.x_pixels == 100
    assert acq.header.y_pixels == 200
    assert acq.header.z_pixels == 1
    logger.info("  - Header matches image data shape")


def test_acq_image_from_synthetic_3d() -> None:
    """Test AcqImage with synthetic 3D numpy array."""
    logger.info("Testing AcqImage with synthetic 3D data")
    
    # Create a 3D synthetic image (z, y, x)
    img_3d = np.random.randint(0, 255, size=(10, 100, 200), dtype=np.uint8)
    logger.info(f"== Created 3D array with shape: {img_3d.shape}")
    
    acq = AcqImage(path=None, img_data=img_3d, load_image=False)
    
    # Image data should be set
    assert acq.img_data is not None
    logger.info(f"  - Image data shape: {acq.img_data.shape}")
    
    # Shape should be 3D
    assert acq.shape is not None
    assert len(acq.shape) == 3
    assert acq.shape == (10, 100, 200)  # Should remain 3D
    logger.info(f"  - Shape: {acq.shape}")
    
    # Properties should work
    assert acq.x_pixels == 100
    assert acq.y_pixels == 200
    assert acq.z_pixels == 10
    logger.info(f"  - x_pixels: {acq.x_pixels}, y_pixels: {acq.y_pixels}, z_pixels: {acq.z_pixels}")
    
    # Header should be created from image data
    assert acq.header is not None
    assert acq.header.x_pixels == 100
    assert acq.header.y_pixels == 200
    assert acq.header.z_pixels == 10
    logger.info("  - Header matches image data shape")


def test_acq_image_from_synthetic_4d_raises_error() -> None:
    """Test that AcqImage raises ValueError for 4D numpy arrays when loading from file."""
    logger.info("Testing AcqImage with synthetic 4D data (should raise error)")
    
    # Create a 4D synthetic image
    img_4d = np.random.randint(0, 255, size=(5, 10, 100, 200), dtype=np.uint8)
    logger.info(f"==Created 4D array with shape: {img_4d.shape}")
    
    # Test loading 4D data from a file - this should raise ValueError
    import tempfile
    import tifffile
    
    with tempfile.NamedTemporaryFile(suffix='.tif', delete=False) as tmp_file:
        tmp_path = Path(tmp_file.name)
        tifffile.imwrite(tmp_path, img_4d)
        
        logger.info(f"== Created temporary 4D TIFF file: {tmp_path}")
        
        # Loading should raise ValueError
        with pytest.raises(ValueError, match="Image data must be 2D or 3D"):
            _ = AcqImage(path=tmp_path, load_image=True)  # Should raise ValueError
            logger.info("  - ValueError raised as expected")
        
        # Clean up
        tmp_path.unlink()
        logger.info("  - Temporary file cleaned up")


def test_acq_image_header_from_img_data() -> None:
    """Test AcqImageHeader.from_img_data method."""
    logger.info("Testing AcqImageHeader.from_img_data")
    
    # Test with 2D data
    img_2d = np.random.randint(0, 255, size=(100, 200), dtype=np.uint8)
    header_2d = AcqImageHeader.from_img_data(img_2d)
    assert header_2d.x_pixels == 200
    assert header_2d.y_pixels == 100
    assert header_2d.z_pixels == 1
    logger.info(f"  - 2D data: x={header_2d.x_pixels}, y={header_2d.y_pixels}, z={header_2d.z_pixels}")
    
    # Test with 3D data
    img_3d = np.random.randint(0, 255, size=(10, 100, 200), dtype=np.uint8)
    header_3d = AcqImageHeader.from_img_data(img_3d)
    assert header_3d.x_pixels == 100
    assert header_3d.y_pixels == 200
    assert header_3d.z_pixels == 10
    logger.info(f"  - 3D data: x={header_3d.x_pixels}, y={header_3d.y_pixels}, z={header_3d.z_pixels}")


@pytest.mark.skip(reason="no way of currently testing this")
def test_acq_image_no_path_no_data() -> None:
    """Test AcqImage with neither path nor image data."""
    logger.info("Testing AcqImage with no path and no image data")
    
    acq = AcqImage(path=None, img_data=None, load_image=False)
    
    # Path should be None
    assert acq.path is None
    logger.info("  - Path is None")
    
    # Image data should be None
    assert acq.img_data is None
    logger.info("  - Image data is None")
    
    # Shape should be None
    assert acq.shape is None
    logger.info("  - Shape is None")
    
    # Header should have default values
    assert acq.header is not None
    assert acq.header.x_pixels == 0
    assert acq.header.y_pixels == 0
    assert acq.header.z_pixels == 0
    logger.info("  - Header has default values")


def test_acq_image_properties_with_loaded_data() -> None:
    """Test AcqImage properties when image data is loaded."""
    logger.info("Testing AcqImage properties with loaded data")
    
    # Create 3D synthetic image
    img_3d = np.random.randint(0, 255, size=(5, 50, 100), dtype=np.uint8)
    logger.info(f"== Created 3D array with shape: {img_3d.shape}")
    
    acq = AcqImage(path=None, img_data=img_3d, load_image=False)
    logger.info(f"  created AcqImage: {acq}")
    
    # Test shape property
    assert acq.shape == (5, 50, 100)
    logger.info(f"  - shape: {acq.shape}")
    
    # Test x_pixels, y_pixels, z_pixels properties
    assert acq.x_pixels == 50
    assert acq.y_pixels == 100
    assert acq.z_pixels == 5
    logger.info(f"  - x_pixels: {acq.x_pixels}, y_pixels: {acq.y_pixels}, z_pixels: {acq.z_pixels}")
    
    # Test header property
    assert acq.header is not None
    assert isinstance(acq.header, AcqImageHeader)
    logger.info(f"  - header type: {type(acq.header)}")
    
    # Test img_data property
    assert acq.img_data is not None
    assert np.array_equal(acq.img_data, img_3d)
    logger.info("  - img_data matches input data")

