from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Literal, Optional, Sequence

import pandas as pd

from heart_rate_pipeline import (
    HRAnalysisConfig,
    HeartRateAnalysis,
    HeartRatePerRoiResults,
    build_roi_summary_from_result,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HRBatchTask:
    """One batch-analysis task over either a CSV path or a dataframe.

    Args:
        csv_path: CSV input path for this task.
        df: In-memory dataframe input for this task.
        source_id: Optional source identifier used in outputs.
        roi_ids: Optional ROI ids to analyze; defaults to all ROI ids in input.
        cfg: Optional task-specific analysis config.

    Raises:
        ValueError: If both or neither of ``csv_path`` and ``df`` are provided.
    """

    csv_path: Optional[Path] = None
    df: Optional[pd.DataFrame] = None
    source_id: Optional[str] = None
    roi_ids: Optional[Sequence[int]] = None
    cfg: Optional[HRAnalysisConfig] = None

    def __post_init__(self) -> None:
        has_csv = self.csv_path is not None
        has_df = self.df is not None
        if has_csv == has_df:
            raise ValueError("Exactly one of csv_path or df must be provided.")
        if has_csv and not isinstance(self.csv_path, Path):
            object.__setattr__(self, "csv_path", Path(self.csv_path))
        if self.df is not None and self.source_id is None:
            object.__setattr__(self, "source_id", "<df>")
        if self.csv_path is not None and self.source_id is None:
            object.__setattr__(self, "source_id", str(self.csv_path))


@dataclass(frozen=True)
class HeartRateFileResult:
    """Batch output for one source file/dataframe.

    Args:
        source_id: Source identifier for this file-level result.
        per_roi: Mapping from roi_id to per-ROI analysis payload.
    """

    source_id: str
    per_roi: dict[int, HeartRatePerRoiResults]


@dataclass(frozen=True)
class HRBatchSaveResult:
    """Per-file save result for ``batch_run_and_save``.

    Args:
        csv_path: Source CSV path processed.
        ok: True when analysis/save completed or was skipped due to overwrite=False.
        saved_json_path: Path to persisted JSON when available.
        error: Error message for failed files.
    """

    csv_path: Path
    ok: bool
    saved_json_path: Optional[Path]
    error: str = ""


def compute_hr_for_df(
    df: pd.DataFrame,
    *,
    roi_ids: Optional[Sequence[int]],
    cfg: HRAnalysisConfig,
    source_id: str,
) -> HeartRateFileResult:
    """Run HR analysis for one dataframe source.

    Args:
        df: Input dataframe with required columns including ``roi_id``.
        roi_ids: Optional ROI ids to analyze; defaults to all.
        cfg: Analysis config for this task.
        source_id: Source identifier for this output record.

    Returns:
        HeartRateFileResult: Structured file-level result.
    """
    analysis = HeartRateAnalysis(df, source_path=None)
    selected = analysis.roi_ids if roi_ids is None else [int(x) for x in roi_ids]
    cfg_obj = HRAnalysisConfig.from_any(cfg)
    for rid in selected:
        analysis.run_roi(rid, cfg=cfg_obj)
    return HeartRateFileResult(source_id=source_id, per_roi=dict(analysis.results_by_roi))


def compute_hr_for_csv(
    csv_path: Path,
    *,
    roi_ids: Optional[Sequence[int]],
    cfg: HRAnalysisConfig,
) -> HeartRateFileResult:
    """Run HR analysis for one CSV source.

    Args:
        csv_path: CSV path to analyze.
        roi_ids: Optional ROI ids to analyze; defaults to all.
        cfg: Analysis config for this task.

    Returns:
        HeartRateFileResult: Structured file-level result.
    """
    csv_path = Path(csv_path)
    df = pd.read_csv(csv_path)
    return compute_hr_for_df(df, roi_ids=roi_ids, cfg=cfg, source_id=str(csv_path))


def _process_csv_task(payload: tuple[str, Optional[list[int]], dict]) -> HeartRateFileResult:
    """Top-level worker for process backend (pickle-safe)."""
    csv_path_str, roi_ids, cfg_payload = payload
    cfg = HRAnalysisConfig.from_dict(cfg_payload)
    return compute_hr_for_csv(Path(csv_path_str), roi_ids=roi_ids, cfg=cfg)


def _thread_task(task: HRBatchTask, cfg_obj: HRAnalysisConfig) -> HeartRateFileResult:
    """Run one task on thread backend."""
    if task.csv_path is not None:
        return compute_hr_for_csv(task.csv_path, roi_ids=task.roi_ids, cfg=cfg_obj)
    if task.df is None:
        raise ValueError("Invalid task: neither csv_path nor df provided.")
    source_id = task.source_id or "<df>"
    return compute_hr_for_df(task.df, roi_ids=task.roi_ids, cfg=cfg_obj, source_id=source_id)


def run_hr_batch(
    tasks: Sequence[HRBatchTask],
    *,
    default_cfg: Optional[HRAnalysisConfig] = None,
    n_workers: int = 0,
    backend: Literal["process", "thread"] = "process",
) -> list[HeartRateFileResult]:
    """Run HR analysis over many tasks with process or thread backend.

    Args:
        tasks: Batch task sequence.
        default_cfg: Optional default config for tasks missing ``task.cfg``.
        n_workers: Worker count. Non-positive values use executor defaults.
        backend: ``"process"`` or ``"thread"``.

    Returns:
        list[HeartRateFileResult]: One result per task, preserving task order.

    Raises:
        ValueError: If backend is invalid or process backend receives dataframe tasks.
    """
    if backend not in {"process", "thread"}:
        raise ValueError(f"Unsupported backend={backend!r}.")
    cfg_default = HRAnalysisConfig() if default_cfg is None else HRAnalysisConfig.from_any(default_cfg)
    max_workers = None if int(n_workers) <= 0 else int(n_workers)
    if not tasks:
        return []

    if backend == "process":
        for task in tasks:
            if task.df is not None or task.csv_path is None:
                raise ValueError("backend='process' requires tasks with csv_path only (df tasks are not allowed).")
        payloads: list[tuple[str, Optional[list[int]], dict]] = []
        for task in tasks:
            cfg_obj = HRAnalysisConfig.from_any(task.cfg if task.cfg is not None else cfg_default)
            rid_list = None if task.roi_ids is None else [int(x) for x in task.roi_ids]
            payloads.append((str(task.csv_path), rid_list, cfg_obj.to_dict()))
        with ProcessPoolExecutor(max_workers=max_workers) as pool:
            return list(pool.map(_process_csv_task, payloads))

    cfgs = [HRAnalysisConfig.from_any(t.cfg if t.cfg is not None else cfg_default) for t in tasks]
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(_thread_task, task, cfg_obj) for task, cfg_obj in zip(tasks, cfgs)]
        return [f.result() for f in futures]


