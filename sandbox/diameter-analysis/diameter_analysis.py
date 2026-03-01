from __future__ import annotations

import csv
import json
import math
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Optional

import numpy as np

from diameter_plots import (
    plot_diameter_vs_time_mpl,
    plot_diameter_vs_time_plotly_dict,
    plot_kymograph_with_edges_mpl,
    plot_kymograph_with_edges_plotly_dict,
)

ANALYSIS_SCHEMA_VERSION = 1
THREAD_CHUNK_SIZE = 512


class BinningMethod(str, Enum):
    MEAN = "mean"
    MEDIAN = "median"


class Polarity(str, Enum):
    BRIGHT_ON_DARK = "bright_on_dark"
    DARK_ON_BRIGHT = "dark_on_bright"


class DiameterMethod(str, Enum):
    THRESHOLD_WIDTH = "threshold_width"


@dataclass(frozen=True)
class DiameterDetectionParams:
    roi: tuple[int, int, int, int] | None = None
    window_rows_odd: int = 5
    stride: int = 1
    binning_method: BinningMethod = BinningMethod.MEAN
    polarity: Polarity = Polarity.BRIGHT_ON_DARK
    diameter_method: DiameterMethod = DiameterMethod.THRESHOLD_WIDTH
    threshold_mode: str = "half_max"
    threshold_value: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "roi": list(self.roi) if self.roi is not None else None,
            "window_rows_odd": int(self.window_rows_odd),
            "stride": int(self.stride),
            "binning_method": self.binning_method.value,
            "polarity": self.polarity.value,
            "diameter_method": self.diameter_method.value,
            "threshold_mode": self.threshold_mode,
            "threshold_value": self.threshold_value,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DiameterDetectionParams":
        roi_payload = payload.get("roi")
        roi: tuple[int, int, int, int] | None
        if roi_payload is None:
            roi = None
        else:
            if len(roi_payload) != 4:
                raise ValueError("roi must have four entries (t0, t1, x0, x1)")
            roi = tuple(int(v) for v in roi_payload)  # type: ignore[assignment]

        return cls(
            roi=roi,
            window_rows_odd=int(payload.get("window_rows_odd", 5)),
            stride=int(payload.get("stride", 1)),
            binning_method=BinningMethod(payload.get("binning_method", "mean")),
            polarity=Polarity(payload.get("polarity", "bright_on_dark")),
            diameter_method=DiameterMethod(payload.get("diameter_method", "threshold_width")),
            threshold_mode=str(payload.get("threshold_mode", "half_max")),
            threshold_value=(
                None
                if payload.get("threshold_value") is None
                else float(payload.get("threshold_value"))
            ),
        )


@dataclass
class DiameterResult:
    center_row: int
    time_s: float
    left_edge_px: float
    right_edge_px: float
    diameter_px: float
    peak: float
    baseline: float
    qc_score: float
    qc_flags: list[str]

    def to_row(self, *, roi_id: int, schema_version: int, um_per_pixel: float) -> dict[str, Any]:
        return {
            "schema_version": int(schema_version),
            "roi_id": int(roi_id),
            "center_row": int(self.center_row),
            "time_s": float(self.time_s),
            "left_edge_px": float(self.left_edge_px),
            "right_edge_px": float(self.right_edge_px),
            "diameter_px": float(self.diameter_px),
            "diameter_um": float(self.diameter_px * um_per_pixel),
            "peak": float(self.peak),
            "baseline": float(self.baseline),
            "qc_score": float(self.qc_score),
            "qc_flags": "|".join(self.qc_flags),
        }

    @classmethod
    def from_row(cls, row: dict[str, str]) -> "DiameterResult":
        qc_flags = row.get("qc_flags", "")
        return cls(
            center_row=int(row["center_row"]),
            time_s=float(row["time_s"]),
            left_edge_px=float(row["left_edge_px"]),
            right_edge_px=float(row["right_edge_px"]),
            diameter_px=float(row["diameter_px"]),
            peak=float(row["peak"]),
            baseline=float(row["baseline"]),
            qc_score=float(row["qc_score"]),
            qc_flags=[f for f in qc_flags.split("|") if f],
        )


