from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np

from diameter_analysis import DiameterAnalyzer, DiameterDetectionParams
from diameter_plots import (
    plot_diameter_vs_time_plotly_dict,
    plot_kymograph_with_edges_plotly_dict,
)
from synthetic_kymograph import generate_synthetic_kymograph


def main() -> None:
    payload = generate_synthetic_kymograph(n_time=180, n_space=140, seed=1)

    analyzer = DiameterAnalyzer(
        payload["kymograph"],
        seconds_per_line=payload["seconds_per_line"],
        um_per_pixel=payload["um_per_pixel"],
        polarity=payload["polarity"],
    )
    params = DiameterDetectionParams(threshold_fraction=0.45, min_diameter_px=2.0)
    analysis = analyzer.analyze(params=params)

    figs = analyzer.plot(analysis, backend="matplotlib")
    plt.close(figs["kymograph"])
    plt.close(figs["diameter"])

    plotly_kym = plot_kymograph_with_edges_plotly_dict(
        payload["kymograph"],
        left_edge_px=analysis["left_edge_px"],
        right_edge_px=analysis["right_edge_px"],
    )
    plotly_diam = plot_diameter_vs_time_plotly_dict(
        analysis["time_s"], analysis["diameter_um"], ylabel="Diameter (um)"
    )

    finite_count = int(np.isfinite(analysis["diameter_px"]).sum())
    print(f"analysis keys: {sorted(analysis.keys())}")
    print(f"finite diameter points: {finite_count}")
    print(f"plotly kym dict keys: {sorted(plotly_kym.keys())}")
    print(f"plotly diameter traces: {len(plotly_diam['data'])}")


if __name__ == "__main__":
    main()
