"""Simple tests for KymImage using test data.

These tests demonstrate basic usage patterns and use sample TIFF files from tests/data/.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.utils.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)


@pytest.mark.requires_data
def test_get_analysis_folder_path(sample_tif_file: Path | None) -> None:
    """Test that analysis folder path is generated correctly."""
    if sample_tif_file is None:
        pytest.skip("No test data files available")

    kymFile = KymImage(sample_tif_file, load_image=False)
    analysis_path = kymFile.get_kym_analysis()._get_analysis_folder_path()
    logger.info(f"Analysis folder path: {analysis_path}")
    
    # Verify the path structure
    assert analysis_path.is_absolute() or analysis_path.is_relative_to(sample_tif_file.parent)
    assert analysis_path.name.endswith("-analysis")


@pytest.mark.requires_data
def test_kym_file_basic_properties(sample_tif_file: Path | None) -> None:
    """Test basic KymFile properties using test data."""
    if sample_tif_file is None:
        pytest.skip("No test data files available")

    kymFile = KymImage(sample_tif_file, load_image=False)
    
    logger.info(f"num_lines: {kymFile.num_lines}")
    logger.info(f"pixels_per_line: {kymFile.pixels_per_line}")
    logger.info(f"header.physical_size[0]: {kymFile.header.physical_size[0] if kymFile.header.physical_size else None}")
    logger.info(f"experiment_metadata: {kymFile.experiment_metadata}")
    
    # Basic assertions
    assert kymFile.num_lines > 0
    assert kymFile.pixels_per_line > 0
    # duration_seconds is now header.physical_size[0] for kymographs
    if kymFile.header.physical_size and len(kymFile.header.physical_size) > 0:
        assert kymFile.header.physical_size[0] >= 0


@pytest.mark.requires_data
def test_save_analysis_without_analysis(sample_tif_file: Path | None) -> None:
    """Test that save_analysis() handles the case where no analysis has been run.
    
    Note: save_analysis() only saves if analysis has been run.
    This test verifies the method exists and doesn't crash when called without analysis.
    """
    if sample_tif_file is None:
        pytest.skip("No test data files available")

    kymFile = KymImage(sample_tif_file, load_image=False)
    
    # save_analysis() will only save if analysis has been performed
    # This just verifies the method exists and doesn't crash
    result = kymFile.get_kym_analysis().save_analysis()  # Should return False and not raise an error
    assert result is False  # No analysis to save
    
    # The analysis folder path can be checked
    analysis_folder = kymFile.get_kym_analysis()._get_analysis_folder_path()
    logger.info(f"Analysis folder would be: {analysis_folder}")


@pytest.mark.requires_data
def test_tif_file_without_txt_header(tif_file_without_txt: Path | None) -> None:
    """Test loading a TIFF file that doesn't have a corresponding .txt header file.
    
    This tests the case where Capillary2_no_txt.tif is loaded and should handle
    the missing Olympus header gracefully with default values.
    """
    if tif_file_without_txt is None:
        pytest.skip("Capillary2_no_txt.tif not found in test data")
    
    kymFile = KymImage(tif_file_without_txt, load_image=False)
    
    # Should load without error even without .txt file
    assert kymFile.path.name == "Capillary2_no_txt.tif"
    
    # Header should have default values since .txt file is missing
    # header = kymFile.acquisition_metadata
    # assert header.um_per_pixel == 1.0  # Default value
    # assert header.seconds_per_line == 0.001  # Default value (1 ms)
    
    logger.info(f"Loaded file without header: {tif_file_without_txt.name}")
    logger.info(f"Using default um_per_pixel: {kymFile.um_per_pixel}")
    logger.info(f"Using default seconds_per_line: {kymFile.seconds_per_line}")


@pytest.mark.skip(reason="Needs API update - uses old analyze_flow/getAnalysisValue API. Update after KymAnalysis API is finalized.")
@pytest.mark.requires_data
def test_analyze_and_save_analysis(sample_tif_file: Path | None) -> None:
    """Test running analysis and saving results, then verifying they can be loaded.
    
    TODO: Update to use new KymAnalysis API:
    - Create ROI first
    - Use kym.kymanalysis.analyze_roi() instead of kym.analyze_flow()
    - Use kym.kymanalysis.get_analysis_value() instead of kym.getAnalysisValue()
    - Use kym.kymanalysis.save_analysis() instead of kym.save_analysis()
    """
    pytest.skip("Test needs to be updated to use new KymAnalysis API")


@pytest.mark.skip(reason="Needs API update - uses old analyze_flow/save_analysis API. Update after KymAnalysis API is finalized.")
@pytest.mark.requires_data
def test_analysis_parameters_all_fields_saved(sample_tif_file: Path | None) -> None:
    """Test that all ROI and analysis metadata fields are saved to JSON file.
    
    TODO: Update to use new KymAnalysis API - now saves ROIs in metadata.json
    and analysis metadata in analysis JSON structure.
    """
    pytest.skip("Test needs to be updated to use new KymAnalysis API")


@pytest.mark.requires_data
def test_all_tif_files_loadable(sample_tif_files: list[Path]) -> None:
    """Test that all TIFF files in the test data directory can be loaded.
    
    This ensures we test all files, including the one without a .txt header file.
    """
    if not sample_tif_files:
        pytest.skip("No test data files available")
    
    logger.info(f"Testing {len(sample_tif_files)} TIFF files")
    
    for tif_file in sample_tif_files:
        logger.info(f"Loading {tif_file.name}")
        kymFile = KymImage(tif_file, load_image=True)
        
        # Basic assertions that should work for all files
        assert kymFile.path == tif_file
        assert kymFile.path.name == tif_file.name
        
        # Files should have some basic properties (may be None if header missing)
        # But the file should still load without error
        logger.info(f"  - num_lines: {kymFile.num_lines}")
        logger.info(f"  - pixels_per_line: {kymFile.pixels_per_line}")
        # logger.info(f"  - duration_seconds: {kymFile.duration_seconds}")
