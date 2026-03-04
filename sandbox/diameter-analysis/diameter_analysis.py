from __future__ import annotations

import csv
import json
import math
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar, Iterable, Literal, Optional

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
ALIGNED_RESULTS_SCHEMA_VERSION = 1


class BinningMethod(str, Enum):
    """Window aggregation mode for building a per-frame 1D profile."""
    MEAN = "mean"
    MEDIAN = "median"


class Polarity(str, Enum):
    """Intensity polarity used before edge detection."""
    BRIGHT_ON_DARK = "bright_on_dark"
    DARK_ON_BRIGHT = "dark_on_bright"


class DiameterMethod(str, Enum):
    """Primary edge-detection backend used for diameter estimation."""
    THRESHOLD_WIDTH = "threshold_width"
    GRADIENT_EDGES = "gradient_edges"


class PostFilterType(str, Enum):
    MEDIAN = "median"
    HAMPEL = "hampel"


@dataclass(frozen=True)
class DiameterDetectionParams:
    """Configuration for the diameter detection pipeline.

    Attributes:
        window_rows_odd: Odd temporal window size (rows) used to create a
            1D spatial profile around each center row. Units: pixels (time rows).
            Used by all methods.
        stride: Step between analyzed center rows. Units: pixels (time rows).
            Used by all methods.
        binning_method: Aggregation strategy across rows in each temporal window.
            Used by all methods.
        polarity: Brightness convention. `dark_on_bright` inverts the profile
            before edge detection. Used by all methods.
        diameter_method: Core detector implementation:
            `threshold_width` or `gradient_edges`.
        threshold_mode: Threshold behavior for `threshold_width`:
            `half_max` or `absolute`.
        threshold_value: Absolute threshold value used only when
            `threshold_mode='absolute'`. Ignored otherwise.
        gradient_sigma: Gaussian smoothing sigma in pixels for `gradient_edges`.
            Ignored by `threshold_width`.
        gradient_kernel: Gradient operator choice for `gradient_edges`.
            Currently only `central_diff` is supported.
        gradient_min_edge_strength: Minimum derivative magnitude threshold for
            edge-confidence flags in `gradient_edges`. Ignored by `threshold_width`.
        max_edge_shift_um_on: Enables/disables left/right edge displacement
            gating for `gradient_edges`.
        max_diameter_change_um_on: Enables/disables diameter jump gating for
            `gradient_edges`.
        max_center_shift_um_on: Enables/disables centerline shift gating for
            `gradient_edges`.
        max_edge_shift_um: Maximum allowed per-frame left/right edge shift in
            microns before flagging/rejecting a frame.
        max_diameter_change_um: Maximum allowed per-frame diameter jump in
            microns before flagging/rejecting a frame.
        max_center_shift_um: Maximum allowed per-frame center shift in microns
            before flagging/rejecting a frame.
    """
    window_rows_odd: int = field(
        default=5,
        metadata={
            "description": "Odd number of time rows to aggregate into each spatial profile.",
            "units": "px (time rows)",
            "methods": ["threshold_width", "gradient_edges"],
            "constraints": "odd integer >= 1",
        },
    )
    stride: int = field(
        default=1,
        metadata={
            "description": "Center-row increment between successive measurements.",
            "units": "px (time rows)",
            "methods": ["threshold_width", "gradient_edges"],
            "constraints": "integer >= 1",
        },
    )
    binning_method: BinningMethod = field(
        default=BinningMethod.MEAN,
        metadata={
            "description": "Window reducer: mean or median across rows before edge detection.",
            "units": "unitless",
            "methods": ["threshold_width", "gradient_edges"],
            "constraints": "mean | median",
        },
    )
    polarity: Polarity = field(
        default=Polarity.BRIGHT_ON_DARK,
        metadata={
            "description": "Intensity polarity; dark_on_bright inverts profile prior to detection.",
            "units": "unitless",
            "methods": ["threshold_width", "gradient_edges"],
            "constraints": "bright_on_dark | dark_on_bright",
        },
    )
    diameter_method: DiameterMethod = field(
        default=DiameterMethod.THRESHOLD_WIDTH,
        metadata={
            "description": "Primary detector implementation.",
            "units": "unitless",
            "methods": ["threshold_width", "gradient_edges"],
            "constraints": "threshold_width | gradient_edges",
        },
    )
    threshold_mode: str = field(
        default="half_max",
        metadata={
            "description": "Threshold rule for threshold_width: half_max or absolute.",
            "units": "unitless",
            "methods": ["threshold_width"],
            "constraints": "half_max | absolute",
        },
    )
    threshold_value: float | None = field(
        default=None,
        metadata={
            "description": "Absolute threshold value used when threshold_mode='absolute'.",
            "units": "intensity",
            "methods": ["threshold_width"],
            "constraints": "required when threshold_mode=absolute",
        },
    )
    gradient_sigma: float = field(
        default=1.5,
        metadata={
            "description": "Gaussian smoothing sigma for gradient-based edge finding.",
            "units": "px",
            "methods": ["gradient_edges"],
            "constraints": "float >= 0",
        },
    )
    gradient_kernel: str = field(
        default="central_diff",
        metadata={
            "description": "Derivative kernel used by gradient_edges.",
            "units": "unitless",
            "methods": ["gradient_edges"],
            "constraints": "currently central_diff only",
        },
    )
    gradient_min_edge_strength: float = field(
        default=0.02,
        metadata={
            "description": "Minimum derivative magnitude considered a confident edge.",
            "units": "intensity/px",
            "methods": ["gradient_edges"],
            "constraints": "float >= 0",
        },
    )
    max_edge_shift_um_on: bool = field(
        default=True,
        metadata={
            "description": "Enable edge-shift motion gating for gradient_edges.",
            "units": "unitless",
            "methods": ["gradient_edges"],
            "constraints": "bool",
        },
    )
    max_diameter_change_um_on: bool = field(
        default=True,
        metadata={
            "description": "Enable diameter-change motion gating for gradient_edges.",
            "units": "unitless",
            "methods": ["gradient_edges"],
            "constraints": "bool",
        },
    )
    max_center_shift_um_on: bool = field(
        default=True,
        metadata={
            "description": "Enable center-shift motion gating for gradient_edges.",
            "units": "unitless",
            "methods": ["gradient_edges"],
            "constraints": "bool",
        },
    )
    max_edge_shift_um: float = field(
        default=2.0,
        metadata={
            "description": "Max left/right edge shift allowed between adjacent frames.",
            "units": "um",
            "methods": ["gradient_edges"],
            "constraints": "float >= 0",
        },
    )
    max_diameter_change_um: float = field(
        default=2.0,
        metadata={
            "description": "Max diameter jump allowed between adjacent frames.",
            "units": "um",
            "methods": ["gradient_edges"],
            "constraints": "float >= 0",
        },
    )
    max_center_shift_um: float = field(
        default=2.0,
        metadata={
            "description": "Max centerline shift allowed between adjacent frames.",
            "units": "um",
            "methods": ["gradient_edges"],
            "constraints": "float >= 0",
        },
    )

    def to_dict(self) -> dict[str, Any]:
        # TODO(ticket_014): add stable DetectionParams.to_dict() schema contract.
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DiameterDetectionParams":
        # TODO(ticket_014): add stable DetectionParams.from_dict() schema contract.
        return dataclass_from_dict(cls, payload)


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
    loaded_shape: tuple[int, int] | None = None
    loaded_dtype: str | None = None
    loaded_min: float | None = None
    loaded_max: float | None = None

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
            loaded_shape=(
                None if obj.loaded_shape is None else tuple(int(v) for v in obj.loaded_shape)
            ),
            loaded_dtype=None if obj.loaded_dtype is None else str(obj.loaded_dtype),
            loaded_min=None if obj.loaded_min is None else float(obj.loaded_min),
            loaded_max=None if obj.loaded_max is None else float(obj.loaded_max),
        )


