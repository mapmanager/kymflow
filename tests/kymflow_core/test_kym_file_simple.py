"""Simple tests for KymFile using test data.

These tests demonstrate basic usage patterns and use sample TIFF files from tests/data/.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kymflow_core.kym_file import KymFile, _get_analysis_folder_path
from kymflow_core.utils.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)


@pytest.mark.requires_data
def test_get_analysis_folder_path(sample_tif_file: Path | None) -> None:
    """Test that analysis folder path is generated correctly."""
    if sample_tif_file is None:
        pytest.skip("No test data files available")

    analysis_path = _get_analysis_folder_path(sample_tif_file)
    logger.info(f"Analysis folder path: {analysis_path}")
    
    # Verify the path structure
    assert analysis_path.is_absolute() or analysis_path.is_relative_to(sample_tif_file.parent)
    assert analysis_path.name.endswith("-analysis")


@pytest.mark.requires_data
def test_kym_file_basic_properties(sample_tif_file: Path | None) -> None:
    """Test basic KymFile properties using test data."""
    if sample_tif_file is None:
        pytest.skip("No test data files available")

    kym = KymFile(sample_tif_file, load_image=False)
    
    logger.info(f"num_lines: {kym.num_lines}")
    logger.info(f"pixels_per_line: {kym.pixels_per_line}")
    logger.info(f"duration_seconds: {kym.duration_seconds}")
    logger.info(f"experiment_metadata: {kym.experiment_metadata}")
    
    # Basic assertions
    assert kym.num_lines > 0
    assert kym.pixels_per_line > 0
    assert kym.duration_seconds >= 0


@pytest.mark.requires_data
def test_save_analysis(sample_tif_file: Path | None) -> None:
    """Test saving analysis results.
    
    Note: save_analysis() only saves if analysis has been run.
    This test verifies the method exists and can be called.
    """
    if sample_tif_file is None:
        pytest.skip("No test data files available")

    kym = KymFile(sample_tif_file, load_image=False)
    
    # save_analysis() will only save if analysis has been performed
    # For a full test, we'd need to run analysis first
    # This just verifies the method exists and doesn't crash
    kym.save_analysis()  # Should not raise an error even if no analysis to save
    
    # The analysis folder path can be checked
    analysis_folder = _get_analysis_folder_path(sample_tif_file)
    logger.info(f"Analysis folder would be: {analysis_folder}")
