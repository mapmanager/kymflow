"""Unit tests for KymImage class.

Tests KymImage with various data sources:
- TIFF files with Olympus headers (lazy loading)
- TIFF files with Olympus headers (with loading)
- Synthetic numpy arrays
- Header-based shape/ndim functionality
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

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


@pytest.mark.requires_data
def test_kym_image_from_tif_path_without_loading(sample_tif_files: list[Path]) -> None:
    """Test KymImage initialization with TIFF path but without loading image data.
    
    Should have shape/ndim from Olympus header even when image data is not loaded.
    """
    if not sample_tif_files:
        pytest.skip("No test data files available")
    
    logger.info("Testing KymImage with TIFF path (load_image=False)")
    
    for tif_file in sample_tif_files:
        logger.info(f"Testing with file: {tif_file.name}")
        
        kymImage = KymImage(path=tif_file)
        
        # Path should be stored in _file_path_dict
        assert kymImage.getChannelPath(1) == Path(tif_file)
        logger.info(f"  - Path: {kymImage.getChannelPath(1)}")
        
        # Image data should not be loaded
        assert kymImage.getChannelData(1) is None
        logger.info("  - Image data not loaded (as expected)")
        
        # Shape and ndim should be available from header if Olympus header exists
        # If no header, they will be None (like AcqImage)
        if kymImage.img_shape is not None:
            assert kymImage.img_ndim == 2  # kymographs are always 2D
            assert len(kymImage.img_shape) == 2
            logger.info(f"  - Shape from header: {kymImage.img_shape}")
            logger.info(f"  - NDim from header: {kymImage.img_ndim}")
        else:
            logger.info("  - No header available, shape/ndim are None (as expected)")


@pytest.mark.requires_data
def test_kym_image_from_tif_path_with_loading(sample_tif_files: list[Path]) -> None:
    """Test KymImage initialization with TIFF path and loading image data."""
    if not sample_tif_files:
        pytest.skip("No test data files available")
    
    logger.info("Testing KymImage with TIFF path (load_image=True)")
    
    for tif_file in sample_tif_files:
        logger.info(f"Testing with file: {tif_file.name}")
        
        kymImage = KymImage(path=tif_file, load_image=True)
        
        # Path should be stored in _file_path_dict
        assert kymImage.getChannelPath(1) == Path(tif_file)
        logger.info(f"  - Path: {kymImage.getChannelPath(1)}")
        
        # Image data should be loaded
        channel_data = kymImage.getChannelData(1)
        assert channel_data is not None
        logger.info(f"  - Image data loaded, dtype: {channel_data.dtype}")
        
        # Shape should be available (from header or data)
        assert kymImage.img_shape is not None
        assert kymImage.img_ndim == 2  # kymographs are always 2D
        assert len(kymImage.img_shape) == 2
        logger.info(f"  - Shape: {kymImage.img_shape}")
        
        # If header was loaded, shape should match loaded data
        if kymImage.img_shape is not None and channel_data is not None:
            assert kymImage.img_shape == channel_data.shape
            logger.info("  - Header shape matches loaded data shape")
        
        # Properties should work
        assert kymImage.img_shape[0] > 0
        assert kymImage.img_shape[1] > 0
        logger.info(f"  - img_shape: {kymImage.img_shape}")
        
        # KymImage-specific properties
        assert kymImage.num_lines == kymImage.img_shape[0]
        assert kymImage.pixels_per_line == kymImage.img_shape[1]
        logger.info(f"  - num_lines: {kymImage.num_lines}, pixels_per_line: {kymImage.pixels_per_line}")


def test_kym_image_from_synthetic_2d() -> None:
    """Test KymImage with synthetic 2D numpy array."""
    logger.info("Testing KymImage with synthetic 2D data")
    
    # Create a 2D synthetic image
    img_2d = np.random.randint(0, 255, size=(100, 200), dtype=np.uint8)
    logger.info(f"== Created 2D array with shape: {img_2d.shape}")
    
    kymImage = KymImage(path=None, img_data=img_2d)
    
    # Image data should be set
    channel_data = kymImage.getChannelData(1)
    assert channel_data is not None
    logger.info(f"  - Image data shape: {channel_data.shape}")
    
    # Shape should be available from data
    assert kymImage.img_shape is not None
    assert len(kymImage.img_shape) == 2
    assert kymImage.img_shape == (100, 200)
    assert kymImage.img_ndim == 2
    logger.info(f"  - Shape: {kymImage.img_shape}")
    
    # KymImage-specific properties should work
    assert kymImage.num_lines == 100
    assert kymImage.pixels_per_line == 200
    logger.info(f"  - num_lines: {kymImage.num_lines}, pixels_per_line: {kymImage.pixels_per_line}")


def test_kym_image_header_shape_matches_loaded_data() -> None:
    """Test that header-based shape matches loaded data shape when both are available."""
    logger.info("Testing KymImage header shape vs loaded data shape")
    
    # Create a 2D synthetic image
    img_2d = np.random.randint(0, 255, size=(50, 100), dtype=np.uint8)
    
    # Create KymImage with data (this sets header fields from data)
    kymImage = KymImage(path=None, img_data=img_2d)
    
    # Both header and data should have same shape
    assert kymImage.img_shape == (50, 100)
    assert kymImage.getChannelData(1).shape == (50, 100)
    assert kymImage.img_shape == kymImage.getChannelData(1).shape
    logger.info(f"  - Header shape: {kymImage.img_shape}")
    logger.info(f"  - Data shape: {kymImage.getChannelData(1).shape}")
    logger.info("  - Shapes match (as expected)")


def test_kym_image_properties() -> None:
    """Test KymImage-specific properties."""
    logger.info("Testing KymImage-specific properties")
    
    # Create a 2D synthetic image
    img_2d = np.random.randint(0, 255, size=(30, 40), dtype=np.uint8)
    kymImage = KymImage(path=None, img_data=img_2d)
    
    # Test num_lines and pixels_per_line
    assert kymImage.num_lines == 30
    assert kymImage.pixels_per_line == 40
    logger.info(f"  - num_lines: {kymImage.num_lines}")
    logger.info(f"  - pixels_per_line: {kymImage.pixels_per_line}")
    
    # Test image_dur (requires seconds_per_line)
    # Default seconds_per_line is 0.001
    expected_dur = 30 * 0.001
    assert kymImage.image_dur == expected_dur
    logger.info(f"  - image_dur: {kymImage.image_dur}")


def test_kym_image_header_property() -> None:
    """Test header property access in KymImage."""
    logger.info("Testing KymImage header property")
    
    # Create 2D synthetic image
    img_2d = np.random.randint(0, 255, size=(100, 200), dtype=np.uint8)
    kymImage = KymImage(path=None, img_data=img_2d)
    
    # Header should be accessible
    assert kymImage.header is not None
    assert kymImage.header.shape == (100, 200)
    assert kymImage.header.ndim == 2
    logger.info(f"  - header.shape: {kymImage.header.shape}")
    logger.info(f"  - header.ndim: {kymImage.header.ndim}")


def test_kym_image_getRowDict_with_data() -> None:
    """Test getRowDict() with KymImage and image data."""
    logger.info("Testing KymImage getRowDict() with data")
    
    # Create 2D synthetic image
    img_2d = np.random.randint(0, 255, size=(50, 75), dtype=np.uint8)
    kymImage = KymImage(path=None, img_data=img_2d)
    
    # Get row dict
    row_dict = kymImage.getRowDict()
    
    # Check file info (no path, so should be None)
    assert row_dict['path'] is None
    assert row_dict['filename'] is None
    
    # Check header fields (should be populated from data)
    assert row_dict['ndim'] == 2
    assert row_dict['shape'] == (50, 75)
    assert row_dict['voxels'] == [1.0, 1.0]
    assert row_dict['voxels_units'] == ["px", "px"]
    assert row_dict['labels'] == ["", ""]
    
    logger.info(f"  - getRowDict(): {row_dict}")


@pytest.mark.requires_data
def test_kym_image_getRowDict_with_path(sample_tif_files: list[Path]) -> None:
    """Test getRowDict() with KymImage and file path."""
    if not sample_tif_files:
        pytest.skip("No test data files available")
    
    logger.info("Testing KymImage getRowDict() with path")
    
    tif_file = sample_tif_files[0]
    kymImage = KymImage(path=tif_file)
    
    # Get row dict
    row_dict = kymImage.getRowDict()
    
    # Check file info
    assert row_dict['path'] == str(tif_file)
    assert row_dict['filename'] == tif_file.name
    
    # Check that parent folders are computed (may be None if path is shallow)
    assert 'parent1' in row_dict
    assert 'parent2' in row_dict
    assert 'parent3' in row_dict
    
    # Check header fields (may be None if no Olympus header, or populated if header exists)
    assert 'ndim' in row_dict
    assert 'shape' in row_dict
    assert 'voxels' in row_dict
    assert 'voxels_units' in row_dict
    assert 'labels' in row_dict
    
    logger.info(f"  - getRowDict(): {row_dict}")

