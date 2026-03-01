from __future__ import annotations

from dataclasses import MISSING, dataclass, field, fields, is_dataclass, replace
from datetime import datetime, timezone
from enum import Enum
import json
from pathlib import Path
from types import UnionType
from typing import Any, Literal, Mapping, Optional, Sequence, TypeVar, Union, get_args, get_origin, get_type_hints

import numpy as np
import pandas as pd

from heart_rate_analysis import (
    HRStatus,
    HeartRateEstimate,
    estimate_heart_rate_global,
    estimate_heart_rate_segment_series,
)

AGREE_TOL_BPM_DEFAULT = 30.0
RESULTS_JSON_SCHEMA_VERSION = 1
T = TypeVar("T")


def dataclass_to_jsonable(obj: Any) -> Any:
    """Convert dataclasses and nested values to JSON-compatible primitives.

    Args:
        obj: Input object to convert.

    Returns:
        Any: JSON-compatible object composed of dict/list/primitive values.

    Raises:
        TypeError: If an unsupported value type is encountered.
    """
    if is_dataclass(obj):
        out: dict[str, Any] = {}
        for f in fields(obj):
            out[f.name] = dataclass_to_jsonable(getattr(obj, f.name))
        return out
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, dict):
        out_map: dict[str, Any] = {}
        for k, v in obj.items():
            if not isinstance(k, (str, int, float, bool)):
                raise TypeError(f"Unsupported mapping key type {type(k).__name__} for JSON serialization.")
            out_map[str(k)] = dataclass_to_jsonable(v)
        return out_map
    if isinstance(obj, (list, tuple)):
        return [dataclass_to_jsonable(x) for x in obj]
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    raise TypeError(f"Unsupported type for JSON serialization: {type(obj).__name__}")


def dataclass_from_dict(cls: type[T], payload: Mapping[str, Any]) -> T:
    """Deserialize a dataclass from a mapping with forward/backward compatibility.

    Unknown keys are ignored. Missing keys are left to dataclass defaults.

    Args:
        cls: Target dataclass type.
        payload: Serialized mapping to parse.

    Returns:
        T: Deserialized dataclass instance.

    Raises:
        TypeError: If ``cls`` is not a dataclass type or payload is invalid.
    """
    if not isinstance(payload, Mapping):
        raise TypeError(f"Expected Mapping for {cls.__name__} deserialization.")
    if not is_dataclass(cls):
        raise TypeError(f"{cls!r} is not a dataclass type.")

    type_hints = get_type_hints(cls)
    kwargs: dict[str, Any] = {}
    for f in fields(cls):
        if f.name not in payload:
            continue
        hinted_type = type_hints.get(f.name, f.type)
        kwargs[f.name] = _convert_value_for_type(payload[f.name], hinted_type)

    for f in fields(cls):
        if f.name in kwargs:
            continue
        has_default = f.default is not MISSING or f.default_factory is not MISSING  # type: ignore[attr-defined]
        if not has_default:
            raise TypeError(f"Missing required field {f.name!r} for {cls.__name__}.")

    return cls(**kwargs)


def _convert_value_for_type(value: Any, annotation: Any) -> Any:
    """Convert one value according to an annotated dataclass field type."""
    if value is None:
        return None

    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin in (Union, UnionType):
        non_none = [a for a in args if a is not type(None)]
        for sub_t in non_none:
            try:
                return _convert_value_for_type(value, sub_t)
            except Exception:
                continue
        return value

    if origin is Literal:
        return value

    if origin in (list, Sequence):
        elem_t = args[0] if args else Any
        if not isinstance(value, list):
            return value
        return [_convert_value_for_type(v, elem_t) for v in value]

    if origin is tuple:
        if not isinstance(value, list):
            return value
        if len(args) == 2 and args[1] is Ellipsis:
            return tuple(_convert_value_for_type(v, args[0]) for v in value)
        if args and len(args) == len(value):
            return tuple(_convert_value_for_type(v, t) for v, t in zip(value, args))
        return tuple(value)

    if origin in (dict, Mapping):
        key_t = args[0] if len(args) > 0 else Any
        val_t = args[1] if len(args) > 1 else Any
        if not isinstance(value, Mapping):
            return value
        out: dict[Any, Any] = {}
        for k, v in value.items():
            out[_convert_scalar(k, key_t)] = _convert_value_for_type(v, val_t)
        return out

    if isinstance(annotation, type):
        if issubclass(annotation, Enum):
            if isinstance(value, annotation):
                return value
            return annotation(value)
        if issubclass(annotation, Path):
            return Path(value)
        if is_dataclass(annotation):
            return dataclass_from_dict(annotation, value)

    return value


def _convert_scalar(value: Any, annotation: Any) -> Any:
    """Convert scalar mapping keys when a concrete scalar type is known."""
    if isinstance(annotation, type):
        if issubclass(annotation, int):
            return int(value)
        if issubclass(annotation, float):
            return float(value)
        if issubclass(annotation, str):
            return str(value)
    return value


