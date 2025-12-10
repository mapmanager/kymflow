#!/usr/bin/env python3
"""Generate test ROI analysis data for manual GUI testing.

This script:
1. Loads a .tif file from tests/data
2. Creates 2-3 ROIs with different coordinates
3. Runs analysis on each ROI with progress callbacks
4. Saves kymanalysis (to JSON and CSV)

Usage:
    python notebooks/generate_rois.py
    # or
    uv run python notebooks/generate_rois.py
"""

from __future__ import annotations

from pathlib import Path
import sys
import pytest

from kymflow.core.kym_file import KymFile
from kymflow.core.utils.logging import get_logger, setup_logging
from kymflow.core.utils import get_data_folder
# Configure logging to show INFO level messages to console
setup_logging(level="INFO")
logger = get_logger(__name__)


def create_progress_callback(roi_id: int, roi_label: str = "") -> callable:
    """Create a progress callback function that prints to console.
    
    Args:
        roi_id: ROI identifier for display
        roi_label: Optional label for the ROI (e.g., "Full Image", "Center Region")
    
    Returns:
        Callback function that accepts (completed: int, total: int)
    """
    label = f"ROI {roi_id}"
    if roi_label:
        label = f"{label} ({roi_label})"
    
    def progress_cb(completed: int, total: int) -> None:
        if total > 0:
            pct = (completed / total) * 100
            print(f"  {label}: {completed}/{total} windows ({pct:.1f}%)", end="\r")
            if completed >= total:
                print()  # Newline when complete
        else:
            print(f"  {label}: {completed} windows", end="\r")
    
    return progress_cb

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
def test_generate_rois(sample_tif_files: list[Path]) -> None:
    """Generate ROI analysis data for testing."""
    
    # Use first .tif file
    tif_file = sample_tif_files[0]
    logger.info(f"Loading first .tif file: {tif_file}")
    
    # Load KymFile (this will auto-load analysis if it exists)
    kym_file = KymFile(tif_file, load_image=True)
    # logger.info(f"Image loaded: {kym_file.num_lines} lines x {kym_file.pixels_per_line} pixels")
    logger.info(kym_file)

    # Delete any existing ROIs (start fresh)
    deleted_count = kym_file.kymanalysis.clear_all_rois()
    logger.info(f"Deleted {deleted_count} existing ROI(s)")
    
    # Get image dimensions for ROI creation
    # img_w = kym_file.pixels_per_line
    # img_h = kym_file.num_lines
    
    logger.info("="*60)
    logger.info("Creating ROIs...")
    logger.info("="*60)
    
    # Create ROIs with different regions
    # ROI 1: Full image (default)
    roi1 = kym_file.kymanalysis.add_roi(note="Full Image")
    logger.info(f"Created ROI {roi1.roi_id}: Full image (0, 0, {kym_file.pixels_per_line}, {kym_file.num_lines})")
    
    # ROI 2: Center region (if image is large enough)
    # if img_w > 100 and img_h > 100:
    if kym_file.pixels_per_line > 100:
        center_w = kym_file.pixels_per_line // 2
        center_h = kym_file.pixels_per_line // 2
        quarter_w = kym_file.pixels_per_line // 4
        quarter_h = kym_file.pixels_per_line // 4
        roi2 = kym_file.kymanalysis.add_roi(
            left=quarter_w,
            top=quarter_h,
            right=center_w + quarter_w,
            bottom=center_h + quarter_h,
            note="Center Region"
        )
        logger.info(f"Created ROI {roi2.roi_id}: Center region ({quarter_w}, {quarter_h}, {center_w + quarter_w}, {center_h + quarter_h})")
    else:
        roi2 = None
        logger.info("Skipping center ROI (image too small)")
    
    # ROI 3: Left region (if image is large enough)
    # if img_w > 150 and img_h > 50:
    if kym_file.pixels_per_line > 150:
        third_w = kym_file.pixels_per_line // 3
        roi3 = kym_file.kymanalysis.add_roi(
            left=0,
            top=kym_file.num_lines // 4,
            right=third_w,
            bottom=3 * kym_file.num_lines // 4,
            note="Left Region"
        )
        logger.info(f"Created ROI {roi3.roi_id}: Left region (0, {kym_file.num_lines // 4}, {third_w}, {3 * kym_file.num_lines // 4})")
    else:
        roi3 = None
        logger.info("Skipping left region ROI (image too small)")
    
    # Run analysis on each ROI
    window_size = 16
    logger.info("="*60)
    logger.info(f"Running analysis (window_size={window_size})...")
    logger.info("="*60)
    
    # Analyze ROI 1
    logger.info(f"\nAnalyzing ROI {roi1.roi_id}...")
    kym_file.kymanalysis.analyze_roi(
        roi1.roi_id,
        window_size,
        progress_callback=create_progress_callback(roi1.roi_id, "Full Image"),
        use_multiprocessing=True,
    )
    logger.info(f"✓ ROI {roi1.roi_id} analysis complete")
    
    # Analyze ROI 2 if created
    if roi2 is not None:
        logger.info(f"\nAnalyzing ROI {roi2.roi_id}...")
        kym_file.kymanalysis.analyze_roi(
            roi2.roi_id,
            window_size,
            progress_callback=create_progress_callback(roi2.roi_id, "Center Region"),
            use_multiprocessing=True,
        )
        logger.info(f"✓ ROI {roi2.roi_id} analysis complete")
    
    # Analyze ROI 3 if created
    if roi3 is not None:
        logger.info(f"\nAnalyzing ROI {roi3.roi_id}...")
        kym_file.kymanalysis.analyze_roi(
            roi3.roi_id,
            window_size,
            progress_callback=create_progress_callback(roi3.roi_id, "Left Region"),
            use_multiprocessing=True,
        )
        logger.info(f"✓ ROI {roi3.roi_id} analysis complete")
    
    # Save analysis
    logger.info("="*60)
    logger.info("Saving analysis...")
    logger.info("="*60)
    
    success = kym_file.kymanalysis.save_analysis()
    if success:
        csv_path, json_path = kym_file.kymanalysis._get_save_paths()
        logger.info(f"✓ Analysis saved to:")
        logger.info(f"  CSV: {csv_path}")
        logger.info(f"  JSON: {json_path}")
    else:
        logger.error("Failed to save analysis")
        sys.exit(1)
    
    logger.info("="*60)
    logger.info("Done! You can now copy these files for GUI testing:")
    logger.info(f"  Source: {tif_file}")
    logger.info(f"  Analysis folder: {csv_path.parent}")
    logger.info("="*60)

