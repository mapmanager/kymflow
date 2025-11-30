"""Pytest configuration and fixtures for kymflow tests."""

from __future__ import annotations

from pathlib import Path

import pytest

# Path to test data directory
TEST_DATA_DIR = Path(__file__).parent / "data"


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "requires_data: mark test as requiring test data directory",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Automatically skip tests marked with 'requires_data' if data doesn't exist."""
    if TEST_DATA_DIR.exists():
        return  # Data exists, no need to skip anything

    skip_marker = pytest.mark.skip(reason="Test data directory not found")
    for item in items:
        if "requires_data" in [mark.name for mark in item.iter_markers()]:
            item.add_marker(skip_marker)


@pytest.fixture
def test_data_dir() -> Path:
    """Fixture providing path to test data directory.

    Returns:
        Path to tests/data/ directory.
    """
    if not TEST_DATA_DIR.exists():
        pytest.skip("Test data directory does not exist")
    return TEST_DATA_DIR


@pytest.fixture
def sample_tif_files(test_data_dir: Path) -> list[Path]:
    """Fixture providing list of sample TIFF files for testing.

    Returns:
        List of Path objects for TIFF files found in test_data_dir.
        Returns empty list if no files found (tests should skip gracefully).
    """
    if not test_data_dir.exists():
        return []

    tif_files = sorted(test_data_dir.glob("*.tif"))
    return list(tif_files)


@pytest.fixture
def sample_tif_file(sample_tif_files: list[Path]) -> Path | None:
    """Fixture providing a single sample TIFF file for testing.

    Returns:
        First TIFF file found, or None if no files available.
    """
    return sample_tif_files[0] if sample_tif_files else None