@dataclass(frozen=True)
class HRAnalysisConfig:
    """Configuration used for per-ROI heart-rate analysis.

    Args:
        bpm_band: Lower/upper heart-rate bounds in bpm.
        use_abs: Whether to analyze absolute velocity.
        outlier_k_mad: MAD clip factor used during preprocessing.
        lomb_n_freq: Number of frequencies for Lomb-Scargle grid.
        interp_max_gap_sec: Maximum NaN gap (seconds) to interpolate for Welch.
        bandpass_order: Butterworth band-pass order for Welch path.
        nperseg_sec: Welch segment length in seconds.
        edge_margin_hz: Optional edge margin override in Hz for edge-flagging.
        peak_half_width_hz: Half-width around peak used for band concentration.
        do_segments: Whether to compute segment/windowed HR metrics.
        seg_win_sec: Segment window length in seconds.
        seg_step_sec: Segment window step in seconds.
        seg_min_valid_frac: Minimum finite sample fraction per segment.
    """

    bpm_band: tuple[float, float] = (240.0, 600.0)
    use_abs: bool = True
    outlier_k_mad: float = 4.0
    lomb_n_freq: int = 512
    interp_max_gap_sec: float = 0.05
    bandpass_order: int = 3
    nperseg_sec: float = 2.0
    edge_margin_hz: Optional[float] = None
    peak_half_width_hz: float = 0.5
    do_segments: bool = False
    seg_win_sec: float = 6.0
    seg_step_sec: float = 1.0
    seg_min_valid_frac: float = 0.5

    @classmethod
    def from_any(cls, cfg: Any = None) -> "HRAnalysisConfig":
        """Build a normalized config from None/dict/config-like object.

        Args:
            cfg: `None`, a dict, or an object exposing matching attribute names.

        Returns:
            HRAnalysisConfig: Normalized immutable config.
        """
        if cfg is None:
            return cls()
        if isinstance(cfg, HRAnalysisConfig):
            return cfg

        keys = (
            "bpm_band",
            "use_abs",
            "outlier_k_mad",
            "lomb_n_freq",
            "interp_max_gap_sec",
            "bandpass_order",
            "nperseg_sec",
            "edge_margin_hz",
            "peak_half_width_hz",
            "do_segments",
            "seg_win_sec",
            "seg_step_sec",
            "seg_min_valid_frac",
        )

        payload: dict[str, Any] = {}
        if isinstance(cfg, dict):
            for k in keys:
                if k in cfg:
                    payload[k] = cfg[k]
        else:
            for k in keys:
                if hasattr(cfg, k):
                    payload[k] = getattr(cfg, k)

        return cls(**payload)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable configuration dictionary.

        Returns:
            dict[str, Any]: Plain-JSON config payload.
        """
        return dataclass_to_jsonable(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "HRAnalysisConfig":
        """Create config from a serialized dictionary.

        Args:
            payload: Serialized config mapping produced by ``to_dict``.

        Returns:
            HRAnalysisConfig: Parsed config object.
        """
        return dataclass_from_dict(cls, payload)


@dataclass(frozen=True)
class HeartRateResults:
    """Result payload for one method on one ROI.

    Args:
        method: Method label (`"lombscargle"` or `"welch"`).
        bpm: Estimated heart-rate in bpm, or None when unavailable.
        f_hz: Estimated frequency in Hz, or None when unavailable.
        snr: Confidence metric, or None when unavailable.
        t_start: Start time of analyzed interval, or None.
        t_end: End time of analyzed interval, or None.
        n_samples: Number of original samples in interval, or None.
        n_valid: Number of valid samples used, or None.
        status: Structured method status code.
        status_note: Human-readable method status note.
        reason: Optional failure reason when estimate is unavailable.
        edge_flag: True if detected peak is near band edge.
        edge_hz_distance: Distance from closest band edge in Hz.
        band_concentration: Fraction of band power concentrated near detected peak.
        debug: Optional debug payload from core estimator.
    """

    method: str
    bpm: Optional[float]
    f_hz: Optional[float]
    snr: Optional[float]
    t_start: Optional[float]
    t_end: Optional[float]
    n_samples: Optional[int]
    n_valid: Optional[int]
    status: HRStatus = HRStatus.OK
    status_note: str = ""
    reason: Optional[str] = None
    edge_flag: Optional[bool] = None
    edge_hz_distance: Optional[float] = None
    band_concentration: Optional[float] = None
    debug: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_estimate(
        cls,
        method: str,
        estimate: Optional[HeartRateEstimate],
        debug: Optional[dict[str, Any]] = None,
    ) -> "HeartRateResults":
        """Create `HeartRateResults` from core estimator outputs.

        Args:
            method: Method name used for the estimate.
            estimate: Optional `HeartRateEstimate` returned by core analysis.
            debug: Optional debug dictionary returned by core analysis.

        Returns:
            HeartRateResults: Normalized result payload.
        """
        dbg = debug or {}
        status = _coerce_hr_status(dbg.get("status"), default=HRStatus.OK if estimate is not None else HRStatus.OTHER_ERROR)
        status_note = str(dbg.get("note", ""))
        if estimate is None:
            return cls(
                method=method,
                bpm=None,
                f_hz=None,
                snr=None,
                t_start=None,
                t_end=None,
                n_samples=None,
                n_valid=None,
                status=status,
                status_note=status_note,
                reason=str(dbg.get("reason", "not_available")),
                edge_flag=None,
                edge_hz_distance=None,
                band_concentration=None,
                debug=dbg,
            )

        return cls(
            method=method,
            bpm=float(estimate.bpm),
            f_hz=float(estimate.f_hz),
            snr=float(estimate.snr),
            t_start=float(estimate.t_start),
            t_end=float(estimate.t_end),
            n_samples=int(estimate.n_samples),
            n_valid=int(estimate.n_valid),
            status=status,
            status_note=status_note,
            reason=None,
            edge_flag=bool(estimate.edge_flag),
            edge_hz_distance=estimate.edge_hz_distance,
            band_concentration=estimate.band_concentration,
            debug=dbg,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary for this method result.

        Returns:
            dict[str, Any]: Serializable method-level output.
        """
        payload = replace(self, debug={})
        return dataclass_to_jsonable(payload)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "HeartRateResults":
        """Create method-level results from a serialized dictionary.

        Args:
            payload: Serialized method result dictionary.

        Returns:
            HeartRateResults: Parsed method payload.
        """
        out = dataclass_from_dict(cls, payload)
        return replace(out, debug={})


