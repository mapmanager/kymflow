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

from serialization import dataclass_from_dict, dataclass_to_dict
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
    GRADIENT_EDGES = "gradient_edges"


class PostFilterType(str, Enum):
    MEDIAN = "median"
    HAMPEL = "hampel"


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
    gradient_sigma: float = 1.5
    gradient_kernel: str = "central_diff"
    gradient_min_edge_strength: float = 0.02

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DiameterDetectionParams":
        obj = dataclass_from_dict(cls, payload)
        if obj.roi is not None and len(obj.roi) != 4:
            raise ValueError("roi must have four entries (t0, t1, x0, x1)")
        return obj


@dataclass(frozen=True)
class PostFilterParams:
    enabled: bool = False
    filter_type: PostFilterType = PostFilterType.MEDIAN
    kernel_size: int = 3
    hampel_n_sigma: float = 3.0
    hampel_scale: str = "mad"

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PostFilterParams":
        return dataclass_from_dict(cls, payload)


@dataclass(frozen=True)
class KymographPayload:
    kymograph: np.ndarray
    seconds_per_line: float
    um_per_pixel: float
    polarity: str = "bright_on_dark"
    source: str = "synthetic"
    path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "KymographPayload":
        obj = dataclass_from_dict(cls, payload)
        return cls(
            kymograph=np.asarray(obj.kymograph),
            seconds_per_line=float(obj.seconds_per_line),
            um_per_pixel=float(obj.um_per_pixel),
            polarity=str(obj.polarity),
            source=str(obj.source),
            path=None if obj.path is None else str(obj.path),
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
    edge_strength_left: float
    edge_strength_right: float
    diameter_px_filt: float
    diameter_was_filtered: bool
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
            "edge_strength_left": float(self.edge_strength_left),
            "edge_strength_right": float(self.edge_strength_right),
            "diameter_px_filt": float(self.diameter_px_filt),
            "diameter_um_filt": float(self.diameter_px_filt * um_per_pixel),
            "diameter_was_filtered": int(bool(self.diameter_was_filtered)),
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
            edge_strength_left=float(row.get("edge_strength_left", "nan")),
            edge_strength_right=float(row.get("edge_strength_right", "nan")),
            diameter_px_filt=float(row.get("diameter_px_filt", row["diameter_px"])),
            diameter_was_filtered=bool(int(row.get("diameter_was_filtered", "0"))),
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
        post_filter_params: Optional[PostFilterParams] = None,
    ) -> list[DiameterResult]:
        cfg = params or DiameterDetectionParams(polarity=self.polarity)
        cfg = self._validated_params(cfg)
        pf_cfg = self._validated_post_filter_params(post_filter_params or PostFilterParams())

        t0, t1, x0, x1 = self._resolve_roi(cfg.roi)
        centers = list(range(t0, t1, cfg.stride))

        if backend == "serial":
            results = [self._analyze_center(i, cfg, t0, t1, x0, x1) for i in centers]
        elif backend == "threads":
            results = self._analyze_threads(centers, cfg, t0, t1, x0, x1)
        else:
            raise ValueError("backend must be 'serial' or 'threads'")

        results.sort(key=lambda r: r.center_row)
        if pf_cfg.enabled:
            self._apply_post_filter(results=results, params=pf_cfg)
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

        # Analysis operates on float profiles and does not assume normalized [0,1] intensity.
        profile_proc = np.asarray(profile, dtype=float)
        if params.polarity == Polarity.DARK_ON_BRIGHT:
            profile_proc = np.nanmax(profile_proc) - profile_proc

        baseline = float(np.nanpercentile(profile_proc, 10))
        peak = float(np.nanpercentile(profile_proc, 90))

        if params.diameter_method == DiameterMethod.THRESHOLD_WIDTH:
            left_edge, right_edge, diameter, edge_flags = self._threshold_width(profile_proc, params, x0)
            edge_strength_left = math.nan
            edge_strength_right = math.nan
        elif params.diameter_method == DiameterMethod.GRADIENT_EDGES:
            (
                left_edge,
                right_edge,
                diameter,
                edge_strength_left,
                edge_strength_right,
                edge_flags,
            ) = self._gradient_edges(profile_proc, params, x0)
        else:
            raise ValueError(f"Unsupported diameter_method={params.diameter_method!r}")

        qc_score, qc_flags = self._qc_metrics(
            profile=profile_proc,
            baseline=baseline,
            peak=peak,
            edge_flags=edge_flags,
            edge_strength_left=edge_strength_left,
            edge_strength_right=edge_strength_right,
            edge_strength_threshold=params.gradient_min_edge_strength,
        )

        return DiameterResult(
            center_row=int(center_row),
            time_s=float(center_row * self.seconds_per_line),
            left_edge_px=float(left_edge),
            right_edge_px=float(right_edge),
            diameter_px=float(diameter),
            peak=peak,
            baseline=baseline,
            edge_strength_left=float(edge_strength_left),
            edge_strength_right=float(edge_strength_right),
            diameter_px_filt=float(diameter),
            diameter_was_filtered=False,
            qc_score=qc_score,
            qc_flags=qc_flags,
        )

    @staticmethod
    def _nan_safe_median_filter(series: np.ndarray, kernel_size: int) -> np.ndarray:
        x = np.asarray(series, dtype=float)
        out = x.copy()
        n = x.size
        half = kernel_size // 2
        for i in range(n):
            if not np.isfinite(x[i]):
                continue
            i0 = max(0, i - half)
            i1 = min(n, i + half + 1)
            win = x[i0:i1]
            valid = win[np.isfinite(win)]
            if valid.size > 0:
                out[i] = float(np.median(valid))
        return out

    @staticmethod
    def _nan_safe_hampel_filter(
        series: np.ndarray,
        kernel_size: int,
        n_sigma: float,
        scale: str = "mad",
    ) -> tuple[np.ndarray, np.ndarray]:
        x = np.asarray(series, dtype=float)
        out = x.copy()
        replaced = np.zeros(x.size, dtype=bool)
        half = kernel_size // 2

        for i in range(x.size):
            xi = x[i]
            if not np.isfinite(xi):
                continue
            i0 = max(0, i - half)
            i1 = min(x.size, i + half + 1)
            win = x[i0:i1]
            valid = win[np.isfinite(win)]
            if valid.size < 2:
                continue
            med = float(np.median(valid))
            if scale == "mad":
                mad = float(np.median(np.abs(valid - med)))
                sigma_est = 1.4826 * mad
            else:
                raise ValueError("hampel_scale must be 'mad'")

            if sigma_est <= 0:
                continue
            if abs(xi - med) > (n_sigma * sigma_est):
                out[i] = med
                replaced[i] = True
        return out, replaced

    @classmethod
    def _apply_post_filter(cls, results: list[DiameterResult], params: PostFilterParams) -> None:
        if not results:
            return
        raw = np.asarray([r.diameter_px for r in results], dtype=float)
        if params.filter_type == PostFilterType.MEDIAN:
            filtered = cls._nan_safe_median_filter(raw, kernel_size=params.kernel_size)
            replaced = np.isfinite(raw) & np.isfinite(filtered) & (~np.isclose(raw, filtered))
        elif params.filter_type == PostFilterType.HAMPEL:
            filtered, replaced = cls._nan_safe_hampel_filter(
                raw,
                kernel_size=params.kernel_size,
                n_sigma=params.hampel_n_sigma,
                scale=params.hampel_scale,
            )
        else:
            raise ValueError(f"Unsupported PostFilterType={params.filter_type!r}")

        for i, r in enumerate(results):
            r.diameter_px_filt = float(filtered[i])
            r.diameter_was_filtered = bool(replaced[i])

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

    def _gradient_edges(
        self,
        profile: np.ndarray,
        params: DiameterDetectionParams,
        x0: int,
    ) -> tuple[float, float, float, float, float, list[str]]:
        if profile.size == 0 or not np.any(np.isfinite(profile)):
            return math.nan, math.nan, math.nan, math.nan, math.nan, ["empty_profile"]

        finite_profile = self._fill_nan_1d(profile)
        smooth = self._smooth_profile(finite_profile, sigma=params.gradient_sigma)

        if params.gradient_kernel != "central_diff":
            raise ValueError("gradient_kernel must be 'central_diff'")
        deriv = np.gradient(smooth)

        left_idx = int(np.argmax(deriv))
        right_idx = int(np.argmin(deriv))
        edge_strength_left = float(max(0.0, deriv[left_idx]))
        edge_strength_right = float(max(0.0, -deriv[right_idx]))

        flags: list[str] = []
        if left_idx >= right_idx:
            flags.append("gradient_invalid_order")
            return (
                math.nan,
                math.nan,
                math.nan,
                edge_strength_left,
                edge_strength_right,
                flags,
            )

        if (
            edge_strength_left < params.gradient_min_edge_strength
            or edge_strength_right < params.gradient_min_edge_strength
        ):
            flags.append("gradient_low_edge_strength")

        left_edge = float(left_idx + x0)
        right_edge = float(right_idx + x0)
        diameter = float(right_edge - left_edge)
        return left_edge, right_edge, diameter, edge_strength_left, edge_strength_right, flags

    @staticmethod
    def _fill_nan_1d(values: np.ndarray) -> np.ndarray:
        out = np.asarray(values, dtype=float).copy()
        mask = np.isfinite(out)
        if np.all(mask):
            return out
        if not np.any(mask):
            return np.zeros_like(out)

        x = np.arange(out.size, dtype=float)
        out[~mask] = np.interp(x[~mask], x[mask], out[mask])
        return out

    @staticmethod
    def _smooth_profile(profile: np.ndarray, sigma: float) -> np.ndarray:
        if sigma <= 0:
            return profile.copy()

        try:
            from scipy.ndimage import gaussian_filter1d  # type: ignore

            return gaussian_filter1d(profile, sigma=sigma, mode="nearest")
        except Exception:
            radius = max(1, int(round(3.0 * sigma)))
            x = np.arange(-radius, radius + 1, dtype=float)
            kernel = np.exp(-0.5 * (x / sigma) ** 2)
            kernel /= np.sum(kernel)
            return np.convolve(profile, kernel, mode="same")

    @staticmethod
    def _qc_metrics(
        profile: np.ndarray,
        baseline: float,
        peak: float,
        edge_flags: list[str],
        edge_strength_left: float,
        edge_strength_right: float,
        edge_strength_threshold: float,
    ) -> tuple[float, list[str]]:
        flags = list(edge_flags)
        contrast = peak - baseline

        if not np.isfinite(contrast) or contrast <= 0:
            flags.append("low_contrast")

        pmin = float(np.nanmin(profile))
        pmax = float(np.nanmax(profile))
        dynamic_range = pmax - pmin
        if dynamic_range > 0:
            p01 = float(np.nanpercentile(profile, 1))
            p99 = float(np.nanpercentile(profile, 99))
            low_tail = (p01 - pmin) / dynamic_range
            high_tail = (pmax - p99) / dynamic_range
            saturated = bool(low_tail < 0.01 or high_tail < 0.01)
        else:
            saturated = True
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

        if np.isfinite(edge_strength_left) and np.isfinite(edge_strength_right):
            min_strength = min(edge_strength_left, edge_strength_right)
            if min_strength < edge_strength_threshold:
                flags.append("gradient_low_edge_strength")

            if np.isfinite(contrast) and contrast > 0:
                strength_ratio = min_strength / (contrast + 1e-12)
                if strength_ratio < 0.2:
                    flags.append("gradient_low_edge_strength")

        score = 1.0
        if "low_contrast" in flags:
            score -= 0.55
        if "missing_left_edge" in flags:
            score -= 0.25
        if "missing_right_edge" in flags:
            score -= 0.25
        if "gradient_invalid_order" in flags:
            score -= 0.35
        if "gradient_low_edge_strength" in flags:
            score -= 0.2
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
        if params.gradient_sigma < 0:
            raise ValueError("gradient_sigma must be >= 0")
        if params.gradient_min_edge_strength < 0:
            raise ValueError("gradient_min_edge_strength must be >= 0")
        if params.gradient_kernel != "central_diff":
            raise ValueError("gradient_kernel must be 'central_diff'")
        return params

    @staticmethod
    def _validated_post_filter_params(params: PostFilterParams) -> PostFilterParams:
        if params.kernel_size < 3 or params.kernel_size % 2 == 0:
            raise ValueError("PostFilterParams.kernel_size must be odd and >= 3")
        if params.hampel_n_sigma <= 0:
            raise ValueError("PostFilterParams.hampel_n_sigma must be > 0")
        if params.hampel_scale != "mad":
            raise ValueError("PostFilterParams.hampel_scale must be 'mad'")
        return params

    @staticmethod
    def save_analysis(
        output_dir: str | Path,
        params_by_roi: dict[int, DiameterDetectionParams],
        results_by_roi: dict[int, list[DiameterResult]],
        *,
        um_per_pixel: float,
        post_filter_params_by_roi: Optional[dict[int, PostFilterParams]] = None,
    ) -> tuple[Path, Path]:
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)

        params_path = output / "analysis_params.json"
        results_path = output / "analysis_results.csv"

        pf_map = post_filter_params_by_roi or {}
        params_payload = {
            "schema_version": ANALYSIS_SCHEMA_VERSION,
            "rois": {str(k): v.to_dict() for k, v in sorted(params_by_roi.items())},
            "post_filter_params": {str(k): v.to_dict() for k, v in sorted(pf_map.items())},
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
            "edge_strength_left",
            "edge_strength_right",
            "diameter_px_filt",
            "diameter_um_filt",
            "diameter_was_filtered",
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
        pf_raw = params_payload.get("post_filter_params", {})
        if not isinstance(pf_raw, dict):
            raise ValueError("analysis_params.json 'post_filter_params' must be an object")
        post_filter_params_by_roi = {
            int(roi_id): PostFilterParams.from_dict(cfg) for roi_id, cfg in pf_raw.items()
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
            "post_filter_params_by_roi": post_filter_params_by_roi,
            "results_by_roi": results_by_roi,
        }

    def plot(
        self,
        results: list[DiameterResult],
        *,
        backend: str = "matplotlib",
        use_filtered: bool = True,
        show_raw: bool = False,
    ) -> Any:
        if backend == "matplotlib":
            fig1 = plot_kymograph_with_edges_mpl(
                self.kymograph,
                results,
                seconds_per_line=self.seconds_per_line,
                um_per_pixel=self.um_per_pixel,
            )
            fig2 = plot_diameter_vs_time_mpl(
                results,
                um_per_pixel=self.um_per_pixel,
                use_filtered=use_filtered,
                show_raw=show_raw,
            )
            return {"kymograph": fig1, "diameter": fig2}

        if backend == "plotly_dict":
            fig1 = plot_kymograph_with_edges_plotly_dict(
                self.kymograph,
                results,
                seconds_per_line=self.seconds_per_line,
                um_per_pixel=self.um_per_pixel,
            )
            fig2 = plot_diameter_vs_time_plotly_dict(
                results,
                um_per_pixel=self.um_per_pixel,
                use_filtered=use_filtered,
                show_raw=show_raw,
            )
            return {"kymograph": fig1, "diameter": fig2}

        raise ValueError("backend must be 'matplotlib' or 'plotly_dict'")