def batch_results_to_dataframe(
    results: Sequence[HeartRateFileResult],
    *,
    roi_id: Optional[int] = None,
    minimal: Literal["mini", "full"] = "mini",
) -> pd.DataFrame:
    """Convert batch results to a dataframe of per-ROI summaries.

    Args:
        results: Batch file-level results.
        roi_id: Optional ROI filter. When omitted, include all.
        minimal: ``"mini"`` for compact summary or ``"full"`` for full per-ROI payload.

    Returns:
        pd.DataFrame: One row per included ``(source_id, roi_id)``.
    """
    rows: list[dict] = []
    for file_result in results:
        for rid in sorted(file_result.per_roi.keys()):
            if roi_id is not None and int(rid) != int(roi_id):
                continue
            if minimal == "mini":
                row = build_roi_summary_from_result(
                    file_result.per_roi[rid],
                    file_label=file_result.source_id,
                    minimal="mini",
                )
            else:
                row = build_roi_summary_from_result(
                    file_result.per_roi[rid],
                    file_label=file_result.source_id,
                    minimal=False,
                )
                row["file"] = file_result.source_id
            rows.append(row)

    if minimal == "mini":
        mini_cols = [
            "file",
            "roi_id",
            "valid_frac",
            "lomb_bpm",
            "lomb_hz",
            "lomb_snr",
            "welch_bpm",
            "welch_hz",
            "welch_snr",
            "agree_delta_bpm",
            "agree_ok",
            "status",
            "status_note",
        ]
        if not rows:
            return pd.DataFrame(columns=mini_cols)
        return pd.DataFrame(rows).reindex(columns=mini_cols)

    return pd.DataFrame(rows)