@dataclass(frozen=True)
class HeartRatePerRoiResults:
    """Container for all method outputs and QC for one ROI.

    Args:
        roi_id: ROI identifier analyzed.
        lomb: Lomb-Scargle result payload.
        welch: Welch result payload.
        agreement: Optional agreement metrics when both methods are available.
        n_total: Number of rows for this ROI.
        n_valid: Number of finite velocity/time rows for this ROI.
        valid_fraction: Fraction of valid rows.
        time_range: Optional `(t_min, t_max)` for this ROI.
        analysis_cfg: Exact analysis config used for this ROI run.
        segments: Optional windowed segment HR QC payload.
    """

    roi_id: int
    lomb: Optional[HeartRateResults]
    welch: Optional[HeartRateResults]
    agreement: Optional[dict[str, float]]
    n_total: int
    n_valid: int
    valid_fraction: float
    time_range: Optional[tuple[float, float]]
    analysis_cfg: HRAnalysisConfig
    segments: Optional[dict[str, list[float]]] = None

    def to_dict(self, *, compact: bool = False) -> dict[str, Any]:
        """Return JSON-serializable per-ROI summary.

        Args:
            compact: When True, omit raw segment series and include only a small
                segment summary.

        Returns:
            dict[str, Any]: Serializable ROI summary payload.
        """
        out: dict[str, Any] = {
            "roi_id": int(self.roi_id),
            "lomb": None if self.lomb is None else self.lomb.to_dict(),
            "welch": None if self.welch is None else self.welch.to_dict(),
            "agreement": self.agreement,
            "n_total": int(self.n_total),
            "n_valid": int(self.n_valid),
            "valid_fraction": float(self.valid_fraction),
            "time_range": None,
            "analysis_cfg": self.analysis_cfg.to_dict(),
        }
        if self.time_range is not None:
            out["time_range"] = [float(self.time_range[0]), float(self.time_range[1])]
        if compact:
            if self.segments is not None:
                seg_bpm = np.asarray(self.segments.get("bpm", []), dtype=float)
                valid = np.isfinite(seg_bpm)
                q25 = float(np.nanpercentile(seg_bpm, 25)) if np.any(valid) else float("nan")
                q75 = float(np.nanpercentile(seg_bpm, 75)) if np.any(valid) else float("nan")
                out["segments_summary"] = {
                    "method": self.segments.get("method", "unknown"),
                    "n_windows": int(seg_bpm.size),
                    "n_valid_windows": int(np.sum(valid)),
                    "median_bpm": float(np.nanmedian(seg_bpm)) if np.any(valid) else None,
                    "iqr_bpm": float(q75 - q25) if np.any(valid) else None,
                }
            else:
                out["segments_summary"] = None
        else:
            out["segments"] = self.segments
        return out

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "HeartRatePerRoiResults":
        """Create per-ROI result payload from a serialized dictionary.

        Args:
            payload: Serialized per-ROI mapping produced by ``to_dict``.

        Returns:
            HeartRatePerRoiResults: Parsed per-ROI result.
        """
        return dataclass_from_dict(cls, payload)


