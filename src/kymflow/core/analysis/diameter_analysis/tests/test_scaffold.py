from __future__ import annotations

import numpy as np

from kymflow.core.analysis.diameter_analysis import DiameterAnalyzer, DiameterDetectionParams
from kymflow.core.analysis.diameter_analysis import generate_synthetic_kymograph


def test_basic_scaffold_still_runs_with_new_engine() -> None:
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

    params = DiameterDetectionParams(window_rows_odd=3, stride=2)
    round_trip = DiameterDetectionParams.from_dict(params.to_dict())
    assert round_trip == params

    results = analyzer.analyze(
        params=params,
        roi_id=1,
        roi_bounds=(0, analyzer.kymograph.shape[0], 0, analyzer.kymograph.shape[1]),
        channel_id=1,
        backend="serial",
    )
    assert len(results) == 30
    assert results[0].center_row == 0
    assert results[-1].center_row == 58