def _run_and_save_one_csv(
    csv_path: Path,
    *,
    roi_ids: Optional[Sequence[int]],
    cfg: Optional[HRAnalysisConfig],
    overwrite: bool,
) -> HRBatchSaveResult:
    """Run analysis and persist one CSV file to ``*_heart_rate.json``.

    Args:
        csv_path: Source CSV path.
        roi_ids: Optional ROI ids to analyze; defaults to all in the file.
        cfg: Optional shared config. Defaults to ``HRAnalysisConfig()``.
        overwrite: Whether to recompute/overwrite existing JSON output.

    Returns:
        HRBatchSaveResult: Success/failure record for this CSV.
    """
    csv_path = Path(csv_path)
    try:
        analysis = HeartRateAnalysis.from_csv(csv_path)
        out_path = analysis.default_results_json_path()
        if (not overwrite) and out_path.exists():
            return HRBatchSaveResult(csv_path=csv_path, ok=True, saved_json_path=out_path, error="")

        selected_roi_ids: list[int]
        if roi_ids is None:
            selected_roi_ids = list(analysis.roi_ids)
        else:
            selected_roi_ids = [int(x) for x in roi_ids]
            missing = [rid for rid in selected_roi_ids if rid not in analysis.roi_ids]
            if missing:
                return HRBatchSaveResult(
                    csv_path=csv_path,
                    ok=False,
                    saved_json_path=None,
                    error=f"Requested roi_ids not found in file: {missing}; available={analysis.roi_ids}",
                )

        cfg_obj = HRAnalysisConfig() if cfg is None else HRAnalysisConfig.from_any(cfg)
        for rid in selected_roi_ids:
            analysis.run_roi(rid, cfg=cfg_obj)
        saved = analysis.save_results_json(out_path)
        return HRBatchSaveResult(csv_path=csv_path, ok=True, saved_json_path=saved, error="")
    except Exception as e:
        logger.warning("HR batch failed for %s: %s", csv_path, e)
        return HRBatchSaveResult(csv_path=csv_path, ok=False, saved_json_path=None, error=str(e))


def _run_and_save_worker(payload: tuple[str, Optional[list[int]], Optional[dict], bool]) -> HRBatchSaveResult:
    """Top-level process worker for ``batch_run_and_save``."""
    csv_path_str, roi_ids, cfg_payload, overwrite = payload
    cfg = None if cfg_payload is None else HRAnalysisConfig.from_dict(cfg_payload)
    return _run_and_save_one_csv(Path(csv_path_str), roi_ids=roi_ids, cfg=cfg, overwrite=overwrite)


def batch_run_and_save(
    csv_paths: Sequence[Path],
    *,
    roi_ids: Optional[Sequence[int]] = None,
    cfg: Optional[HRAnalysisConfig] = None,
    overwrite: bool = True,
    backend: Literal["process", "thread", "serial"] = "process",
    n_workers: int = 0,
) -> list[HRBatchSaveResult]:
    """Run HR analysis for each CSV and save JSON next to each source file.

    Args:
        csv_paths: Source CSV paths to process.
        roi_ids: Optional ROI ids to analyze. When ``None``, analyzes all rois
            found in each file.
        cfg: Optional shared config used for every ROI in every file.
        overwrite: When False and output JSON exists, skip recomputation.
        backend: ``"serial"``, ``"thread"``, or ``"process"``.
        n_workers: Worker count for thread/process backends. Non-positive values
            use executor defaults.

    Returns:
        list[HRBatchSaveResult]: Per-input CSV save result in input order.

    Raises:
        ValueError: If input list is empty or backend is unsupported.
    """
    if not csv_paths:
        raise ValueError("csv_paths must contain at least one path.")
    if backend not in {"process", "thread", "serial"}:
        raise ValueError(f"Unsupported backend={backend!r}.")

    csv_list = [Path(p) for p in csv_paths]
    rid_list = None if roi_ids is None else [int(x) for x in roi_ids]
    cfg_obj = None if cfg is None else HRAnalysisConfig.from_any(cfg)
    max_workers = None if int(n_workers) <= 0 else int(n_workers)

    if backend == "serial":
        return [
            _run_and_save_one_csv(path, roi_ids=rid_list, cfg=cfg_obj, overwrite=overwrite)
            for path in csv_list
        ]

    if backend == "thread":
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [
                pool.submit(_run_and_save_one_csv, path, roi_ids=rid_list, cfg=cfg_obj, overwrite=overwrite)
                for path in csv_list
            ]
            return [f.result() for f in futures]

    cfg_payload = None if cfg_obj is None else cfg_obj.to_dict()
    payloads = [(str(path), rid_list, cfg_payload, bool(overwrite)) for path in csv_list]
    with ProcessPoolExecutor(max_workers=max_workers) as pool:
        return list(pool.map(_run_and_save_worker, payloads))