class HeartRateAnalysis:
    """Per-ROI heart-rate analysis pipeline over a full CSV dataframe.

    The object stores the full CSV (`self.df`) and only analyzes one ROI at a time
    (`run_roi`) or iterates ROI-by-ROI (`run_all_rois`). Analysis is never run
    across mixed `roi_id` values.

    Attributes:
        df: Full dataframe including all ROI rows.
        roi_ids: Sorted integer ROI ids found in the dataframe.
        results_by_roi: Latest per-ROI results keyed by roi_id.
    """

    def __init__(
        self,
        df: pd.DataFrame,
        *,
        time_col: str = "time",
        vel_col: str = "velocity",
        roi_col: str = "roi_id",
        source_path: Optional[Path] = None,
        source: Optional[str] = None,
    ) -> None:
        """Initialize with a full dataframe containing one or more ROI values.

        Args:
            df: Full CSV dataframe containing all rows.
            time_col: Name of time column.
            vel_col: Name of velocity column.
            roi_col: Name of ROI id column. Must exist.
            source_path: Optional CSV source path used for persistence naming.
            source: Optional source identifier (backward-compatible alias).

        Raises:
            ValueError: If required columns are missing or roi_id cannot be integer-coerced.
        """
        if roi_col not in df.columns:
            raise ValueError(f"Required ROI column '{roi_col}' is missing from dataframe.")
        if time_col not in df.columns:
            raise ValueError(f"Required time column '{time_col}' is missing from dataframe.")
        if vel_col not in df.columns:
            raise ValueError(f"Required velocity column '{vel_col}' is missing from dataframe.")

        local_df = df.copy()
        local_df[roi_col] = _coerce_roi_to_int(local_df[roi_col], roi_col=roi_col)

        self.df = local_df
        self.time_col = time_col
        self.vel_col = vel_col
        self.roi_col = roi_col
        if source_path is not None:
            self.source_path: Optional[Path] = Path(source_path)
            self.source = str(self.source_path)
        elif source is not None:
            self.source_path = None
            self.source = source
        else:
            self.source_path = None
            self.source = None
        self.roi_ids: list[int] = sorted(int(x) for x in np.unique(local_df[roi_col].to_numpy(dtype=int)))
        self.results_by_roi: dict[int, HeartRatePerRoiResults] = {}

    @classmethod
    def from_csv(
        cls,
        path: str | Path,
        *,
        time_col: str = "time",
        vel_col: str = "velocity",
        roi_col: str = "roi_id",
        **read_csv_kwargs: Any,
    ) -> "HeartRateAnalysis":
        """Create analysis object from a CSV path.

        Args:
            path: CSV file path.
            time_col: Name of time column.
            vel_col: Name of velocity column.
            roi_col: Name of ROI id column. Must exist.
            **read_csv_kwargs: Additional `pandas.read_csv` kwargs.

        Returns:
            HeartRateAnalysis: Initialized pipeline with full dataframe and roi list.

        Raises:
            ValueError: If ROI/time/velocity columns are missing or roi ids are invalid.
        """
        csv_path = Path(path)
        df = pd.read_csv(csv_path, **read_csv_kwargs)
        return cls(df, time_col=time_col, vel_col=vel_col, roi_col=roi_col, source_path=csv_path)

    def default_results_json_path(self) -> Path:
        """Return the default JSON persistence path for this analysis object.

        Returns:
            Path: ``<csv_stem>_heart_rate.json`` next to the source CSV.

        Raises:
            ValueError: If this analysis object has no associated source path.
        """
        if self.source_path is None:
            raise ValueError("default_results_json_path requires source_path to be set.")
        return self.source_path.with_name(f"{self.source_path.stem}_heart_rate.json")

    def save_results_json(self, path: Optional[Path] = None) -> Path:
        """Persist analyzed per-ROI results and config to a JSON artifact.

        Args:
            path: Optional explicit destination path. When omitted, uses
                ``default_results_json_path()``.

        Returns:
            Path: The written JSON path.
        """
        out_path = Path(path) if path is not None else self.default_results_json_path()
        per_roi_payload: dict[str, Any] = {}
        for roi_id in sorted(self.results_by_roi.keys()):
            roi_result = self.results_by_roi[roi_id]
            per_roi_payload[str(roi_id)] = {
                "cfg": roi_result.analysis_cfg.to_dict(),
                "results": roi_result.to_dict(compact=False),
            }

        payload = {
            "schema_version": int(RESULTS_JSON_SCHEMA_VERSION),
            "source_csv": None if self.source_path is None else str(self.source_path),
            "saved_at_iso": datetime.now(timezone.utc).isoformat(),
            "per_roi": per_roi_payload,
        }
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return out_path

    def load_results_json(self, path: Optional[Path] = None) -> None:
        """Load persisted per-ROI results/config from a JSON artifact.

        Args:
            path: Optional explicit source path. When omitted, uses
                ``default_results_json_path()``.

        Raises:
            ValueError: If schema or required keys are invalid.
        """
        in_path = Path(path) if path is not None else self.default_results_json_path()
        raw = json.loads(in_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("Results JSON root must be an object.")
        if int(raw.get("schema_version", -1)) != int(RESULTS_JSON_SCHEMA_VERSION):
            raise ValueError(f"Unsupported schema_version={raw.get('schema_version')!r}.")
        if "per_roi" not in raw or not isinstance(raw["per_roi"], dict):
            raise ValueError("Results JSON requires object key 'per_roi'.")

        source_csv = raw.get("source_csv")
        if self.source_path is None and source_csv:
            self.source_path = Path(source_csv)
            self.source = str(self.source_path)

        loaded: dict[int, HeartRatePerRoiResults] = {}
        for roi_key, entry in raw["per_roi"].items():
            if not isinstance(entry, dict):
                raise ValueError(f"Invalid per_roi entry for key={roi_key!r}.")
            if "cfg" not in entry or "results" not in entry:
                raise ValueError(f"per_roi[{roi_key!r}] requires keys 'cfg' and 'results'.")
            cfg_obj = HRAnalysisConfig.from_dict(entry["cfg"])
            roi_result = HeartRatePerRoiResults.from_dict(entry["results"])
            rid = int(roi_key)
            if roi_result.roi_id != rid:
                raise ValueError(f"ROI key mismatch: key={rid} payload={roi_result.roi_id}.")
            if rid not in self.roi_ids:
                raise ValueError(f"Loaded roi_id={rid} not present in dataframe roi_ids={self.roi_ids}.")
            # Persistence schema keeps cfg in two places for compatibility:
            # per_roi[roi]["cfg"] and per_roi[roi]["results"]["analysis_cfg"].
            # Treat the top-level per-roi cfg as the source of truth.
            if roi_result.analysis_cfg != cfg_obj:
                roi_result = replace(roi_result, analysis_cfg=cfg_obj)
            loaded[rid] = roi_result

        self.results_by_roi = loaded

    def run_roi(
        self,
        roi_id: int,
        *,
        cfg: Any = None,
        methods: Optional[Sequence[str]] = None,
    ) -> HeartRatePerRoiResults:
        """Run global HR analysis for exactly one ROI and cache results.

        Args:
            roi_id: ROI id to analyze. Must exist in `self.roi_ids`.
            cfg: Config for this ROI (`HRAnalysisConfig`, dict, or config-like object).
            methods: Optional iterable of methods to run. If omitted, both
                `"lombscargle"` and `"welch"` are executed.

        Returns:
            HeartRatePerRoiResults: Latest per-ROI result payload.

        Raises:
            ValueError: If roi_id is unavailable or method is unsupported.
        """
        roi_id = int(roi_id)
        if roi_id not in self.roi_ids:
            raise ValueError(f"roi_id={roi_id} not found. Available roi_ids={self.roi_ids}")

        cfg_obj = HRAnalysisConfig.from_any(cfg)
        t, v = self.get_time_velocity(roi_id)
        df_roi = self.get_roi_df(roi_id)
        finite = np.isfinite(t) & np.isfinite(v)

        n_total = int(len(df_roi))
        n_valid = int(np.sum(finite))
        valid_fraction = float(n_valid / n_total) if n_total else 0.0

        time_range: Optional[tuple[float, float]] = None
        if n_valid > 0:
            time_range = (float(np.nanmin(t[finite])), float(np.nanmax(t[finite])))

        method_list = ("lombscargle", "welch") if methods is None else tuple(methods)
        method_set = {m.lower() for m in method_list}
        for m in method_set:
            if m not in {"lombscargle", "welch"}:
                raise ValueError(f"Unsupported method={m!r}")

        lomb: Optional[HeartRateResults] = None
        welch: Optional[HeartRateResults] = None

        if "lombscargle" in method_set:
            est, dbg = estimate_heart_rate_global(
                t,
                v,
                bpm_band=cfg_obj.bpm_band,
                use_abs=cfg_obj.use_abs,
                outlier_k_mad=cfg_obj.outlier_k_mad,
                method="lombscargle",
                lomb_n_freq=cfg_obj.lomb_n_freq,
                edge_margin_hz=cfg_obj.edge_margin_hz,
                peak_half_width_hz=cfg_obj.peak_half_width_hz,
            )
            lomb = HeartRateResults.from_estimate("lombscargle", est, dbg)

        if "welch" in method_set:
            est, dbg = estimate_heart_rate_global(
                t,
                v,
                bpm_band=cfg_obj.bpm_band,
                use_abs=cfg_obj.use_abs,
                outlier_k_mad=cfg_obj.outlier_k_mad,
                method="welch",
                lomb_n_freq=cfg_obj.lomb_n_freq,
                interp_max_gap_sec=cfg_obj.interp_max_gap_sec,
                bandpass_order=cfg_obj.bandpass_order,
                nperseg_sec=cfg_obj.nperseg_sec,
                edge_margin_hz=cfg_obj.edge_margin_hz,
                peak_half_width_hz=cfg_obj.peak_half_width_hz,
            )
            welch = HeartRateResults.from_estimate("welch", est, dbg)

        agreement: Optional[dict[str, float]] = None
        if lomb is not None and welch is not None and lomb.bpm is not None and welch.bpm is not None:
            agreement = {
                "delta_bpm": float(welch.bpm - lomb.bpm),
                "delta_hz": float((welch.f_hz or 0.0) - (lomb.f_hz or 0.0)),
                "abs_delta_bpm": float(abs(welch.bpm - lomb.bpm)),
            }

        segments_payload: Optional[dict[str, list[float]]] = None
        if bool(cfg_obj.do_segments):
            seg = estimate_heart_rate_segment_series(
                t,
                v,
                method="welch",
                bpm_band=cfg_obj.bpm_band,
                use_abs=cfg_obj.use_abs,
                outlier_k_mad=cfg_obj.outlier_k_mad,
                lomb_n_freq=cfg_obj.lomb_n_freq,
                interp_max_gap_sec=cfg_obj.interp_max_gap_sec,
                bandpass_order=cfg_obj.bandpass_order,
                nperseg_sec=cfg_obj.nperseg_sec,
                edge_margin_hz=cfg_obj.edge_margin_hz,
                peak_half_width_hz=cfg_obj.peak_half_width_hz,
                seg_win_sec=cfg_obj.seg_win_sec,
                seg_step_sec=cfg_obj.seg_step_sec,
                seg_min_valid_frac=cfg_obj.seg_min_valid_frac,
            )
            segments_payload = {
                "t_center": seg["t_center"].tolist(),
                "bpm": seg["bpm"].tolist(),
                "snr": seg["snr"].tolist(),
                "valid_frac": seg["valid_frac"].tolist(),
                "edge_flag": seg["edge_flag"].tolist(),
                "band_concentration": seg["band_concentration"].tolist(),
                "method": "welch",
            }

        per_roi = HeartRatePerRoiResults(
            roi_id=roi_id,
            lomb=lomb,
            welch=welch,
            agreement=agreement,
            n_total=n_total,
            n_valid=n_valid,
            valid_fraction=valid_fraction,
            time_range=time_range,
            analysis_cfg=cfg_obj,
            segments=segments_payload,
        )
        self.results_by_roi[roi_id] = per_roi
        return per_roi

    def get_roi_df(self, roi_id: int) -> pd.DataFrame:
        """Return rows for a single ROI id.

        Args:
            roi_id: ROI identifier that must exist in this analysis object.

        Returns:
            pd.DataFrame: Dataframe containing only rows for the requested ROI.

        Raises:
            KeyError: If ``roi_id`` is not available.
            ValueError: If filtering unexpectedly yields no rows.
        """
        rid = int(roi_id)
        if rid not in self.roi_ids:
            raise KeyError(f"roi_id={rid} not found. Available roi_ids={self.roi_ids}")
        out = self.df[self.df[self.roi_col] == rid]
        if out.empty:
            raise ValueError(f"No rows found for roi_id={rid}.")
        return out

    def get_time_velocity(self, roi_id: int) -> tuple[np.ndarray, np.ndarray]:
        """Return time/velocity arrays for one ROI, sorted by time.

        Args:
            roi_id: ROI identifier that must exist in this analysis object.

        Returns:
            tuple[np.ndarray, np.ndarray]: ``(time_s, velocity)`` arrays.

        Raises:
            KeyError: If ``roi_id`` is not available.
            ValueError: If filtered ROI contains no rows.
        """
        df_roi = self.get_roi_df(roi_id)
        df_sorted = df_roi.sort_values(by=self.time_col, kind="mergesort")
        t = df_sorted[self.time_col].to_numpy(dtype=float)
        v = df_sorted[self.vel_col].to_numpy(dtype=float)
        if t.size == 0:
            raise ValueError(f"No samples for roi_id={roi_id}.")
        return t, v

    def get_roi_results(self, roi_id: int) -> HeartRatePerRoiResults:
        """Return cached per-ROI results.

        Args:
            roi_id: ROI identifier that must have been analyzed.

        Returns:
            HeartRatePerRoiResults: Cached result object for this ROI.

        Raises:
            KeyError: If ROI has not been analyzed yet.
        """
        rid = int(roi_id)
        if rid not in self.results_by_roi:
            raise KeyError(f"No cached results for roi_id={rid}. Run run_roi() first.")
        return self.results_by_roi[rid]

    def get_roi_summary(
        self,
        roi_id: int,
        *,
        minimal: bool | Literal["mini"] = True,
        agree_tol_bpm: float = AGREE_TOL_BPM_DEFAULT,
    ) -> dict[str, Any]:
        """Return one ROI summary with optional minimal stable batch schema.

        Args:
            roi_id: ROI identifier that must have cached results.
            minimal: ``True`` for compact stable schema, ``"mini"`` for batch
                table schema with only essential keys, or ``False`` for full
                per-ROI detail payload.
            agree_tol_bpm: Agreement threshold (bpm) for ``agree_ok``.

        Returns:
            dict[str, Any]: ROI summary dictionary.

        Raises:
            KeyError: If ROI has no cached results.
        """
        result = self.get_roi_results(roi_id)
        file_label = self.source if self.source is not None else "<arrays>"
        return build_roi_summary_from_result(
            result,
            file_label=file_label,
            minimal=minimal,
            agree_tol_bpm=agree_tol_bpm,
        )

    def run_all_rois(
        self,
        *,
        cfg_by_roi: Optional[dict[int, Any]] = None,
        cfg: Any = None,
        methods: Sequence[str] = ("lombscargle", "welch"),
    ) -> dict[int, HeartRatePerRoiResults]:
        """Run analysis ROI-by-ROI across all available ROI ids.

        Config precedence per ROI:
        1) `cfg_by_roi[roi_id]` when present.
        2) shared `cfg` when provided.
        3) defaults.

        Args:
            cfg_by_roi: Optional per-ROI config mapping.
            cfg: Optional fallback config for all ROIs.
            methods: Methods to pass through to `run_roi`.

        Returns:
            dict[int, HeartRatePerRoiResults]: Mapping of roi_id to latest results.
        """
        local_cfg_by_roi = cfg_by_roi or {}
        out: dict[int, HeartRatePerRoiResults] = {}
        for roi_id in self.roi_ids:
            selected_cfg = local_cfg_by_roi.get(roi_id, cfg)
            out[roi_id] = self.run_roi(roi_id, cfg=selected_cfg, methods=methods)
        return out

    def getSummaryDict(self, *, compact: bool = True) -> dict[str, Any]:
        """Return JSON-serializable per-ROI and aggregate summary.

        When ``compact=True`` (default), per-ROI output includes global method
        results, agreement, and ``analysis_cfg``, but omits raw segment series
        arrays in favor of a small segment summary. When ``compact=False``,
        segment series arrays are included in full.

        Returns:
            dict[str, Any]: Summary with per-ROI results, per-ROI configs, and
            aggregate rollups over analyzed ROI ids.
        """
        per_roi: dict[str, Any] = {}
        lomb_bpm_by_roi: dict[str, Optional[float]] = {}
        welch_bpm_by_roi: dict[str, Optional[float]] = {}

        for roi_id in sorted(self.results_by_roi.keys()):
            result = self.results_by_roi[roi_id]

            roi_key = str(roi_id)
            payload = result.to_dict(compact=compact)
            per_roi[roi_key] = payload

            lomb_bpm_by_roi[roi_key] = None
            if result.lomb is not None and result.lomb.bpm is not None:
                lomb_bpm_by_roi[roi_key] = float(result.lomb.bpm)

            welch_bpm_by_roi[roi_key] = None
            if result.welch is not None and result.welch.bpm is not None:
                welch_bpm_by_roi[roi_key] = float(result.welch.bpm)

        return {
            "source": self.source,
            "roi_ids_available": [int(x) for x in self.roi_ids],
            "counts": {
                "n_roi_total": int(len(self.roi_ids)),
                "n_roi_analyzed": int(len(self.results_by_roi)),
            },
            "per_roi": per_roi,
            "aggregate": {
                "roi_ids_analyzed": [int(x) for x in sorted(self.results_by_roi.keys())],
                "lomb_bpm_by_roi": lomb_bpm_by_roi,
                "welch_bpm_by_roi": welch_bpm_by_roi,
            },
        }


def run_hr_analysis(
    *,
    csv_path: str | Path | None = None,
    time_s: Optional[Sequence[float]] = None,
    velocity: Optional[Sequence[float]] = None,
    roi_id: Optional[int] = None,
    run_all: bool = False,
    cfg: Any = None,
    cfg_by_roi: Optional[dict[int, Any]] = None,
    methods: Optional[Sequence[str]] = None,
    time_col: str = "time",
    vel_col: str = "velocity",
    roi_col: str = "roi_id",
) -> HeartRateAnalysis:
    """Convenience wrapper to run ROI-aware HR analysis from CSV or arrays.

    Args:
        csv_path: Optional CSV path. When provided, full CSV is loaded.
        time_s: Optional time samples for array-based input.
        velocity: Optional velocity samples for array-based input.
        roi_id: Required for array-based input and required for CSV mode when ``run_all=False``.
        run_all: If True, run all ROI ids available in the analysis object.
        cfg: Optional shared config for `run_roi`/`run_all_rois`.
        cfg_by_roi: Optional per-ROI config mapping for `run_all_rois`.
        methods: Optional method subset to run. When ``None``, both methods run.
        time_col: Time column name (CSV mode).
        vel_col: Velocity column name (CSV mode).
        roi_col: ROI column name (CSV mode).

    Returns:
        HeartRateAnalysis: Analysis object populated with cached results.

    Raises:
        ValueError: If required inputs are missing or ROI semantics are violated.
    """
    if csv_path is not None:
        analysis = HeartRateAnalysis.from_csv(
            csv_path,
            time_col=time_col,
            vel_col=vel_col,
            roi_col=roi_col,
        )
    else:
        if time_s is None or velocity is None:
            raise ValueError("Provide either csv_path or both time_s and velocity.")
        if roi_id is None:
            raise ValueError("Array input requires roi_id to avoid mixed-ROI analysis.")

        t = np.asarray(time_s, dtype=float)
        v = np.asarray(velocity, dtype=float)
        if t.shape != v.shape:
            raise ValueError("time_s and velocity must have matching shapes.")

        df = pd.DataFrame(
            {
                time_col: t,
                vel_col: v,
                roi_col: np.full(t.shape, int(roi_id), dtype=int),
            }
        )
        analysis = HeartRateAnalysis(
            df,
            time_col=time_col,
            vel_col=vel_col,
            roi_col=roi_col,
            source="<arrays>",
        )

    if run_all:
        analysis.run_all_rois(cfg_by_roi=cfg_by_roi, cfg=cfg, methods=methods)
    else:
        if roi_id is None:
            raise ValueError("Explicit roi_id is required when run_all=False.")
        selected_roi = int(roi_id)
        analysis.run_roi(selected_roi, cfg=cfg, methods=methods)

    return analysis


def build_roi_summary_from_result(
    result: HeartRatePerRoiResults,
    *,
    file_label: str,
    minimal: bool | Literal["mini"] = True,
    agree_tol_bpm: float = AGREE_TOL_BPM_DEFAULT,
) -> dict[str, Any]:
    """Build a summary dictionary from one per-ROI result payload.

    Args:
        result: Per-ROI analysis payload.
        file_label: Source identifier/path label for this ROI result.
        minimal: ``True`` for compact stable schema, ``"mini"`` for batch-table
            schema, or ``False`` for full per-ROI payload.
        agree_tol_bpm: Agreement threshold for Lomb-vs-Welch delta in bpm.

    Returns:
        dict[str, Any]: JSON-serializable summary dictionary.
    """
    if minimal is False:
        return result.to_dict(compact=False)

    lomb = result.lomb
    welch = result.welch
    lomb_bpm = None if lomb is None else lomb.bpm
    welch_bpm = None if welch is None else welch.bpm
    delta_bpm = None
    agree_ok = None
    if (lomb_bpm is not None) and (welch_bpm is not None):
        delta_bpm = float(abs(float(lomb_bpm) - float(welch_bpm)))
        agree_ok = bool(delta_bpm <= float(agree_tol_bpm))

    status, status_note = _classify_status(result, agree_tol_bpm=float(agree_tol_bpm))
    if minimal == "mini":
        return {
            "file": Path(file_label).name,
            "roi_id": int(result.roi_id),
            "valid_frac": float(result.valid_fraction),
            "lomb_bpm": None if lomb is None else lomb.bpm,
            "lomb_hz": None if lomb is None else lomb.f_hz,
            "lomb_snr": None if lomb is None else lomb.snr,
            "welch_bpm": None if welch is None else welch.bpm,
            "welch_hz": None if welch is None else welch.f_hz,
            "welch_snr": None if welch is None else welch.snr,
            "agree_delta_bpm": delta_bpm,
            "agree_ok": agree_ok,
            "status": status.value,
            "status_note": status_note if status_note else "",
        }

    t_min = None
    t_max = None
    if result.time_range is not None:
        t_min = float(result.time_range[0])
        t_max = float(result.time_range[1])

    return {
        "file": file_label,
        "roi_id": int(result.roi_id),
        "n_total": int(result.n_total),
        "n_valid": int(result.n_valid),
        "valid_frac": float(result.valid_fraction),
        "t_min": t_min,
        "t_max": t_max,
        "lomb_bpm": None if lomb is None else lomb.bpm,
        "lomb_hz": None if lomb is None else lomb.f_hz,
        "lomb_snr": None if lomb is None else lomb.snr,
        "welch_bpm": None if welch is None else welch.bpm,
        "welch_hz": None if welch is None else welch.f_hz,
        "welch_snr": None if welch is None else welch.snr,
        "lomb_edge": None if lomb is None else lomb.edge_flag,
        "welch_edge": None if welch is None else welch.edge_flag,
        "lomb_bc": None if lomb is None else lomb.band_concentration,
        "welch_bc": None if welch is None else welch.band_concentration,
        "agree_delta_bpm": delta_bpm,
        "agree_ok": agree_ok,
        "status": status.value,
        "status_note": status_note,
    }


def _coerce_roi_to_int(series: pd.Series, *, roi_col: str) -> pd.Series:
    numeric = pd.to_numeric(series, errors="raise")
    if not np.all(np.isfinite(numeric.to_numpy(dtype=float))):
        raise ValueError(f"Column '{roi_col}' contains non-finite values.")

    arr = numeric.to_numpy(dtype=float)
    if not np.all(np.isclose(arr, np.round(arr))):
        raise ValueError(f"Column '{roi_col}' must contain integer-like values.")
    return pd.Series(np.round(arr).astype(int), index=series.index, name=series.name)


def _classify_status(
    result: HeartRatePerRoiResults,
    *,
    agree_tol_bpm: float,
) -> tuple[HRStatus, str]:
    """Classify a per-ROI result into a compact batch status.

    Args:
        result: Per-ROI analysis result.
        agree_tol_bpm: Agreement threshold for Lomb-vs-Welch bpm delta.

    Returns:
        tuple[HRStatus, str]: ``(status, status_note)`` where status is one of
        ``HRStatus.OK``, ``HRStatus.INSUFFICIENT_VALID``,
        ``HRStatus.NO_PEAK_LOMB``, ``HRStatus.NO_PEAK_WELCH``,
        ``method_disagree``, or ``other_error``.
    """
    lomb = result.lomb
    welch = result.welch
    lomb_ok = (lomb is not None) and (lomb.bpm is not None)
    welch_ok = (welch is not None) and (welch.bpm is not None)

    if lomb_ok and welch_ok:
        delta = abs(float(lomb.bpm) - float(welch.bpm))
        if delta > float(agree_tol_bpm):
            return HRStatus.METHOD_DISAGREE, f"abs delta bpm {delta:.1f} > tol {float(agree_tol_bpm):.1f}"
        return HRStatus.OK, ""

    # Milestone-1 policy: when at least one method yields an estimate, overall status is OK.
    if lomb_ok or welch_ok:
        return HRStatus.OK, ""

    if lomb is not None and lomb.status is HRStatus.INSUFFICIENT_VALID:
        return HRStatus.INSUFFICIENT_VALID, lomb.status_note
    if welch is not None and welch.status is HRStatus.INSUFFICIENT_VALID:
        return HRStatus.INSUFFICIENT_VALID, welch.status_note

    if lomb is not None and lomb.status is HRStatus.NO_PEAK_LOMB:
        return HRStatus.NO_PEAK_LOMB, lomb.status_note
    if welch is not None and welch.status is HRStatus.NO_PEAK_WELCH:
        return HRStatus.NO_PEAK_WELCH, welch.status_note

    note_parts = []
    if lomb is not None and lomb.status_note:
        note_parts.append(f"lomb: {lomb.status_note}")
    if welch is not None and welch.status_note:
        note_parts.append(f"welch: {welch.status_note}")
    note = "; ".join(note_parts) if note_parts else "no method estimate available"
    return HRStatus.OTHER_ERROR, note


def _coerce_hr_status(raw: Any, *, default: HRStatus) -> HRStatus:
    """Coerce status payload from debug dictionaries into ``HRStatus``."""
    if isinstance(raw, HRStatus):
        return raw
    if isinstance(raw, Enum):
        raw = raw.value
    if isinstance(raw, str):
        try:
            return HRStatus(raw)
        except ValueError:
            return default
    return default