def _normalize_optional_float(value: Any) -> float | None:
    if value is None:
        return None
    as_float = float(value)
    if np.isnan(as_float):
        return None
    return as_float


def _normalize_float_list(values: list[Any], *, field_name: str) -> list[float]:
    out: list[float] = []
    for idx, value in enumerate(values):
        if value is None:
            raise ValueError(f"{field_name}[{idx}] must be a finite float, got None")
        as_float = float(value)
        if np.isnan(as_float):
            raise ValueError(f"{field_name}[{idx}] must be a finite float, got NaN")
        out.append(as_float)
    return out


def _normalize_optional_float_list(values: list[Any]) -> list[float | None]:
    return [_normalize_optional_float(value) for value in values]


def _normalize_bool_list(values: list[Any], *, field_name: str) -> list[bool]:
    out: list[bool] = []
    for idx, value in enumerate(values):
        if value is None:
            raise ValueError(f"{field_name}[{idx}] must be bool, got None")
        out.append(bool(value))
    return out


@dataclass(frozen=True)
class DiameterAlignedResults:
    """Aligned per-frame diameter outputs for one ROI/channel analysis.

    The schema stores all frame-indexed traces as aligned arrays so each index
    refers to the same analyzed timepoint. `schema_version` version-locks the
    meaning of these fields for persistence. Missing values are represented as
    `None` in serialized payloads (never `np.nan`).

    Args:
        schema_version: Schema version for this payload.
        source: Data source type (`"synthetic"` or `"real"`).
        path: Optional source path.
        roi_id: ROI identifier for real data, else `None`.
        channel_id: Channel identifier for real data, else `None`.
        seconds_per_line: Time spacing used to compute traces.
        um_per_pixel: Spatial scale used to compute traces.
        time_s: Aligned time axis in seconds, or `None` if unknown.
        left_um: Left edge trace in microns.
        right_um: Right edge trace in microns.
        center_um: Center trace in microns.
        diameter_um: Diameter trace in microns.
        diameter_um_filtered: Optional post-filtered diameter trace in microns.
        qc_left_edge_violation: Aligned left-edge QC flags.
        qc_right_edge_violation: Aligned right-edge QC flags.
        qc_center_shift_violation: Aligned center-shift QC flags.
        qc_diameter_change_violation: Aligned diameter-change QC flags.
        qc_any_violation: Optional derived aligned OR of QC flags.
    """

    schema_version: int
    source: Literal["synthetic", "real"]
    path: str | None
    roi_id: int | None
    channel_id: int | None
    seconds_per_line: float
    um_per_pixel: float
    time_s: list[float] | None
    left_um: list[float | None]
    right_um: list[float | None]
    center_um: list[float | None]
    diameter_um: list[float | None]
    diameter_um_filtered: list[float | None] | None
    qc_left_edge_violation: list[bool]
    qc_right_edge_violation: list[bool]
    qc_center_shift_violation: list[bool]
    qc_diameter_change_violation: list[bool]
    qc_any_violation: list[bool] | None = None

    def __post_init__(self) -> None:
        if int(self.schema_version) <= 0:
            raise ValueError("schema_version must be >= 1")
        if self.source not in {"synthetic", "real"}:
            raise ValueError("source must be 'synthetic' or 'real'")
        if float(self.seconds_per_line) <= 0.0:
            raise ValueError("seconds_per_line must be > 0")
        if float(self.um_per_pixel) <= 0.0:
            raise ValueError("um_per_pixel must be > 0")

        normalized_time = (
            None
            if self.time_s is None
            else _normalize_float_list(list(self.time_s), field_name="time_s")
        )
        left_um = _normalize_optional_float_list(list(self.left_um))
        right_um = _normalize_optional_float_list(list(self.right_um))
        center_um = _normalize_optional_float_list(list(self.center_um))
        diameter_um = _normalize_optional_float_list(list(self.diameter_um))
        diameter_um_filtered = (
            None
            if self.diameter_um_filtered is None
            else _normalize_optional_float_list(list(self.diameter_um_filtered))
        )
        qc_left = _normalize_bool_list(
            list(self.qc_left_edge_violation), field_name="qc_left_edge_violation"
        )
        qc_right = _normalize_bool_list(
            list(self.qc_right_edge_violation), field_name="qc_right_edge_violation"
        )
        qc_center = _normalize_bool_list(
            list(self.qc_center_shift_violation), field_name="qc_center_shift_violation"
        )
        qc_diam = _normalize_bool_list(
            list(self.qc_diameter_change_violation), field_name="qc_diameter_change_violation"
        )
        qc_any = (
            None
            if self.qc_any_violation is None
            else _normalize_bool_list(list(self.qc_any_violation), field_name="qc_any_violation")
        )

        n_frames = len(diameter_um)
        candidates = [
            ("left_um", len(left_um)),
            ("right_um", len(right_um)),
            ("center_um", len(center_um)),
            ("qc_left_edge_violation", len(qc_left)),
            ("qc_right_edge_violation", len(qc_right)),
            ("qc_center_shift_violation", len(qc_center)),
            ("qc_diameter_change_violation", len(qc_diam)),
        ]
        if normalized_time is not None:
            candidates.append(("time_s", len(normalized_time)))
        if diameter_um_filtered is not None:
            candidates.append(("diameter_um_filtered", len(diameter_um_filtered)))
        if qc_any is not None:
            candidates.append(("qc_any_violation", len(qc_any)))
        for name, length in candidates:
            if length != n_frames:
                raise ValueError(
                    f"Aligned array '{name}' length={length} does not match diameter_um length={n_frames}"
                )

        if qc_any is None:
            qc_any = [a or b or c or d for a, b, c, d in zip(qc_left, qc_right, qc_center, qc_diam)]

        object.__setattr__(self, "schema_version", int(self.schema_version))
        object.__setattr__(self, "path", None if self.path is None else str(self.path))
        object.__setattr__(self, "roi_id", None if self.roi_id is None else int(self.roi_id))
        object.__setattr__(self, "channel_id", None if self.channel_id is None else int(self.channel_id))
        object.__setattr__(self, "seconds_per_line", float(self.seconds_per_line))
        object.__setattr__(self, "um_per_pixel", float(self.um_per_pixel))
        object.__setattr__(self, "time_s", normalized_time)
        object.__setattr__(self, "left_um", left_um)
        object.__setattr__(self, "right_um", right_um)
        object.__setattr__(self, "center_um", center_um)
        object.__setattr__(self, "diameter_um", diameter_um)
        object.__setattr__(self, "diameter_um_filtered", diameter_um_filtered)
        object.__setattr__(self, "qc_left_edge_violation", qc_left)
        object.__setattr__(self, "qc_right_edge_violation", qc_right)
        object.__setattr__(self, "qc_center_shift_violation", qc_center)
        object.__setattr__(self, "qc_diameter_change_violation", qc_diam)
        object.__setattr__(self, "qc_any_violation", qc_any)

    def to_dict(self) -> dict[str, Any]:
        """Serialize aligned results to a JSON-safe dictionary."""
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DiameterAlignedResults":
        """Deserialize aligned results from dictionary payload."""
        return dataclass_from_dict(cls, payload)

    @classmethod
    def from_frame_results(
        cls,
        results: list["DiameterResult"],
        *,
        seconds_per_line: float,
        um_per_pixel: float,
        source: Literal["synthetic", "real"],
        path: str | None = None,
        roi_id: int | None = None,
        channel_id: int | None = None,
    ) -> "DiameterAlignedResults":
        """Build aligned arrays from per-frame `DiameterResult` objects.

        Args:
            results: Per-frame analysis outputs sorted by center row.
            seconds_per_line: Time spacing used for analysis.
            um_per_pixel: Spatial conversion used for analysis.
            source: Input source category (`"synthetic"` or `"real"`).
            path: Optional source path.
            roi_id: Optional ROI id.
            channel_id: Optional channel id.
        """
        um = float(um_per_pixel)
        time_s = [float(r.time_s) for r in results]
        left_um = [_normalize_optional_float(float(r.left_edge_px) * um) for r in results]
        right_um = [_normalize_optional_float(float(r.right_edge_px) * um) for r in results]
        center_um = []
        for left, right in zip(left_um, right_um):
            if left is None or right is None:
                center_um.append(None)
            else:
                center_um.append(0.5 * (left + right))
        diameter_um = [_normalize_optional_float(float(r.diameter_px) * um) for r in results]
        diameter_um_filtered = [
            _normalize_optional_float(float(r.diameter_px_filt) * um) for r in results
        ]

        edge_flags = [bool(r.qc_edge_violation) for r in results]
        return cls(
            schema_version=ALIGNED_RESULTS_SCHEMA_VERSION,
            source=source,
            path=path,
            roi_id=roi_id,
            channel_id=channel_id,
            seconds_per_line=seconds_per_line,
            um_per_pixel=um_per_pixel,
            time_s=time_s,
            left_um=left_um,
            right_um=right_um,
            center_um=center_um,
            diameter_um=diameter_um,
            diameter_um_filtered=diameter_um_filtered,
            qc_left_edge_violation=edge_flags,
            qc_right_edge_violation=edge_flags,
            qc_center_shift_violation=[bool(r.qc_center_violation) for r in results],
            qc_diameter_change_violation=[bool(r.qc_diameter_violation) for r in results],
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
    qc_edge_violation: bool = False
    qc_diameter_violation: bool = False
    qc_center_violation: bool = False

    ROW_FIELDS: ClassVar[tuple[str, ...]] = (
        "center_row",
        "time_s",
        "left_edge_px",
        "right_edge_px",
        "diameter_px",
        "peak",
        "baseline",
        "edge_strength_left",
        "edge_strength_right",
        "diameter_px_filt",
        "diameter_was_filtered",
        "qc_score",
        "qc_flags",
        "qc_edge_violation",
        "qc_diameter_violation",
        "qc_center_violation",
    )

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DiameterResult":
        return dataclass_from_dict(cls, payload)

    def to_row(self, *, roi_id: int, schema_version: int, um_per_pixel: float) -> dict[str, Any]:
        base = self.to_dict()
        return {
            "schema_version": int(schema_version),
            "roi_id": int(roi_id),
            "center_row": int(base["center_row"]),
            "time_s": float(base["time_s"]),
            "left_edge_px": float(base["left_edge_px"]),
            "right_edge_px": float(base["right_edge_px"]),
            "diameter_px": float(base["diameter_px"]),
            "diameter_um": float(base["diameter_px"]) * um_per_pixel,
            "peak": float(base["peak"]),
            "baseline": float(base["baseline"]),
            "edge_strength_left": float(base["edge_strength_left"]),
            "edge_strength_right": float(base["edge_strength_right"]),
            "diameter_px_filt": float(base["diameter_px_filt"]),
            "diameter_um_filt": float(base["diameter_px_filt"]) * um_per_pixel,
            "diameter_was_filtered": int(bool(base["diameter_was_filtered"])),
            "qc_score": float(base["qc_score"]),
            "qc_flags": "|".join(str(v) for v in base["qc_flags"]),
            "qc_edge_violation": int(bool(base["qc_edge_violation"])),
            "qc_diameter_violation": int(bool(base["qc_diameter_violation"])),
            "qc_center_violation": int(bool(base["qc_center_violation"])),
        }

    @classmethod
    def from_row(cls, row: dict[str, str]) -> "DiameterResult":
        qc_flags = row.get("qc_flags", "")
        payload = {
            "center_row": int(row["center_row"]),
            "time_s": float(row["time_s"]),
            "left_edge_px": float(row["left_edge_px"]),
            "right_edge_px": float(row["right_edge_px"]),
            "diameter_px": float(row["diameter_px"]),
            "peak": float(row["peak"]),
            "baseline": float(row["baseline"]),
            "edge_strength_left": float(row.get("edge_strength_left", "nan")),
            "edge_strength_right": float(row.get("edge_strength_right", "nan")),
            "diameter_px_filt": float(row.get("diameter_px_filt", row["diameter_px"])),
            "diameter_was_filtered": bool(int(row.get("diameter_was_filtered", "0"))),
            "qc_score": float(row["qc_score"]),
            "qc_flags": [f for f in qc_flags.split("|") if f],
            "qc_edge_violation": bool(int(row.get("qc_edge_violation", "0"))),
            "qc_diameter_violation": bool(int(row.get("qc_diameter_violation", "0"))),
            "qc_center_violation": bool(int(row.get("qc_center_violation", "0"))),
        }
        missing = [field for field in cls.ROW_FIELDS if field not in payload]
        if missing:
            raise ValueError(f"Missing row fields: {missing}")
        return cls.from_dict(payload)


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
        self.last_motion_qc: dict[str, np.ndarray] | None = None

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

        t0, t1, x0, x1 = self._resolve_roi(None)
        centers = list(range(t0, t1, cfg.stride))

        if backend == "serial":
            results = [self._analyze_center(i, cfg, t0, t1, x0, x1) for i in centers]
        elif backend == "threads":
            results = self._analyze_threads(centers, cfg, t0, t1, x0, x1)
        else:
            raise ValueError("backend must be 'serial' or 'threads'")

        results.sort(key=lambda r: r.center_row)
        if cfg.diameter_method == DiameterMethod.GRADIENT_EDGES and (
            cfg.max_edge_shift_um_on or cfg.max_diameter_change_um_on or cfg.max_center_shift_um_on
        ):
            self._apply_motion_constraints(results=results, params=cfg)
        self.last_motion_qc = self.motion_qc_arrays(results)
        if pf_cfg.enabled:
            self._apply_post_filter(results=results, params=pf_cfg)
        return results

    def analyze_aligned(
        self,
        params: Optional[DiameterDetectionParams] = None,
        *,
        backend: str = "serial",
        post_filter_params: Optional[PostFilterParams] = None,
        source: Literal["synthetic", "real"] = "synthetic",
        path: str | None = None,
        roi_id: int | None = None,
        channel_id: int | None = None,
    ) -> DiameterAlignedResults:
        """Run diameter analysis and return canonical aligned-array results."""
        frame_results = self.analyze(
            params=params,
            backend=backend,
            post_filter_params=post_filter_params,
        )
        return DiameterAlignedResults.from_frame_results(
            frame_results,
            seconds_per_line=self.seconds_per_line,
            um_per_pixel=self.um_per_pixel,
            source=source,
            path=path,
            roi_id=roi_id,
            channel_id=channel_id,
        )

    @staticmethod
    def motion_qc_arrays(results: list[DiameterResult]) -> dict[str, np.ndarray]:
        return {
            "qc_edge_violation": np.asarray([bool(r.qc_edge_violation) for r in results], dtype=bool),
            "qc_diameter_violation": np.asarray(
                [bool(r.qc_diameter_violation) for r in results], dtype=bool
            ),
            "qc_center_violation": np.asarray(
                [bool(r.qc_center_violation) for r in results], dtype=bool
            ),
        }

    def _apply_motion_constraints(
        self,
        *,
        results: list[DiameterResult],
        params: DiameterDetectionParams,
    ) -> None:
        """Apply frame-to-frame QC gates for `gradient_edges` outputs.

        Reads motion-constraint fields and per-constraint toggles from
        `DiameterDetectionParams`. Each gate is applied only if its `_on` toggle
        is enabled and the corresponding threshold is valid.
        """
        if len(results) < 2:
            return

        um_per_px = float(self.um_per_pixel)
        edge_thr_px = float(params.max_edge_shift_um) / um_per_px
        diam_thr_px = float(params.max_diameter_change_um) / um_per_px
        center_thr_px = float(params.max_center_shift_um) / um_per_px

        for i in range(1, len(results)):
            prev = results[i - 1]
            cur = results[i]
            edge_violation = False
            diameter_violation = False
            center_violation = False

            prev_left = float(prev.left_edge_px)
            prev_right = float(prev.right_edge_px)
            cur_left = float(cur.left_edge_px)
            cur_right = float(cur.right_edge_px)

            if params.max_edge_shift_um_on and np.isfinite(cur_left) and np.isfinite(prev_left):
                if abs(cur_left - prev_left) > edge_thr_px:
                    cur_left = math.nan
                    edge_violation = True

            if params.max_edge_shift_um_on and np.isfinite(cur_right) and np.isfinite(prev_right):
                if abs(cur_right - prev_right) > edge_thr_px:
                    cur_right = math.nan
                    edge_violation = True

            prev_d = prev_right - prev_left if np.isfinite(prev_left) and np.isfinite(prev_right) else math.nan
            cur_d = cur_right - cur_left if np.isfinite(cur_left) and np.isfinite(cur_right) else math.nan
            if params.max_diameter_change_um_on and np.isfinite(cur_d) and np.isfinite(prev_d):
                if abs(cur_d - prev_d) > diam_thr_px:
                    cur_left = math.nan
                    cur_right = math.nan
                    diameter_violation = True

            prev_c = (
                0.5 * (prev_left + prev_right)
                if np.isfinite(prev_left) and np.isfinite(prev_right)
                else math.nan
            )
            cur_c = (
                0.5 * (cur_left + cur_right)
                if np.isfinite(cur_left) and np.isfinite(cur_right)
                else math.nan
            )
            if params.max_center_shift_um_on and np.isfinite(cur_c) and np.isfinite(prev_c):
                if abs(cur_c - prev_c) > center_thr_px:
                    cur_left = math.nan
                    cur_right = math.nan
                    center_violation = True

            cur.left_edge_px = float(cur_left)
            cur.right_edge_px = float(cur_right)
            cur.diameter_px = (
                float(cur_right - cur_left)
                if np.isfinite(cur_left) and np.isfinite(cur_right)
                else math.nan
            )
            cur.diameter_px_filt = float(cur.diameter_px)
            cur.qc_edge_violation = edge_violation
            cur.qc_diameter_violation = diameter_violation
            cur.qc_center_violation = center_violation

            if edge_violation and "motion_edge_violation" not in cur.qc_flags:
                cur.qc_flags.append("motion_edge_violation")
            if diameter_violation and "motion_diameter_violation" not in cur.qc_flags:
                cur.qc_flags.append("motion_diameter_violation")
            if center_violation and "motion_center_violation" not in cur.qc_flags:
                cur.qc_flags.append("motion_center_violation")
            cur.qc_flags = sorted(set(cur.qc_flags))

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
        """Analyze one center row using the selected detection method.

        Method-specific parameter usage:
        - Always reads: `window_rows_odd`, `binning_method`, `polarity`,
          `diameter_method`.
        - `threshold_width` path reads: `threshold_mode`, `threshold_value`.
        - `gradient_edges` path reads: `gradient_sigma`, `gradient_kernel`,
          `gradient_min_edge_strength`.
        """
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
        """Estimate vessel width using threshold crossings.

        Consumes `DiameterDetectionParams.threshold_mode` and
        `DiameterDetectionParams.threshold_value`. Gradient and motion parameters
        are ignored in this method.
        """
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
        """Estimate vessel edges using profile derivatives.

        Consumes `DiameterDetectionParams.gradient_sigma`,
        `DiameterDetectionParams.gradient_kernel`, and
        `DiameterDetectionParams.gradient_min_edge_strength`.
        Threshold parameters are ignored in this method.
        """
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
        if params.max_edge_shift_um < 0:
            raise ValueError("max_edge_shift_um must be >= 0")
        if params.max_diameter_change_um < 0:
            raise ValueError("max_diameter_change_um must be >= 0")
        if params.max_center_shift_um < 0:
            raise ValueError("max_center_shift_um must be >= 0")
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
            "qc_edge_violation",
            "qc_diameter_violation",
            "qc_center_violation",
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
