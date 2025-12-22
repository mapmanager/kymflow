"""Unit tests for ImgAcqHeader dataclass.

Tests ImgAcqHeader validation, initialization, and consistency checks.
"""

from __future__ import annotations

import pytest

from kymflow.core.image_loaders.img_acq_header import ImgAcqHeader


def test_img_acq_header_default_initialization() -> None:
    """Test ImgAcqHeader with default (empty) initialization."""
    header = ImgAcqHeader()
    
    assert header.shape is None
    assert header.ndim is None
    assert header.voxels is None
    assert header.voxels_units is None
    assert header.labels is None
    assert header.physical_size is None


def test_img_acq_header_from_data() -> None:
    """Test ImgAcqHeader.from_data() class method."""
    shape = (100, 200)
    ndim = 2
    
    header = ImgAcqHeader.from_data(shape, ndim)
    
    assert header.shape == shape
    assert header.ndim == ndim
    assert header.voxels == [1.0, 1.0]
    assert header.voxels_units == ["px", "px"]
    assert header.labels == ["", ""]
    assert header.physical_size == [100.0, 200.0]


def test_img_acq_header_validate_ndim() -> None:
    """Test validate_ndim() method."""
    header = ImgAcqHeader()
    
    # Empty header should accept valid ndim
    assert header.validate_ndim(2) is True
    assert header.validate_ndim(3) is True
    assert header.validate_ndim(1) is False  # Invalid ndim
    assert header.validate_ndim(4) is False  # Invalid ndim
    
    # Set shape first
    header.shape = (100, 200)
    assert header.validate_ndim(2) is True
    assert header.validate_ndim(3) is False  # Inconsistent with shape
    
    # Set voxels
    header.voxels = [0.1, 0.2]
    assert header.validate_ndim(2) is True
    assert header.validate_ndim(3) is False  # Inconsistent with voxels


def test_img_acq_header_validate_shape() -> None:
    """Test validate_shape() method."""
    header = ImgAcqHeader()
    
    # Empty header should accept valid shape
    assert header.validate_shape((100, 200)) is True
    assert header.validate_shape((10, 100, 200)) is True
    assert header.validate_shape((100,)) is False  # Invalid (1D)
    assert header.validate_shape((100, 200, 300, 400)) is False  # Invalid (4D)
    
    # Set ndim first
    header.ndim = 2
    assert header.validate_shape((100, 200)) is True
    assert header.validate_shape((10, 100, 200)) is False  # Inconsistent with ndim
    
    # Set voxels
    header.voxels = [0.1, 0.2]
    assert header.validate_shape((100, 200)) is True
    assert header.validate_shape((10, 100, 200)) is False  # Inconsistent with voxels


def test_img_acq_header_compute_physical_size() -> None:
    """Test compute_physical_size() method."""
    header = ImgAcqHeader()
    
    # Should return None if shape or voxels are not set
    assert header.compute_physical_size() is None
    
    # Set shape only
    header.shape = (100, 200)
    assert header.compute_physical_size() is None  # Still None without voxels
    
    # Set voxels only
    header.shape = None
    header.voxels = [0.1, 0.2]
    assert header.compute_physical_size() is None  # Still None without shape
    
    # Set both
    header.shape = (100, 200)
    header.voxels = [0.1, 0.2]
    physical_size = header.compute_physical_size()
    assert physical_size is not None
    assert physical_size == [10.0, 40.0]  # 100 * 0.1, 200 * 0.2
    
    # Test with 3D
    header.shape = (10, 100, 200)
    header.voxels = [0.01, 0.1, 0.2]
    physical_size = header.compute_physical_size()
    assert physical_size is not None
    assert physical_size == [0.1, 10.0, 40.0]  # 10 * 0.01, 100 * 0.1, 200 * 0.2


def test_img_acq_header_inconsistent_fields() -> None:
    """Test that validation catches inconsistent fields."""
    header = ImgAcqHeader()
    
    # Set shape and ndim inconsistently
    header.shape = (100, 200)
    assert header.validate_ndim(3) is False  # ndim doesn't match shape
    
    # Set ndim and shape inconsistently
    header.ndim = 2
    header.shape = None
    assert header.validate_shape((10, 100, 200)) is False  # shape doesn't match ndim
    
    # Set voxels with wrong length
    header.ndim = 2
    header.voxels = [0.1, 0.2, 0.3]  # 3 elements for 2D
    assert header.validate_ndim(2) is False  # voxels length doesn't match ndim


def test_img_acq_header_consistency() -> None:
    """Test that consistent fields pass validation."""
    header = ImgAcqHeader()
    
    # Set all fields consistently for 2D
    header.shape = (100, 200)
    header.ndim = 2
    header.voxels = [0.1, 0.2]
    header.voxels_units = ["s", "um"]
    header.labels = ["time (s)", "space (um)"]
    
    # All validations should pass
    assert header.validate_ndim(2) is True
    assert header.validate_shape((100, 200)) is True
    
    # Compute physical size
    physical_size = header.compute_physical_size()
    assert physical_size == [10.0, 40.0]

