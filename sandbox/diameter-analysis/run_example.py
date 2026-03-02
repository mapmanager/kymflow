from __future__ import annotations
import time

import os

import matplotlib.pyplot as plt
import numpy as np

from diameter_analysis import (
    DiameterAnalyzer,
    DiameterDetectionParams,
    DiameterMethod,
    PostFilterParams,
    PostFilterType,
)
from diameter_plots import (
    plot_diameter_vs_time_mpl,
    plot_diameter_vs_time_plotly_dict,
    plot_kymograph_with_edges_mpl,
    plot_kymograph_with_edges_plotly_dict,
)
from synthetic_kymograph import SyntheticKymographParams, generate_synthetic_kymograph


def _run_one_method(
    analyzer: DiameterAnalyzer,
    payload: dict,
    method: DiameterMethod,
    post_filter_params: PostFilterParams,
) -> None:
    params = DiameterDetectionParams(
        window_rows_odd=5,
        stride=2,
        roi=(0, int(payload["kymograph"].shape[0]), 0, int(payload["kymograph"].shape[1])),
        diameter_method=method,
    )
    
    _time_start = time.time()
    results = analyzer.analyze(
        params=params,
        backend="threads",
        post_filter_params=post_filter_params,
    )
    _time_end = time.time()
    print(f"analyze time: {_time_end - _time_start:.2f} seconds")

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
        use_filtered=True,
        show_raw=True,
        ax=ax1,
    )
    fig.suptitle(f"Method: {method.value}")
    fig.tight_layout()
    # plt.close(fig)

    if 0:
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
            use_filtered=True,
            show_raw=True,
        )

    diameter_px = np.array([r.diameter_px for r in results], dtype=float)
    diameter_px_filt = np.array([r.diameter_px_filt for r in results], dtype=float)
    replaced_count = int(np.sum([r.diameter_was_filtered for r in results]))
    finite_count = int(np.isfinite(diameter_px).sum())
    finite_filt_count = int(np.isfinite(diameter_px_filt).sum())
    print(f"method: {method.value}")
    print(
        "post filter:",
        post_filter_params.filter_type.value,
        f"kernel={post_filter_params.kernel_size}",
        f"enabled={post_filter_params.enabled}",
    )
    print(f"results count: {len(results)}")
    print(f"finite diameter points: {finite_count}")
    print(f"finite filtered diameter points: {finite_filt_count}")
    print(f"filtered replacements: {replaced_count}")
    if 0:
        print(f"plotly kym dict keys: {sorted(plotly_kym.keys())}")
        print(f"plotly diameter traces: {len(plotly_diam['data'])}")


def main() -> None:
    # payload = generate_synthetic_kymograph(n_time=220, n_space=150, seed=1)
    payload = generate_synthetic_kymograph(n_time=2000,n_space=80,
                                seconds_per_line=0.001, um_per_pixel=0.15,
                                seed=1)


    kym = payload["kymograph"]
    print(f"kym shape: {kym.shape} min:{np.min(kym)} max:{np.max(kym)} {kym.dtype}")
    
    analyzer = DiameterAnalyzer(
        payload["kymograph"],
        seconds_per_line=payload["seconds_per_line"],
        um_per_pixel=payload["um_per_pixel"],
        polarity=payload["polarity"],
    )

    post_filter_params = PostFilterParams(
        enabled=True,
        filter_type=PostFilterType.HAMPEL,
        kernel_size=5,
        hampel_n_sigma=3.0,
    )
    for method in (DiameterMethod.THRESHOLD_WIDTH, DiameterMethod.GRADIENT_EDGES):
        _run_one_method(analyzer, payload, method, post_filter_params)

    if os.environ.get("DIAMETER_EXAMPLE_SHOW", "0") == "1":
        plt.show()
    else:
        plt.close("all")
    if os.environ.get("DIAMETER_EXAMPLE_NOISE_DEMO", "0") == "1":
        noisy_params = SyntheticKymographParams(
            n_time=220,
            n_space=150,
            seed=11,
            output_dtype="uint16",
            effective_bits=11,
            baseline_counts=220.0,
            signal_peak_counts=1050.0,
            bright_band_enabled=True,
            bright_band_x_center_px=100,
            bright_band_width_px=8,
            bright_band_amplitude_counts=600.0,
            bright_band_saturate=True,
            bg_gaussian_sigma_frac=0.015,
            speckle_sigma_frac=0.1,
        )
        noisy_payload = generate_synthetic_kymograph(synthetic_params=noisy_params)
        print(
            "noise demo:",
            noisy_payload["kymograph"].dtype,
            int(np.max(noisy_payload["kymograph"])),
            noisy_payload["synthetic_params"]["max_counts"],
        )


if __name__ == "__main__":
    main()
