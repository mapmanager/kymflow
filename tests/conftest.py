"""Pytest configuration and fixtures for kymflow tests."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest

# Configure NiceGUI testing plugin
pytest_plugins = ["nicegui.testing.plugin"]

# Path to test data directory
TEST_DATA_DIR = Path(__file__).parent / "data"


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "requires_data: mark test as requiring test data directory",
    )


@pytest.fixture(scope="session", autouse=True)
def isolate_user_config_dir(tmp_path_factory: pytest.TempPathFactory) -> None:
    """Ensure tests never write to the real platformdirs user config file."""
    cfg_path = tmp_path_factory.mktemp("kymflow_user_config") / "user_config.json"
    previous = os.environ.get("KYMFLOW_USER_CONFIG_PATH")
    os.environ["KYMFLOW_USER_CONFIG_PATH"] = str(cfg_path)
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("KYMFLOW_USER_CONFIG_PATH", None)
        else:
            os.environ["KYMFLOW_USER_CONFIG_PATH"] = previous


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


@pytest.fixture(scope="session")
def temp_test_data_dir() -> Path:
    """Create a temporary copy of the test data directory for the entire test session.
    
    This fixture copies the entire tests/data/ directory to a temporary location
    to prevent tests from modifying the original test data files. The temporary
    directory is cleaned up after all tests complete.
    
    Returns:
        Path to the temporary test data directory.
    """
    if not TEST_DATA_DIR.exists():
        pytest.skip("Test data directory does not exist")
    
    # Create a temporary directory
    temp_dir = Path(tempfile.mkdtemp(prefix="kymflow_test_data_"))
    
    try:
        # Copy entire test data directory to temp location
        shutil.copytree(TEST_DATA_DIR, temp_dir, dirs_exist_ok=True)
        
        yield temp_dir
    finally:
        # Clean up: remove the temporary directory and all its contents
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def test_data_dir(temp_test_data_dir: Path) -> Path:
    """Fixture providing path to temporary test data directory.

    This fixture uses the session-scoped temp_test_data_dir to ensure all tests
    use a copy of the test data, preventing modifications to the original files.

    Returns:
        Path to temporary copy of tests/data/ directory.
    """
    return temp_test_data_dir


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


@pytest.fixture
def tif_file_without_txt(test_data_dir: Path) -> Path | None:
    """Fixture providing the TIFF file that doesn't have a corresponding .txt file.
    
    This fixture specifically finds Capillary2_no_txt.tif to test the case where
    the Olympus header file is missing.
    
    Returns:
        Path to Capillary2_no_txt.tif if it exists, or None.
    """
    tif_path = test_data_dir / "Capillary2_no_txt.tif"
    if tif_path.exists():
        return tif_path
    return None
