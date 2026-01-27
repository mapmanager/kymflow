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

import queue
import threading
from pathlib import Path
import sys
import pytest

from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.image_loaders.roi import RoiBounds
from kymflow.core.utils.logging import get_logger, setup_logging
from kymflow.core.utils import get_data_folder
# Configure logging to show INFO level messages to console
setup_logging(level="INFO")
logger = get_logger(__name__)


def create_progress_queue(roi_id: int, roi_label: str = "") -> queue.Queue:
    """Create a progress queue and start a thread to drain and print progress.
    
    Args:
        roi_id: ROI identifier for display
        roi_label: Optional label for the ROI (e.g., "Full Image", "Center Region")
    
    Returns:
        A queue that receives progress messages and prints them.
    """
    label = f"ROI {roi_id}"
    if roi_label:
        label = f"{label} ({roi_label})"
    
    progress_q: queue.Queue = queue.Queue()
    
    def _drain_and_print() -> None:
        """Drain queue and print progress messages."""
        while True:
            try:
                msg = progress_q.get(timeout=1.0)
            except queue.Empty:
                continue
            if msg[0] == "progress":
                _, completed, total = msg
                if total > 0:
                    pct = (completed / total) * 100
                    print(f"  {label}: {completed}/{total} windows ({pct:.1f}%)", end="\r")
                    if completed >= total:
                        print()  # Newline when complete
                else:
                    print(f"  {label}: {completed} windows", end="\r")
            elif msg[0] == "done":
                break
    
    # Start daemon thread to drain queue
    threading.Thread(target=_drain_and_print, daemon=True).start()
    return progress_q

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
    
    if tif_file.name != 'Capillary1_0001.tif':
        logger.warning(f"Skipping test for non Capillary1_0001.tif file: {tif_file.name}")
        pytest.skip("Skipping test for non-Capillary1_0001.tif file")
    
    # Load KymImage (this will auto-load analysis if it exists)
    kym_image = KymImage(tif_file, load_image=True)
    # logger.info(f"Image loaded: {kym_image.num_lines} lines x {kym_image.pixels_per_line} pixels")
    logger.info(kym_image)

    # Delete any existing ROIs (start fresh)
    deleted_count = kym_image.rois.clear()
    logger.info(f"Deleted {deleted_count} existing ROI(s)")
    
    # Get image dimensions for ROI creation
    # img_w = kym_image.pixels_per_line
    # img_h = kym_image.num_lines
    
    logger.info("="*60)
    logger.info("Creating ROIs...")
    logger.info("="*60)
    
    # Create ROIs with different regions
    # Get image dimensions from acq_image
    pixelsPerLine = kym_image.pixels_per_line  # width (pixels per line / spatial dimension)
    numLines = kym_image.num_lines  # height (num lines / time dimension)
    
    # ROI 1: Full image (default)
    # For kymographs: dim0 = time (rows), dim1 = space (columns)
    bounds1 = RoiBounds(
        dim0_start=0,
        dim0_stop=numLines,  # time dimension (rows)
        dim1_start=0,
        dim1_stop=pixelsPerLine,  # space dimension (columns)
    )
    roi1 = kym_image.rois.create_roi(bounds=bounds1, note="Full Image")
    logger.info(f"Created ROI {roi1.id}: Full image (dim0: 0-{numLines}, dim1: 0-{pixelsPerLine})")
    
    # ROI 2: Center region
    # Coordinates will be automatically clamped to image bounds by create_roi()
    center_w = pixelsPerLine // 2
    center_h = numLines // 2
    quarter_w = pixelsPerLine // 4
    quarter_h = numLines // 4
    bounds2 = RoiBounds(
        dim0_start=quarter_h,
        dim0_stop=center_h + quarter_h,
        dim1_start=quarter_w,
        dim1_stop=center_w + quarter_w,
    )
    roi2 = kym_image.rois.create_roi(bounds=bounds2, note="Center Region")
    logger.info(f"Created ROI {roi2.id}: Center region (dim0: {quarter_h}-{center_h + quarter_h}, dim1: {quarter_w}-{center_w + quarter_w})")
    
    # ROI 3: Left region
    # Coordinates will be automatically clamped to image bounds by create_roi()
    third_w = pixelsPerLine // 3
    bounds3 = RoiBounds(
        dim0_start=numLines // 3,
        dim0_stop=3 * numLines // 3,
        dim1_start=0,
        dim1_stop=third_w,
    )
    roi3 = kym_image.rois.create_roi(bounds=bounds3, note="Left Region")
    logger.info(f"Created ROI {roi3.id}: Left region (dim0: {numLines // 4}-{3 * numLines // 4}, dim1: 0-{third_w})")
    
    # Run analysis on each ROI
    window_size = 16
    logger.info("="*60)
    logger.info(f"Running analysis (window_size={window_size})...")
    logger.info("="*60)
    
    # Analyze ROI 1
    logger.info(f"\nAnalyzing ROI {roi1.id}...")
    kym_image.get_kym_analysis().analyze_roi(
        roi1.id,
        window_size,
        progress_queue=create_progress_queue(roi1.id, "Full Image"),
        use_multiprocessing=True,
    )
    logger.info(f"✓ ROI {roi1.id} analysis complete")
    
    # Analyze ROI 2
    logger.info(f"\nAnalyzing ROI {roi2.id}...")
    kym_image.get_kym_analysis().analyze_roi(
        roi2.id,
        window_size,
        progress_queue=create_progress_queue(roi2.id, "Center Region"),
        use_multiprocessing=True,
    )
    logger.info(f"✓ ROI {roi2.id} analysis complete")
    
    # Analyze ROI 3
    logger.info(f"\nAnalyzing ROI {roi3.id}...")
    kym_image.get_kym_analysis().analyze_roi(
        roi3.id,
        window_size,
        progress_queue=create_progress_queue(roi3.id, "Left Region"),
        use_multiprocessing=True,
    )
    logger.info(f"✓ ROI {roi3.id} analysis complete")
    
    # Save analysis
    logger.info("="*60)
    logger.info("Saving analysis...")
    logger.info("="*60)
    
    success = kym_image.get_kym_analysis().save_analysis()
    if success:
        csv_path, json_path = kym_image.get_kym_analysis()._get_save_paths()
        logger.info(f"✓ Analysis saved to:")
        logger.info(f"  CSV: {csv_path}")
        logger.info(f"  JSON: {json_path}")
    else:
        logger.error("Failed to save analysis")
        # sys.exit(1)
    
    # logger.info("="*60)
    # logger.info("Done! You can now copy these files for GUI testing:")
    # logger.info(f"  Source: {tif_file}")
    # logger.info(f"  Analysis folder: {csv_path.parent}")
    # logger.info("="*60)