class DiameterAnalyzer:
    """Diameter analysis over kymographs with serial and thread backends.

    ROI convention is half-open: `(t0, t1, x0, x1)`.
    """

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

        try:
            self.polarity = Polarity(polarity)
        except ValueError as exc:
            raise ValueError("polarity must be bright_on_dark or dark_on_bright") from exc

        self.kymograph = arr
        self.seconds_per_line = float(seconds_per_line)
        self.um_per_pixel = float(um_per_pixel)

    def analyze(
        self,
        params: Optional[DiameterDetectionParams] = None,
        *,
        backend: str = "serial",
    ) -> list[DiameterResult]:
        cfg = params or DiameterDetectionParams(polarity=self.polarity)
        cfg = self._validated_params(cfg)

        t0, t1, x0, x1 = self._resolve_roi(cfg.roi)
        centers = list(range(t0, t1, cfg.stride))

        if backend == "serial":
            results = [self._analyze_center(i, cfg, t0, t1, x0, x1) for i in centers]
        elif backend == "threads":
            results = self._analyze_threads(centers, cfg, t0, t1, x0, x1)
        else:
            raise ValueError("backend must be 'serial' or 'threads'")

        results.sort(key=lambda r: r.center_row)
        return results

    def _analyze_threads(
        self,
        centers: list[int],
        params: DiameterDetectionParams,
        t0: int,
        t1: int,
        x0: int,
        x1: int,
    ) -> list[DiameterResult]:
        def _chunked(values: list[int], size: int) -> Iterable[list[int]]:
            for start in range(0, len(values), size):
                yield values[start : start + size]

        def _process_chunk(chunk: list[int]) -> list[DiameterResult]:
            return [self._analyze_center(i, params, t0, t1, x0, x1) for i in chunk]

        chunks = list(_chunked(centers, THREAD_CHUNK_SIZE))
        with ThreadPoolExecutor() as executor:
            out_chunks = list(executor.map(_process_chunk, chunks))

        flattened: list[DiameterResult] = []
        for block in out_chunks:
            flattened.extend(block)
        return flattened

    def _analyze_center(
        self,
        center_row: int,
        params: DiameterDetectionParams,
        t0: int,
        t1: int,
        x0: int,
        x1: int,
    ) -> DiameterResult:
        window_half = params.window_rows_odd // 2
        w0 = max(t0, center_row - window_half)
        w1 = min(t1, center_row + window_half + 1)

        window = self.kymograph[w0:w1, x0:x1]
        if params.binning_method == BinningMethod.MEAN:
            profile = np.nanmean(window, axis=0)
        else:
            profile = np.nanmedian(window, axis=0)

        profile_proc = np.asarray(profile, dtype=float)
        if params.polarity == Polarity.DARK_ON_BRIGHT:
            profile_proc = np.nanmax(profile_proc) - profile_proc

        baseline = float(np.nanpercentile(profile_proc, 10))
        peak = float(np.nanpercentile(profile_proc, 90))
        contrast = peak - baseline

        left_edge, right_edge, diameter, edge_flags = self._threshold_width(profile_proc, params, x0)
        qc_score, qc_flags = self._qc_metrics(profile_proc, baseline, peak, edge_flags)

        return DiameterResult(
            center_row=int(center_row),
            time_s=float(center_row * self.seconds_per_line),
            left_edge_px=float(left_edge),
            right_edge_px=float(right_edge),
            diameter_px=float(diameter),
            peak=peak,
            baseline=baseline,
            qc_score=qc_score,
            qc_flags=qc_flags,
        )

    def _threshold_width(
        self,
        profile: np.ndarray,
        params: DiameterDetectionParams,
        x0: int,
    ) -> tuple[float, float, float, list[str]]:
        flags: list[str] = []
        if profile.size == 0 or not np.any(np.isfinite(profile)):
            return math.nan, math.nan, math.nan, ["empty_profile"]

        finite = profile[np.isfinite(profile)]
        baseline = float(np.nanpercentile(finite, 10))
        peak = float(np.nanpercentile(finite, 90))
        if params.threshold_mode == "half_max":
            threshold = baseline + 0.5 * (peak - baseline)
        elif params.threshold_mode == "absolute" and params.threshold_value is not None:
            threshold = params.threshold_value
        else:
            raise ValueError("threshold_mode must be 'half_max' or absolute with threshold_value")

        above = profile >= threshold
        if not np.any(above):
            return math.nan, math.nan, math.nan, ["missing_left_edge", "missing_right_edge"]

        left_idx = int(np.argmax(above))
        right_idx = int(len(above) - 1 - np.argmax(above[::-1]))

        left_edge = float(left_idx + x0)
        right_edge = float(right_idx + x0)
        diameter = right_edge - left_edge

        if left_idx == 0:
            flags.append("missing_left_edge")
            left_edge = math.nan
        if right_idx == len(above) - 1:
            flags.append("missing_right_edge")
            right_edge = math.nan
        if not np.isfinite(left_edge) or not np.isfinite(right_edge):
            diameter = math.nan

        return left_edge, right_edge, diameter, flags

    @staticmethod
    def _qc_metrics(
        profile: np.ndarray,
        baseline: float,
        peak: float,
        edge_flags: list[str],
    ) -> tuple[float, list[str]]:
        flags = list(edge_flags)
        contrast = peak - baseline

        if not np.isfinite(contrast) or contrast <= 0:
            flags.append("low_contrast")

        pmin = float(np.nanmin(profile))
        pmax = float(np.nanmax(profile))
        saturated = bool(pmin <= 0.005 or pmax >= 0.995)
        if saturated:
            flags.append("saturation")

        double_peak = False
        if profile.size >= 3 and np.isfinite(contrast) and contrast > 0:
            center = profile[1:-1]
            peaks = (center > profile[:-2]) & (center >= profile[2:])
            strong = center >= (baseline + 0.8 * contrast)
            double_peak = int(np.count_nonzero(peaks & strong)) >= 2
        if double_peak:
            flags.append("double_peak")

        score = 1.0
        if "low_contrast" in flags:
            score -= 0.55
        if "missing_left_edge" in flags:
            score -= 0.25
        if "missing_right_edge" in flags:
            score -= 0.25
        if "saturation" in flags:
            score -= 0.1
        if "double_peak" in flags:
            score -= 0.15

        score = float(np.clip(score, 0.0, 1.0))
        return score, sorted(set(flags))

    def _resolve_roi(self, roi: tuple[int, int, int, int] | None) -> tuple[int, int, int, int]:
        n_time, n_space = self.kymograph.shape
        if roi is None:
            return 0, n_time, 0, n_space

        t0, t1, x0, x1 = (int(v) for v in roi)
        if not (0 <= t0 < t1 <= n_time):
            raise ValueError("roi time bounds must satisfy 0 <= t0 < t1 <= n_time")
        if not (0 <= x0 < x1 <= n_space):
            raise ValueError("roi space bounds must satisfy 0 <= x0 < x1 <= n_space")
        return t0, t1, x0, x1

    def _validated_params(self, params: DiameterDetectionParams) -> DiameterDetectionParams:
        if params.window_rows_odd < 1 or params.window_rows_odd % 2 == 0:
            raise ValueError("window_rows_odd must be odd and >= 1")
        if params.stride < 1:
            raise ValueError("stride must be >= 1")
        return params

    @staticmethod
    def save_analysis(
        output_dir: str | Path,
        params_by_roi: dict[int, DiameterDetectionParams],
        results_by_roi: dict[int, list[DiameterResult]],
        *,
        um_per_pixel: float,
    ) -> tuple[Path, Path]:
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)

        params_path = output / "analysis_params.json"
        results_path = output / "analysis_results.csv"

        params_payload = {
            "schema_version": ANALYSIS_SCHEMA_VERSION,
            "rois": {str(k): v.to_dict() for k, v in sorted(params_by_roi.items())},
        }
        params_path.write_text(json.dumps(params_payload, indent=2), encoding="utf-8")

        fieldnames = [
            "schema_version",
            "roi_id",
            "center_row",
            "time_s",
            "left_edge_px",
            "right_edge_px",
            "diameter_px",
            "diameter_um",
            "peak",
            "baseline",
            "qc_score",
            "qc_flags",
        ]
        with results_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for roi_id in sorted(results_by_roi):
                for result in results_by_roi[roi_id]:
                    writer.writerow(
                        result.to_row(
                            roi_id=roi_id,
                            schema_version=ANALYSIS_SCHEMA_VERSION,
                            um_per_pixel=um_per_pixel,
                        )
                    )

        return params_path, results_path

    @staticmethod
    def load_analysis(output_dir: str | Path) -> dict[str, Any]:
        output = Path(output_dir)
        params_path = output / "analysis_params.json"
        results_path = output / "analysis_results.csv"

        params_payload = json.loads(params_path.read_text(encoding="utf-8"))
        if int(params_payload.get("schema_version", -1)) != ANALYSIS_SCHEMA_VERSION:
            raise ValueError("Unsupported params schema_version")

        rois_raw = params_payload.get("rois")
        if not isinstance(rois_raw, dict):
            raise ValueError("analysis_params.json must contain 'rois' mapping")

        params_by_roi = {
            int(roi_id): DiameterDetectionParams.from_dict(cfg)
            for roi_id, cfg in rois_raw.items()
        }

        results_by_roi: dict[int, list[DiameterResult]] = {}
        with results_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row_version = int(row.get("schema_version", -1))
                if row_version != ANALYSIS_SCHEMA_VERSION:
                    raise ValueError("Unsupported results schema_version")
                roi_id = int(row["roi_id"])
                results_by_roi.setdefault(roi_id, []).append(DiameterResult.from_row(row))

        for roi_id in results_by_roi:
            results_by_roi[roi_id].sort(key=lambda r: r.center_row)

        return {
            "schema_version": ANALYSIS_SCHEMA_VERSION,
            "params_by_roi": params_by_roi,
            "results_by_roi": results_by_roi,
        }

    def plot(self, results: list[DiameterResult], *, backend: str = "matplotlib") -> Any:
        if backend == "matplotlib":
            fig1 = plot_kymograph_with_edges_mpl(self.kymograph, results)
            fig2 = plot_diameter_vs_time_mpl(results, um_per_pixel=self.um_per_pixel)
            return {"kymograph": fig1, "diameter": fig2}

        if backend == "plotly_dict":
            fig1 = plot_kymograph_with_edges_plotly_dict(self.kymograph, results)
            fig2 = plot_diameter_vs_time_plotly_dict(results, um_per_pixel=self.um_per_pixel)
            return {"kymograph": fig1, "diameter": fig2}

        raise ValueError("backend must be 'matplotlib' or 'plotly_dict'")
