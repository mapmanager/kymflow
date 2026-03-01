from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import numpy as np

from diameter_plots import (
    plot_diameter_vs_time_mpl,
    plot_diameter_vs_time_plotly_dict,
    plot_kymograph_with_edges_mpl,
    plot_kymograph_with_edges_plotly_dict,
)


VALID_POLARITIES = {"bright_on_dark", "dark_on_bright"}


@dataclass(frozen=True)
class DiameterDetectionParams:
    """Minimal, JSON-serializable parameter bundle for detection settings."""

    threshold_fraction: float = 0.5
    min_diameter_px: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "threshold_fraction": float(self.threshold_fraction),
            "min_diameter_px": float(self.min_diameter_px),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DiameterDetectionParams":
        return cls(
            threshold_fraction=float(payload["threshold_fraction"]),
            min_diameter_px=float(payload["min_diameter_px"]),
        )


class DiameterAnalyzer:
    """OO entry point for diameter analysis over a 2D kymograph (time x space)."""

    def __init__(
        self,
        kymograph: np.ndarray,
        *,
        seconds_per_line: float,
        um_per_pixel: float,
        polarity: str = "bright_on_dark",
    ) -> None:
        arr = np.asarray(kymograph, dtype=float)
        if arr.ndim != 2:
            raise ValueError("kymograph must be a 2D array with shape (time, space)")
        if seconds_per_line <= 0 or um_per_pixel <= 0:
            raise ValueError("seconds_per_line and um_per_pixel must be > 0")
        if polarity not in VALID_POLARITIES:
            raise ValueError(f"polarity must be one of {sorted(VALID_POLARITIES)}")

        self.kymograph = arr
        self.seconds_per_line = float(seconds_per_line)
        self.um_per_pixel = float(um_per_pixel)
        self.polarity = polarity

    def analyze(self, params: Optional[DiameterDetectionParams] = None) -> dict[str, np.ndarray]:
        """Placeholder analysis that estimates per-time diameter in pixels.

        This intentionally remains lightweight in ticket_001.
        """
        params = params or DiameterDetectionParams()

        n_time, n_space = self.kymograph.shape
        time_s = np.arange(n_time, dtype=float) * self.seconds_per_line

        diameter_px = np.full(n_time, np.nan, dtype=float)
        left_edge_px = np.full(n_time, np.nan, dtype=float)
        right_edge_px = np.full(n_time, np.nan, dtype=float)

        for idx in range(n_time):
            row = self.kymograph[idx]
            signal = row - np.nanmin(row)
            if self.polarity == "dark_on_bright":
                signal = np.nanmax(signal) - signal
            max_val = np.nanmax(signal)
            if not np.isfinite(max_val) or max_val <= 0:
                continue

            mask = signal >= (params.threshold_fraction * max_val)
            x_idx = np.flatnonzero(mask)
            if x_idx.size == 0:
                continue

            left = float(x_idx[0])
            right = float(x_idx[-1])
            width = right - left
            if width < params.min_diameter_px:
                continue

            left_edge_px[idx] = left
            right_edge_px[idx] = right
            diameter_px[idx] = width

        diameter_um = diameter_px * self.um_per_pixel

        return {
            "time_s": time_s,
            "diameter_px": diameter_px,
            "diameter_um": diameter_um,
            "left_edge_px": left_edge_px,
            "right_edge_px": right_edge_px,
        }

    @staticmethod
    def save_analysis(
        output_prefix: str | Path,
        analysis: dict[str, np.ndarray],
        params: DiameterDetectionParams,
    ) -> tuple[Path, Path]:
        """Save scaffold sidecars: `<prefix>_params.json` and `<prefix>_results.csv`."""
        prefix = Path(output_prefix)
        params_path = prefix.with_name(f"{prefix.name}_params.json")
        results_path = prefix.with_name(f"{prefix.name}_results.csv")

        params_path.write_text(json.dumps(params.to_dict(), indent=2), encoding="utf-8")

        header = "time_s,diameter_px,diameter_um"
        matrix = np.column_stack(
            [analysis["time_s"], analysis["diameter_px"], analysis["diameter_um"]]
        )
        np.savetxt(results_path, matrix, delimiter=",", header=header, comments="")
        return params_path, results_path

    @staticmethod
    def load_analysis(output_prefix: str | Path) -> dict[str, Any]:
        """Load scaffold sidecars produced by `save_analysis`.

        Returns a dictionary with `params` and `results` keys.
        """
        prefix = Path(output_prefix)
        params_path = prefix.with_name(f"{prefix.name}_params.json")
        results_path = prefix.with_name(f"{prefix.name}_results.csv")

        params_payload = json.loads(params_path.read_text(encoding="utf-8"))
        params = DiameterDetectionParams.from_dict(params_payload)

        arr = np.loadtxt(results_path, delimiter=",", skiprows=1)
        if arr.ndim == 1:
            arr = arr[None, :]

        return {
            "params": params,
            "results": {
                "time_s": arr[:, 0],
                "diameter_px": arr[:, 1],
                "diameter_um": arr[:, 2],
            },
        }

    def plot(self, analysis: dict[str, np.ndarray], *, backend: str = "matplotlib") -> Any:
        """Convenience plotting wrapper over composable plot helper functions."""
        if backend == "matplotlib":
            fig1 = plot_kymograph_with_edges_mpl(
                self.kymograph,
                left_edge_px=analysis.get("left_edge_px"),
                right_edge_px=analysis.get("right_edge_px"),
            )
            fig2 = plot_diameter_vs_time_mpl(
                analysis["time_s"], analysis["diameter_um"], ylabel="Diameter (um)"
            )
            return {"kymograph": fig1, "diameter": fig2}

        if backend == "plotly_dict":
            fig1 = plot_kymograph_with_edges_plotly_dict(
                self.kymograph,
                left_edge_px=analysis.get("left_edge_px"),
                right_edge_px=analysis.get("right_edge_px"),
            )
            fig2 = plot_diameter_vs_time_plotly_dict(
                analysis["time_s"], analysis["diameter_um"], ylabel="Diameter (um)"
            )
            return {"kymograph": fig1, "diameter": fig2}

        raise ValueError("backend must be 'matplotlib' or 'plotly_dict'")
