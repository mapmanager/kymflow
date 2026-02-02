"""Tests for Olympus header extractors."""

from __future__ import annotations

import pytest

from kymflow.core.image_loaders.olympus_header.extractors import (
    extract_duration_sec_from_t_dimension,
    extract_float,
    extract_image_size_pixels,
    extract_int,
    extract_um_per_pixel_from_x_dimension,
)


def test_extract_int() -> None:
    """Test extract_int() function."""
    # Test valid integer strings
    assert extract_int("123") == 123
    assert extract_int("-456") == -456
    assert extract_int("+789") == 789
    assert extract_int("abc 123 def") == 123  # First int found
    assert extract_int("Value: 42 units") == 42
    
    # Test None and empty strings
    assert extract_int(None) is None
    assert extract_int("") is None
    assert extract_int("abc") is None  # No integer found


def test_extract_float() -> None:
    """Test extract_float() function."""
    # Test valid float strings
    assert extract_float("123.45") == 123.45
    assert extract_float("-456.78") == -456.78
    assert extract_float("+789.0") == 789.0
    assert extract_float("123") == 123.0  # Integer as float
    assert extract_float("abc 123.45 def") == 123.45  # First float found
    assert extract_float("Value: 42.5 units") == 42.5
    
    # Test None and empty strings
    assert extract_float(None) is None
    assert extract_float("") is None
    assert extract_float("abc") is None  # No float found


def test_extract_image_size_pixels() -> None:
    """Test extract_image_size_pixels() function."""
    # Test valid format
    assert extract_image_size_pixels("38 * 30000 [pixel]") == (38, 30000)
    assert extract_image_size_pixels("100 * 200 pixels") == (100, 200)
    assert extract_image_size_pixels("10 20") == (10, 20)  # Just two numbers
    
    # Test with more numbers (should take first two)
    assert extract_image_size_pixels("38 * 30000 * 5 [pixel]") == (38, 30000)
    
    # Test None and invalid strings
    assert extract_image_size_pixels(None) is None
    assert extract_image_size_pixels("") is None
    assert extract_image_size_pixels("abc") is None  # No integers
    assert extract_image_size_pixels("123") is None  # Only one integer


def test_extract_um_per_pixel_from_x_dimension() -> None:
    """Test extract_um_per_pixel_from_x_dimension() function."""
    # Test with um/pixel in string
    assert extract_um_per_pixel_from_x_dimension(
        "416, 0.0 - 172.357 [um], 0.414 [um/pixel]"
    ) == pytest.approx(0.414)
    
    # Test with um/pixel in different position
    assert extract_um_per_pixel_from_x_dimension(
        "0.284 [um/pixel], other values"
    ) == pytest.approx(0.284)
    
    # Test fallback to last float
    assert extract_um_per_pixel_from_x_dimension(
        "416, 0.0 - 172.357 [um], 0.414"
    ) == pytest.approx(0.414)
    
    # Test None and invalid strings
    assert extract_um_per_pixel_from_x_dimension(None) is None
    assert extract_um_per_pixel_from_x_dimension("") is None
    assert extract_um_per_pixel_from_x_dimension("abc") is None  # No floats


def test_extract_duration_sec_from_t_dimension() -> None:
    """Test extract_duration_sec_from_t_dimension() function."""
    # Test with [s] in string
    assert extract_duration_sec_from_t_dimension(
        "1, 0.000 - 35.099 [s], Interval FreeRun"
    ) == pytest.approx(35.099)
    
    # Test with [s] in different position
    assert extract_duration_sec_from_t_dimension(
        "0.000 - 10.5 [s], other text"
    ) == pytest.approx(10.5)
    
    # Test fallback to last float
    assert extract_duration_sec_from_t_dimension(
        "1, 0.000 - 35.099, Interval FreeRun"
    ) == pytest.approx(35.099)
    
    # Test None and invalid strings
    assert extract_duration_sec_from_t_dimension(None) is None
    assert extract_duration_sec_from_t_dimension("") is None
    assert extract_duration_sec_from_t_dimension("abc") is None  # No floats
