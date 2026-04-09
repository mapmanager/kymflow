"""Radon-based flow analysis for kymograph ROIs.

This module provides RadonAnalysis for performing per-ROI radon transform
flow analysis. RadonAnalysis depends only on AcqImage (no KymAnalysis).
"""

from __future__ import annotations

import multiprocessing as mp
import os
import queue
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict, List, Optional

import numpy as np
import pandas as pd

from kymflow.core.analysis.kym_flow_radon import mp_analyze_flow
from kymflow.core.analysis.utils import _medianFilter, _removeOutliers_sd, _removeOutliers_analyzeflow
from kymflow.core.utils.logging import get_logger
from kymflow.core.image_loaders.acq_analysis_base import AcqAnalysisBase
from kymflow.core.image_loaders.radon_report import RadonReport
from kymflow.core.image_loaders.roi import ROI

if TYPE_CHECKING:
    from kymflow.core.image_loaders.acq_image import AcqImage

logger = get_logger(__name__)

CancelCallback = Callable[[], bool]

# JSON version for radon-only persistence.
RADON_JSON_VERSION = "3.0"


@dataclass
class RoiAnalysisMetadata:
    """Analysis metadata for a specific ROI and channel.

    ROI geometry lives in AcqImage.rois. Channel is imposed at analysis time.
    """

    roi_id: int
    channel: int
    algorithm: str = "mpRadon"
    window_size: int | None = None
    analyzed_at: str | None = None
    analyzed_on: str | None = None
    roi_revision_at_analysis: int = 0


