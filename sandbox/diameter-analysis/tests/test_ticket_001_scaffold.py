from __future__ import annotations

import numpy as np

from diameter_analysis import DiameterAnalyzer, DiameterDetectionParams
from synthetic_kymograph import generate_synthetic_kymograph


def test_synthetic_and_placeholder_analysis_and_params_round_trip() -> None:
    payload = generate_synthetic_kymograph(n_time=60, n_space=80, seed=2)
    kym = payload["kymograph"]

    assert isinstance(kym, np.ndarray)
    assert kym.shape == (60, 80)

    analyzer = DiameterAnalyzer(
        kym,
        seconds_per_line=payload["seconds_per_line"],
        um_per_pixel=payload["um_per_pixel"],
        polarity=payload["polarity"],
    )

    params = DiameterDetectionParams(threshold_fraction=0.5, min_diameter_px=2.0)
    round_trip = DiameterDetectionParams.from_dict(params.to_dict())
    assert round_trip == params

    result = analyzer.analyze(params=params)
    assert set(result.keys()) == {
        "time_s",
        "diameter_px",
        "diameter_um",
        "left_edge_px",
        "right_edge_px",
    }
    assert result["time_s"].shape == (60,)
    assert result["diameter_px"].shape == (60,)
    assert result["diameter_um"].shape == (60,)
    assert np.isfinite(result["diameter_px"]).sum() >= 1
