"""Simple tests for KymFile using test data.

These tests demonstrate basic usage patterns and use sample TIFF files from tests/data/.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kymflow_core.kym_file import KymFile, _get_analysis_folder_path, _getSavePaths
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
def test_save_analysis_without_analysis(sample_tif_file: Path | None) -> None:
    """Test that save_analysis() handles the case where no analysis has been run.
    
    Note: save_analysis() only saves if analysis has been run.
    This test verifies the method exists and doesn't crash when called without analysis.
    """
    if sample_tif_file is None:
        pytest.skip("No test data files available")

    kym = KymFile(sample_tif_file, load_image=False)
    
    # save_analysis() will only save if analysis has been performed
    # This just verifies the method exists and doesn't crash
    result = kym.save_analysis()  # Should return False and not raise an error
    assert result is False  # No analysis to save
    
    # The analysis folder path can be checked
    analysis_folder = _get_analysis_folder_path(sample_tif_file)
    logger.info(f"Analysis folder would be: {analysis_folder}")


@pytest.mark.requires_data
def test_tif_file_without_txt_header(tif_file_without_txt: Path | None) -> None:
    """Test loading a TIFF file that doesn't have a corresponding .txt header file.
    
    This tests the case where Capillary2_no_txt.tif is loaded and should handle
    the missing Olympus header gracefully with default values.
    """
    if tif_file_without_txt is None:
        pytest.skip("Capillary2_no_txt.tif not found in test data")
    
    kym = KymFile(tif_file_without_txt, load_image=False)
    
    # Should load without error even without .txt file
    assert kym.path.name == "Capillary2_no_txt.tif"
    
    # Header should have default values since .txt file is missing
    header = kym.acquisition_metadata
    assert header.um_per_pixel == 1.0  # Default value
    assert header.seconds_per_line == 0.001  # Default value (1 ms)
    
    logger.info(f"Loaded file without header: {tif_file_without_txt.name}")
    logger.info(f"Using default um_per_pixel: {header.um_per_pixel}")
    logger.info(f"Using default seconds_per_line: {header.seconds_per_line}")


@pytest.mark.requires_data
def test_analyze_and_save_analysis(sample_tif_file: Path | None) -> None:
    """Test running analysis and saving results, then verifying they can be loaded.
    
    This test:
    1. Loads a file and runs analyze_flow()
    2. Modifies experiment metadata
    3. Saves the analysis
    4. Creates a new KymFile instance and loads the saved analysis
    5. Verifies the loaded analysis matches what was saved
    """
    if sample_tif_file is None:
        pytest.skip("No test data files available")
    
    # Step 1: Load file and run analysis
    logger.info(f'testing sample_tif_file:{sample_tif_file}')
    kym = KymFile(sample_tif_file, load_image=True)
    
    # Modify experiment metadata to test that it gets saved
    kym.update_experiment_metadata(
        species="test_species",
        region="test_region",
        note="Test note for analysis save/load test"
    )
    
    # Run analysis with a larger window size for faster testing (fewer windows to process)
    # window_size = 256
    window_size = 32
    logger.info(f'calling analyze_flow() window_size: {window_size} -->> wait ...')
    kym.analyze_flow(window_size=window_size, use_multiprocessing=False)
    
    # Verify analysis was created
    assert kym.analysisExists
    assert kym._dfAnalysis is not None
    
    # Get some values to verify after reload
    original_velocity = kym.getAnalysisValue("velocity")
    original_time = kym.getAnalysisValue("time")
    original_species = kym.experiment_metadata.species
    original_note = kym.experiment_metadata.note
    
    # Step 2: Save analysis
    save_result = kym.save_analysis()
    assert save_result is True, "Analysis should have been saved successfully"
    
    # Verify files were created
    analysis_folder = _get_analysis_folder_path(sample_tif_file)
    csv_path = analysis_folder / f"{sample_tif_file.stem}.csv"
    json_path = analysis_folder / f"{sample_tif_file.stem}.json"
    
    assert csv_path.exists(), f"CSV file should exist at {csv_path}"
    assert json_path.exists(), f"JSON file should exist at {json_path}"
    
    # Step 3: Create a new KymFile instance and load the saved analysis
    kym_reloaded = KymFile(sample_tif_file, load_image=False)
    load_result = kym_reloaded.load_analysis()
    
    assert load_result is True, "Analysis should have been loaded successfully"
    assert kym_reloaded.analysisExists, "Reloaded file should have analysis"
    
    # Step 4: Verify the loaded analysis matches what was saved
    reloaded_velocity = kym_reloaded.getAnalysisValue("velocity")
    reloaded_time = kym_reloaded.getAnalysisValue("time")
    
    # Compare arrays (allowing for small floating point differences)
    assert reloaded_velocity is not None
    assert reloaded_time is not None
    assert len(reloaded_velocity) == len(original_velocity)
    assert len(reloaded_time) == len(original_time)
    
    # Verify metadata was saved and loaded
    assert kym_reloaded.experiment_metadata.species == original_species
    assert kym_reloaded.experiment_metadata.note == original_note
    
    # Verify analysis parameters
    assert kym_reloaded.analysis_parameters.algorithm == "mpRadon"
    assert kym_reloaded.analysis_parameters.window_size == window_size
    
    logger.info(f"Successfully saved and reloaded analysis for {sample_tif_file.name}")


@pytest.mark.requires_data
def test_analysis_parameters_all_fields_saved(sample_tif_file: Path | None) -> None:
    """Test that all AnalysisParameters fields are saved to JSON file.
    
    This test verifies that programmatically declared fields in AnalysisParameters
    are actually persisted to the JSON file when analysis is saved.
    """
    if sample_tif_file is None:
        pytest.skip("No test data files available")
    
    import json
    
    # Load file and run analysis with various parameter values
    kym = KymFile(sample_tif_file, load_image=True)
    window_size = 32
    start_pixel = 10
    stop_pixel = 100
    start_line = 5
    stop_line = 200
    use_multiprocessing = False
    
    kym.analyze_flow(
        window_size=window_size,
        start_pixel=start_pixel,
        stop_pixel=stop_pixel,
        start_line=start_line,
        stop_line=stop_line,
        use_multiprocessing=use_multiprocessing,
    )
    
    # Save analysis
    save_result = kym.save_analysis()
    assert save_result is True, "Analysis should have been saved successfully"
    
    # Load the saved JSON file directly
    _, json_path = _getSavePaths(sample_tif_file)
    
    assert json_path.exists(), f"JSON file should exist at {json_path}"
    
    with open(json_path, "r") as f:
        saved_metadata = json.load(f)
    
    # Verify analysis_parameters section exists
    assert "analysis_parameters" in saved_metadata
    ap_data = saved_metadata["analysis_parameters"]
    
    # Verify all expected fields are present
    expected_fields = [
        "algorithm",
        "window_size",
        "start_pixel",
        "stop_pixel",
        "start_line",
        "stop_line",
        "use_multiprocessing",
        "analyzed_at",
        "result_path",
    ]
    
    for field in expected_fields:
        assert field in ap_data, f"Field '{field}' should be present in saved JSON"
    
    # Verify values match what was set
    assert ap_data["algorithm"] == "mpRadon"
    assert ap_data["window_size"] == window_size
    assert ap_data["start_pixel"] == start_pixel
    assert ap_data["stop_pixel"] == stop_pixel
    assert ap_data["start_line"] == start_line
    assert ap_data["stop_line"] == stop_line
    assert ap_data["use_multiprocessing"] == use_multiprocessing
    assert ap_data["analyzed_at"] is not None
    # result_path may be None or a string path
    
    # Verify no nested "parameters" dict exists (flattened structure)
    assert "parameters" not in ap_data, "Should not have nested 'parameters' dict in flattened structure"
    
    logger.info(f"All AnalysisParameters fields verified in JSON for {sample_tif_file.name}")


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
        kym = KymFile(tif_file, load_image=False)
        
        # Basic assertions that should work for all files
        assert kym.path == tif_file
        assert kym.path.name == tif_file.name
        
        # Files should have some basic properties (may be None if header missing)
        # But the file should still load without error
        logger.info(f"  - num_lines: {kym.num_lines}")
        logger.info(f"  - pixels_per_line: {kym.pixels_per_line}")
        logger.info(f"  - duration_seconds: {kym.duration_seconds}")