class RadonAnalysis(AcqAnalysisBase):
    """Radon-based flow analysis. Depends only on acq_image."""

    analysis_name: str = "RadonAnalysis"

    def __init__(self, acq_image: "AcqImage") -> None:
        super().__init__(acq_image)
        self._analysis_metadata: Dict[tuple[int, int], RoiAnalysisMetadata] = {}
        self._df: Optional[pd.DataFrame] = None
        self._dirty: bool = False

    # abb declan
    def get_kym_analysis(self) -> "KymAnalysis" | None:
        """try and get kym analysis if acq_image is actually a kymimage.
        """
        # check if acqimage has attribute (member function) get_kym_analysis
        if hasattr(self.acq_image, 'get_kym_analysis'):
            return self.acq_image.get_kym_analysis()
        else:
            return None

    def iter_roi_channel_keys(self) -> list[tuple[int, int]]:
        """Return all (roi_id, channel) keys that have radon analysis metadata."""
        return list(self._analysis_metadata.keys())

    @staticmethod
    def _meta_key(roi_id: int, channel: int) -> tuple[int, int]:
        return (roi_id, channel)

    def _filter_df_by_roi_channel(
        self,
        df: pd.DataFrame,
        roi_id: int,
        channel: int | None = None,
    ) -> pd.DataFrame:
        if "roi_id" not in df.columns:
            return pd.DataFrame()
        mask = df["roi_id"] == roi_id
        if channel is not None and "channel" in df.columns:
            mask = mask & (df["channel"] == channel)
        return df[mask].copy()

    def _get_primary_path(self) -> Path | None:
        return self.acq_image.path

    def _get_first_meta_for_roi(self, roi_id: int) -> RoiAnalysisMetadata | None:
        for key, meta in self._analysis_metadata.items():
            if key[0] == roi_id:
                return meta
        return None

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    def has_analysis(self, roi_id: int | None = None, channel: int | None = None) -> bool:
        """Check if radon analysis exists for (roi_id, channel) or any analysis.

        Args:
            roi_id: ROI identifier, or None to check if any analysis exists.
            channel: 1-based channel index. Required when roi_id is given.

        Returns:
            True if analysis exists.

        Raises:
            TypeError: If roi_id is given but channel is None.
        """
        if roi_id is None:
            return bool(self._analysis_metadata)
        if channel is None:
            raise TypeError("channel is required when roi_id is given")
        return self._meta_key(roi_id, channel) in self._analysis_metadata

    def get_analysis_metadata(self, roi_id: int, channel: int) -> RoiAnalysisMetadata | None:
        """Get analysis metadata for (roi_id, channel).

        Args:
            roi_id: ROI identifier.
            channel: 1-based channel index.

        Returns:
            RoiAnalysisMetadata or None if not found.
        """
        return self._analysis_metadata.get(self._meta_key(roi_id, channel))

    def get_channel_for_roi(self, roi_id: int) -> int | None:
        """Return channel index for first analysis found for roi_id.

        Args:
            roi_id: ROI identifier.

        Returns:
            1-based channel index, or None if no analysis for this ROI.
        """
        meta = self._get_first_meta_for_roi(roi_id)
        return meta.channel if meta is not None else None

    def has_v0_flow_analysis(self, roi_id: int, channel: int) -> bool:
        """Check if (roi_id, channel) has legacy v0 flow analysis.

        Args:
            roi_id: ROI identifier.
            channel: 1-based channel index.

        Returns:
            True if v0 analysis exists.
        """
        amd = self.get_analysis_metadata(roi_id, channel)
        return amd is not None and amd.algorithm == "mpRadon_v0"

    def is_stale(self, roi_id: int, channel: int) -> bool:
        """Check if analysis for (roi_id, channel) is stale (ROI geometry changed).

        Args:
            roi_id: ROI identifier.
            channel: 1-based channel index.

        Returns:
            True if stale or ROI not found.
        """
        roi = self.acq_image.rois.get(roi_id)
        if roi is None:
            return True
        meta = self.get_analysis_metadata(roi_id, channel)
        if meta is None:
            return True
        return roi.revision != meta.roi_revision_at_analysis

    def invalidate(self, roi_id: int, channel: int | None = None) -> None:
        """Invalidate radon analysis for (roi_id, channel) or all channels for roi_id.

        Args:
            roi_id: ROI identifier.
            channel: 1-based channel index, or None to invalidate all channels for roi_id.
        """
        if channel is not None:
            key = self._meta_key(roi_id, channel)
            if key in self._analysis_metadata:
                del self._analysis_metadata[key]
            self._remove_roi_data_from_df(roi_id, channel)
        else:
            keys_to_remove = [k for k in self._analysis_metadata if k[0] == roi_id]
            for k in keys_to_remove:
                del self._analysis_metadata[k]
            self._remove_all_roi_data_from_df(roi_id)
        self._dirty = True

    def clear_analysis_for_roi_channel(self, roi_id: int, channel: int) -> None:
        """Remove in-memory radon analysis for (roi_id, channel).

        Clears metadata and DataFrame rows for this pair and sets is_dirty.
        Delegates to :meth:`invalidate` with a fixed channel (same semantics).

        Args:
            roi_id: ROI identifier.
            channel: 1-based channel index.
        """
        self.invalidate(roi_id, channel)

    def _remove_roi_data_from_df(self, roi_id: int, channel: int) -> None:
        if self._df is None or "roi_id" not in self._df.columns:
            return
        mask = (self._df["roi_id"] != roi_id) | (self._df["channel"] != channel)
        self._df = self._df[mask].copy()
        if len(self._df) == 0:
            self._df = self._create_empty_velocity_df()

    def _remove_all_roi_data_from_df(self, roi_id: int) -> None:
        if self._df is not None and "roi_id" in self._df.columns:
            self._df = self._df[self._df["roi_id"] != roi_id].copy()
            if len(self._df) == 0:
                self._df = self._create_empty_velocity_df()

    def _get_radon_paths(self, folder_path: Path) -> tuple[Path, Path]:
        """Return (csv_path, json_path) for radon persistence."""
        primary_path = self._get_primary_path()
        if primary_path is None:
            raise ValueError("No file path available for radon save paths")
        base_name = primary_path.stem
        csv_path = folder_path / f"{base_name}_radon.csv"
        json_path = folder_path / f"{base_name}_radon.json"
        return csv_path, json_path

    def analyze_roi(
        self,
        roi_id: int,
        channel: int,
        window_size: int,
        *,
        progress_queue: Optional[queue.Queue] = None,
        is_cancelled: Optional[CancelCallback] = None,
        use_multiprocessing: bool = True,
    ) -> None:
        """Run radon flow analysis for (roi_id, channel).

        Args:
            roi_id: ROI identifier.
            channel: 1-based channel index.
            window_size: Number of time lines per analysis window.
            progress_queue: Optional queue for progress updates.
            is_cancelled: Optional callback to check for cancellation.
            use_multiprocessing: If True, use multiprocessing for flow computation.

        Raises:
            ValueError: If ROI not found.
        """
        roi = self.acq_image.rois.get(roi_id)
        if roi is None:
            raise ValueError(f"ROI {roi_id} not found")

        image = self.acq_image.get_img_slice(channel=channel)
        start_pixel = roi.bounds.dim0_start
        stop_pixel = roi.bounds.dim0_stop
        start_line = roi.bounds.dim1_start
        stop_line = roi.bounds.dim1_stop

        thetas, the_t, spread = mp_analyze_flow(
            image,
            window_size,
            start_pixel,
            stop_pixel,
            start_line,
            stop_line,
            progress_queue=progress_queue,
            is_cancelled=is_cancelled,
            use_multiprocessing=use_multiprocessing,
            verbose=False,
        )

        now_iso = datetime.now(timezone.utc).isoformat()
        key = self._meta_key(roi_id, channel)
        self._analysis_metadata[key] = RoiAnalysisMetadata(
            roi_id=roi_id,
            channel=channel,
            algorithm="mpRadon",
            window_size=window_size,
            analyzed_at=now_iso,
            analyzed_on=now_iso,
            roi_revision_at_analysis=roi.revision,
        )

        seconds_per_line = self.acq_image.seconds_per_line
        um_per_pixel = self.acq_image.um_per_pixel
        drew_time = the_t * seconds_per_line
        _rad = np.deg2rad(thetas)
        drew_velocity = (um_per_pixel / seconds_per_line) * np.tan(_rad)
        drew_velocity = drew_velocity / 1000  # mm/s

        roi_df = self._make_velocity_df(drew_velocity, drew_time, roi_id, channel)
        if self._df is None:
            self._df = roi_df
        else:
            self._remove_roi_data_from_df(roi_id, channel)
            if self._df.empty:
                self._df = roi_df
            else:
                self._df = pd.concat([self._df, roi_df], ignore_index=True)
        self._dirty = True

    def _make_velocity_df(
        self,
        velocity: np.ndarray,
        time_values: np.ndarray,
        roi_id: int,
        channel: int,
    ) -> pd.DataFrame:
        clean_velocity = _removeOutliers_sd(velocity)
        clean_velocity = _medianFilter(clean_velocity, window_size=3)
        primary_path = self._get_primary_path()
        parent_name = primary_path.parent.name if primary_path is not None else ""
        file_name = primary_path.name if primary_path is not None else ""
        shape = self.acq_image.img_shape
        num_lines = shape[0] if shape is not None else 0
        pixels_per_line = shape[1] if shape is not None else 0
        seconds_per_line = self.acq_image.seconds_per_line
        um_per_pixel = self.acq_image.um_per_pixel
        roi_df = pd.DataFrame({
            "roi_id": roi_id,
            "channel": channel,
            "time": time_values,
            "velocity": velocity,
            "parentFolder": parent_name,
            "file": file_name,
            "algorithm": "mpRadon",
            "delx": um_per_pixel,
            "delt": seconds_per_line,
            "numLines": num_lines,
            "pntsPerLine": pixels_per_line,
            "cleanVelocity": clean_velocity,
            "absVelocity": abs(clean_velocity),
        })
        return roi_df

    def _create_empty_velocity_df(self) -> pd.DataFrame:
        return pd.DataFrame({
            "roi_id": pd.Series(dtype="int64"),
            "channel": pd.Series(dtype="int64"),
            "time": pd.Series(dtype="float64"),
            "velocity": pd.Series(dtype="float64"),
            "parentFolder": pd.Series(dtype="string"),
            "file": pd.Series(dtype="string"),
            "algorithm": pd.Series(dtype="string"),
            "delx": pd.Series(dtype="float64"),
            "delt": pd.Series(dtype="float64"),
            "numLines": pd.Series(dtype="int64"),
            "pntsPerLine": pd.Series(dtype="int64"),
            "cleanVelocity": pd.Series(dtype="float64"),
            "absVelocity": pd.Series(dtype="float64"),
        })

    def _try_load_v0_into_existing_roi(self, folder_path: Path) -> bool:
        primary_path = self._get_primary_path()
        if primary_path is None:
            return False
        if self.acq_image.rois.numRois() != 1:
            return False
        if self._analysis_metadata:
            return False

        v0_folder = primary_path.parent / f"{primary_path.parent.name}-analysis"
        v0_csv = v0_folder / f"{primary_path.stem}.csv"
        if not v0_folder.exists() or not v0_csv.exists():
            return False

        roi_ids = self.acq_image.rois.get_roi_ids()
        if len(roi_ids) != 1:
            return False
        existing_roi = self.acq_image.rois.get(roi_ids[0])
        if existing_roi is None:
            return False

        try:
            old_vel_df = pd.read_csv(v0_csv)
        except Exception as e:
            logger.warning(f"Failed to read v0 CSV {v0_csv}: {e}")
            return False
        if "velocity" not in old_vel_df.columns or "time" not in old_vel_df.columns:
            return False

        old_vel = old_vel_df["velocity"].values
        old_time = old_vel_df["time"].values
        roi_df = self._make_velocity_df(old_vel, old_time, existing_roi.id, 1)
        self._df = roi_df
        now_iso = datetime.now(timezone.utc).isoformat()
        key = self._meta_key(existing_roi.id, 1)
        self._analysis_metadata[key] = RoiAnalysisMetadata(
            roi_id=existing_roi.id,
            channel=1,
            algorithm="mpRadon_v0",
            window_size=16,
            analyzed_at=now_iso,
            analyzed_on=now_iso,
            roi_revision_at_analysis=existing_roi.revision,
        )
        self._dirty = True
        return True

    def import_v0_analysis(self, folder_path: Path) -> Optional[bool]:
        """Import v0 analysis. Only runs if num_rois is 0."""
        if self.acq_image.rois.numRois() > 0:
            return None
        if self.acq_image.path is None:
            return None

        _v0_analysis_folder = f"{self.acq_image.path.parent.name}-analysis"
        old_analysis_folder_path = self.acq_image.path.parent / _v0_analysis_folder
        if not old_analysis_folder_path.exists():
            return None
        old_vel_csv = old_analysis_folder_path / f"{self.acq_image.path.stem}.csv"
        if not old_vel_csv.exists():
            return None

        new_roi = self.acq_image.rois.create_roi()
        now_iso = datetime.now(timezone.utc).isoformat()
        key = self._meta_key(new_roi.id, 1)
        self._analysis_metadata[key] = RoiAnalysisMetadata(
            roi_id=new_roi.id,
            channel=1,
            algorithm="mpRadon_v0",
            window_size=16,
            analyzed_at=now_iso,
            analyzed_on=now_iso,
            roi_revision_at_analysis=new_roi.revision,
        )
        old_vel_df = pd.read_csv(old_vel_csv)
        old_vel = old_vel_df["velocity"].values
        old_time = old_vel_df["time"].values
        roi_df = self._make_velocity_df(old_vel, old_time, new_roi.id, 1)
        self._df = roi_df
        self._dirty = True
        return True

    def save_analysis(self, folder_path: Path) -> bool:
        csv_path, json_path = self._get_radon_paths(folder_path)
        folder_path.mkdir(parents=True, exist_ok=True)

        current_roi_ids = {roi.id for roi in self.acq_image.rois}
        self._analysis_metadata = {
            rid: meta for rid, meta in self._analysis_metadata.items()
            if rid[0] in current_roi_ids
        }
        if self._df is not None and "roi_id" in self._df.columns:
            self._df = self._df[self._df["roi_id"].isin(current_roi_ids)].copy()

        if self._df is not None:
            self._df.to_csv(csv_path, index=False)

        import json
        json_data = {
            "version": RADON_JSON_VERSION,
            "analysis_metadata": {
                f"{meta.roi_id}:{meta.channel}": {
                    "roi_id": meta.roi_id,
                    "channel": meta.channel,
                    "algorithm": meta.algorithm,
                    "window_size": meta.window_size,
                    "analyzed_at": meta.analyzed_at,
                    "analyzed_on": meta.analyzed_on,
                    "roi_revision_at_analysis": meta.roi_revision_at_analysis,
                }
                for rid, meta in self._analysis_metadata.items()
            },
        }
        with open(json_path, "w") as f:
            json.dump(json_data, f, indent=2, default=str)
        self._dirty = False
        return True

    def load_analysis(self, folder_path: Path) -> bool:
        csv_path, json_path = self._get_radon_paths(folder_path)

        if self.import_v0_analysis(folder_path) is not None:
            return True

        primary_path = self._get_primary_path()
        if primary_path is None:
            return False

        if not json_path.exists():
            if self._try_load_v0_into_existing_roi(folder_path):
                return True
            return False

        import json
        with open(json_path, "r") as f:
            json_data = json.load(f)

        version = str(json_data.get("version", ""))
        if "analysis_metadata" not in json_data:
            return False
        if not (version.startswith("2.") or version.startswith("3.")):
            return False

        self._analysis_metadata.clear()
        for json_key, meta in json_data.get("analysis_metadata", {}).items():
            try:
                parts = str(json_key).split(":")
                roi_id = int(meta.get("roi_id", parts[0]))
                channel = int(meta.get("channel", 1))
                analyzed_at = meta.get("analyzed_at")
                analyzed_on = meta.get("analyzed_on") or analyzed_at
                key = self._meta_key(roi_id, channel)
                self._analysis_metadata[key] = RoiAnalysisMetadata(
                    roi_id=roi_id,
                    channel=channel,
                    algorithm=str(meta.get("algorithm", "mpRadon")),
                    window_size=meta.get("window_size"),
                    analyzed_at=analyzed_at,
                    analyzed_on=analyzed_on,
                    roi_revision_at_analysis=int(meta.get("roi_revision_at_analysis", 0)),
                )
            except Exception as e:
                logger.warning(f"Skipping invalid analysis metadata entry {json_key}: {e}")

        if csv_path.exists():
            self._df = pd.read_csv(csv_path)
        else:
            self._df = None

        current_roi_ids = {roi.id for roi in self.acq_image.rois}
        self._analysis_metadata = {
            rid: meta for rid, meta in self._analysis_metadata.items()
            if rid[0] in current_roi_ids
        }
        if self._df is not None and "roi_id" in self._df.columns:
            self._df = self._df[self._df["roi_id"].isin(current_roi_ids)].copy()
        self._dirty = False
        return True

    def load_from_combined_v2(self, json_data: dict, csv_path: Path | None) -> None:
        """Load from v2.x/v3.x combined JSON (migration path)."""
        self._analysis_metadata.clear()
        for json_key, meta in json_data.get("analysis_metadata", {}).items():
            try:
                parts = str(json_key).split(":")
                roi_id = int(meta.get("roi_id", parts[0]))
                channel = int(meta.get("channel", 1))
                analyzed_at = meta.get("analyzed_at")
                analyzed_on = meta.get("analyzed_on") or analyzed_at
                key = self._meta_key(roi_id, channel)
                self._analysis_metadata[key] = RoiAnalysisMetadata(
                    roi_id=roi_id,
                    channel=channel,
                    algorithm=str(meta.get("algorithm", "mpRadon")),
                    window_size=meta.get("window_size"),
                    analyzed_at=analyzed_at,
                    analyzed_on=analyzed_on,
                    roi_revision_at_analysis=int(meta.get("roi_revision_at_analysis", 0)),
                )
            except Exception:
                pass
        if csv_path is not None and csv_path.exists():
            self._df = pd.read_csv(csv_path)
        else:
            self._df = None
        current_roi_ids = {roi.id for roi in self.acq_image.rois}
        self._analysis_metadata = {
            rid: meta for rid, meta in self._analysis_metadata.items()
            if rid[0] in current_roi_ids
        }
        if self._df is not None and "roi_id" in self._df.columns:
            self._df = self._df[self._df["roi_id"].isin(current_roi_ids)].copy()

    def get_analysis(
        self, roi_id: Optional[int] = None, channel: Optional[int] = None
    ) -> Optional[pd.DataFrame]:
        """Get velocity DataFrame for (roi_id, channel) or full DataFrame.

        Args:
            roi_id: ROI identifier, or None for full DataFrame.
            channel: 1-based channel index. Required when roi_id is given.

        Returns:
            Filtered or full DataFrame, or None if no analysis.

        Raises:
            TypeError: If roi_id is given but channel is None.
        """
        if self._df is None:
            return None
        if roi_id is None:
            return self._df.copy()
        if channel is None:
            raise TypeError("channel is required when roi_id is given")
        return self._filter_df_by_roi_channel(self._df, roi_id, channel=channel)

    def get_analysis_value(
        self,
        roi_id: int,
        channel: int,
        key: str,
        remove_outliers: bool = False,
        median_filter: int = 0,
    ) -> Optional[np.ndarray]:
        """Return analysis column values for (roi_id, channel).

        Args:
            roi_id: ROI identifier.
            channel: 1-based channel index.
            key: Column name (e.g. "velocity", "time").
            remove_outliers: If True, apply outlier removal.
            median_filter: Median filter window size, 0 to disable.

        Returns:
            NumPy array of values, or None if analysis or column not found.
        """
        roi_df = self.get_analysis(roi_id=roi_id, channel=channel)
        if roi_df is None or key not in roi_df.columns:
            return None
        if remove_outliers or median_filter > 0:
            values = roi_df[key].values.copy()
        else:
            values = roi_df[key].values
        if remove_outliers:
            values = _removeOutliers_analyzeflow(values)
        if median_filter > 0:
            values = _medianFilter(values, median_filter)
        return values

    def get_radon_report(self, *, accepted: bool = True) -> List[RadonReport]:
        report: List[RadonReport] = []
        roi_ids = self.acq_image.rois.get_roi_ids()
        path = str(self.acq_image.path) if self.acq_image.path is not None else None
        file_name = self.acq_image.path.stem if self.acq_image.path is not None else None
        parent_folder: Optional[str] = None
        grandparent_folder: Optional[str] = None
        if self.acq_image.path is not None and self.acq_image.path.parent:
            parent_folder = self.acq_image.path.parent.name
            if self.acq_image.path.parent.parent:
                grandparent_folder = self.acq_image.path.parent.parent.name
        em = self.acq_image.experiment_metadata
        treatment = getattr(em, "treatment", None) or None
        condition = getattr(em, "condition", None) or None
        date = getattr(em, "date", None) or None

        for roi_id in roi_ids:
            channel = self.get_channel_for_roi(roi_id)
            if channel is None:
                velocity = None
            else:
                velocity = self.get_analysis_value(roi_id, channel, "velocity")

            vel_min = vel_max = vel_mean = vel_std = vel_se = vel_cv = None
            vel_n_nan = vel_n_zero = vel_n_big = None

            # abb declan 20260407
            user_added_count: Optional[int] = None
            user_added_dur_sum: Optional[float] = None
            user_added_dur_mean: Optional[float] = None

            if velocity is not None and len(velocity) > 0 and not np.all(np.isnan(velocity)):
                vel_min = float(np.nanmin(velocity))
                vel_max = float(np.nanmax(velocity))
                vel_mean = float(np.nanmean(velocity))
                vel_std = float(np.nanstd(velocity))
                if vel_mean and abs(vel_mean) > 1e-10 and vel_std is not None:
                    vel_cv = vel_std / vel_mean
                n_valid = np.sum(~np.isnan(velocity))
                if vel_std is not None and n_valid > 0:
                    vel_se = vel_std / np.sqrt(n_valid)
                vel_n_nan = int(np.sum(np.isnan(velocity)))
                vel_n_zero = int(np.sum((velocity == 0) & (~np.isnan(velocity))))
                if vel_mean is not None and vel_std is not None:
                    big_threshold = vel_mean + 2.0 * vel_std
                    vel_n_big = int(np.sum((velocity > big_threshold) & (~np.isnan(velocity))))

                #abb declan 20260407
                kym_analysis = self.get_kym_analysis()
                if kym_analysis is not None:
                    user_added_count, user_added_dur_sum, user_added_dur_mean = kym_analysis._get_user_added_stats(roi_id, channel)

            roi = self.acq_image.rois.get(roi_id)
            if roi is None:
                img_min = img_max = img_mean = img_std = None
            else:
                img_min = roi.img_min
                img_max = roi.img_max
                img_mean = float(roi.img_mean) if roi.img_mean is not None else None
                img_std = float(roi.img_std) if roi.img_std is not None else None

            report.append(RadonReport(
                roi_id=roi_id,
                channel=channel,
                vel_min=vel_min,
                vel_max=vel_max,
                vel_mean=vel_mean,
                vel_std=vel_std,
                vel_se=vel_se,
                vel_cv=vel_cv,
                vel_n_nan=vel_n_nan,
                vel_n_zero=vel_n_zero,
                vel_n_big=vel_n_big,

                users_added_count=user_added_count,
                users_added_dur_sum=user_added_dur_sum,
                users_added_dur_mean=user_added_dur_mean,

                img_min=img_min,
                img_max=img_max,
                img_mean=img_mean,
                img_std=img_std,
                path=path,
                file_name=file_name,
                parent_folder=parent_folder,
                grandparent_folder=grandparent_folder,
                accepted=accepted,
                treatment=treatment,
                condition=condition,
                date=date,
            ))
        return report
