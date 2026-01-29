"""Simple test to generate and inspect stall analysis results.

DEPRECATED: Stall analysis tests are deprecated in favor of velocity event analysis.
This test is kept for reference but is skipped by default.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from kymflow.core.analysis.stall_analysis import detect_stalls
from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.utils.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)

pytestmark = pytest.mark.skip(reason="Stall analysis tests are deprecated in favor of velocity event analysis")


@pytest.mark.requires_data
def test_generate_stall_analysis() -> None:
    """Generate stall analysis for Capillary1_0001.tif and log detailed results."""
    # Load directly from tests/data directory
    data_dir = Path(__file__).parent.parent / "data"
    tif_file = data_dir / "Capillary1_0001.tif"
    
    if not tif_file.exists():
        pytest.skip("Capillary1_0001.tif not found in test data")
    
    logger.info(f"Loading KymImage: {tif_file}")
    
    # Load KymImage
    kym_image = KymImage(tif_file, load_image=False)
    logger.info(f"KymImage loaded: shape={kym_image.img_shape}")
    logger.info(f"  seconds_per_line: {kym_image.seconds_per_line}")
    
    # Get velocity data for ROI 1
    kym_analysis = kym_image.get_kym_analysis()
    roi_id = 1
    velocity = kym_analysis.get_analysis_value(roi_id=roi_id, key="velocity")
    
    if velocity is None:
        pytest.skip("No velocity data available for ROI 1")
    
    logger.info(f"Velocity array length: {len(velocity)}")
    logger.info(f"Number of NaN values: {np.sum(np.isnan(velocity))}")
    
    # Stall detection is performed in array-index space for tests.
    # (We do not rely on any 'lineScanBin' column.)
    start_bin = 0
    
    # Run stall detection with start_bin offset
    refactory_bins = 20
    min_stall_duration = 2  # 4
    end_stall_non_nan_bins = 2
    stalls = detect_stalls(
        velocity,
        refactory_bins=refactory_bins,
        min_stall_duration=min_stall_duration,
        start_bin=start_bin,
        end_stall_non_nan_bins=end_stall_non_nan_bins,
    )
    logger.info(f"Detected {len(stalls)} stalls")
    
    for i, stall in enumerate(stalls, 1):
        logger.info(f"  Stall {i}: bins [{stall.bin_start}, {stall.bin_stop}], duration: {stall.stall_bins} bins")
    
    # Verify the code ran successfully
    assert isinstance(stalls, list)

    if 0:
        logger.info(f'plotting stalls {len(stalls)}')
        from kymflow.core.plotting.stall_plots import plot_stalls_matplotlib
        fig = plot_stalls_matplotlib(kym_image, roi_id, stalls)
        # fig.show()

        from kymflow.core.plotting.stall_plots import plot_stalls_plotly
        fig = plot_stalls_plotly(kym_image, roi_id, stalls)
        fig.show()

        import matplotlib.pyplot as plt
        plt.show()

if __name__ == "__main__":
    test_generate_stall_analysis()