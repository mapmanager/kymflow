"""Simple test to generate and inspect stall analysis results."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from kymflow.core.analysis.stall_analysis import detect_stalls
from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.utils.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)


@pytest.mark.requires_data
def test_generate_velocity_events() -> None:
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
    
    kym_analysis.run_velocity_event_analysis(roi_id=roi_id)
    
    velocityEvents = kym_analysis.get_velocity_events(roi_id=roi_id)
    assert velocityEvents is not None
    assert len(velocityEvents) > 0
    for velocityEvent in velocityEvents:
        logger.info(f"Event: {velocityEvent}")
        from pprint import pprint
        pprint(velocityEvent)
    
    # if 0:
    #     logger.info(f'plotting velocity events {len(velocityEvents)}')
    #     from kymflow.core.analysis.velocity_events.velocity_plots import plot_kym_zoom_with_event
    #     fig = plot_kym_zoom_with_event(kym_image.img_time_space, kym_image.scaling, velocityEvent)
    #     fig.show()

    # save kym_analysis
    kym_analysis.save_analysis()
    logger.info(f"Saved kym_analysis")

if __name__ == "__main__":
    test_generate_velocity_events()