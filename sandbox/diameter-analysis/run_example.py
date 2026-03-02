from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np

from diameter_analysis import DiameterAnalyzer, DiameterDetectionParams, DiameterMethod
from diameter_plots import (
    plot_diameter_vs_time_mpl,
    plot_diameter_vs_time_plotly_dict,
    plot_kymograph_with_edges_mpl,
    plot_kymograph_with_edges_plotly_dict,
)
from synthetic_kymograph import generate_synthetic_kymograph


def _run_one_method(
    analyzer: DiameterAnalyzer,
    payload: dict,
    method: DiameterMethod,
) -> None:
    params = DiameterDetectionParams(
        window_rows_odd=5,
        stride=2,
        roi=(0, int(payload["kymograph"].shape[0]), 0, int(payload["kymograph"].shape[1])),
        diameter_method=method,
    )
    results = analyzer.analyze(params=params, backend="threads")

    fig, (ax0, ax1) = plt.subplots(2, 1, figsize=(9, 7), sharex=False)
    plot_kymograph_with_edges_mpl(
        payload["kymograph"],
        results,
        seconds_per_line=payload["seconds_per_line"],
        um_per_pixel=payload["um_per_pixel"],
        ax=ax0,
    )
    plot_diameter_vs_time_mpl(
        results,
        um_per_pixel=payload["um_per_pixel"],
        seconds_per_line=payload["seconds_per_line"],
        ax=ax1,
    )
    fig.suptitle(f"Method: {method.value}")
    fig.tight_layout()
    # plt.close(fig)

    plotly_kym = plot_kymograph_with_edges_plotly_dict(
        payload["kymograph"],
        results,
        seconds_per_line=payload["seconds_per_line"],
        um_per_pixel=payload["um_per_pixel"],
    )
    plotly_diam = plot_diameter_vs_time_plotly_dict(
        results,
        um_per_pixel=payload["um_per_pixel"],
        seconds_per_line=payload["seconds_per_line"],
    )

    diameter_px = np.array([r.diameter_px for r in results], dtype=float)
    finite_count = int(np.isfinite(diameter_px).sum())
    print(f"method: {method.value}")
    print(f"results count: {len(results)}")
    print(f"finite diameter points: {finite_count}")
    print(f"plotly kym dict keys: {sorted(plotly_kym.keys())}")
    print(f"plotly diameter traces: {len(plotly_diam['data'])}")


def main() -> None:
    # payload = generate_synthetic_kymograph(n_time=220, n_space=150, seed=1)
    payload = generate_synthetic_kymograph(n_time=1000,n_space=80,
                                seconds_per_line=0.001, um_per_pixel=0.15,
                                seed=1)

    analyzer = DiameterAnalyzer(
        payload["kymograph"],
        seconds_per_line=payload["seconds_per_line"],
        um_per_pixel=payload["um_per_pixel"],
        polarity=payload["polarity"],
    )

    for method in (DiameterMethod.THRESHOLD_WIDTH, DiameterMethod.GRADIENT_EDGES):
        _run_one_method(analyzer, payload, method)

    plt.show()

if __name__ == "__main__":
    main()
