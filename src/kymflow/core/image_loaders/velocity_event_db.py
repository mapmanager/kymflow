"""Velocity event database for KymImageList.

Maintains a denormalized cache of VelocityEvent across all (path, roi) in a KymImageList.
Persisted as kym_event_db.csv. Follows the same patterns as radon_report_db but encapsulates
all CRUD and I/O in this class.
"""

from __future__ import annotations
import os
from dataclasses import fields
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict, Iterable, List, Optional

import pandas as pd

from kymflow.core.image_loaders.velocity_event_report import (
    VELOCITY_EVENT_CSV_ROUND_DECIMALS,
    VelocityEventReport,
)
from kymflow.core.utils.logging import get_logger
from kymflow.core.utils.hidden_cache_paths import (
    ensure_hidden_cache_dir,
    get_hidden_cache_path,
)
from kymflow.core.utils.progress import CancelledError, ProgressCallback, ProgressMessage

if TYPE_CHECKING:
    from kymflow.core.image_loaders.kym_image import KymImage

logger = get_logger(__name__)

# Required columns for CSV schema validation (must match VelocityEventReport fields)
_EXPECTED_COLS = {
    "_unique_row_id",
    "path",
    "roi_id",
    "channel",
    "rel_path",
    "parent_folder",
    "grandparent_folder",
    "event_type",
    "i_start",
    "t_start",
    "i_peak",
    "t_peak",
    "i_end",
    "t_end",
    "score_peak",
    "baseline_before",
    "baseline_after",
    "strength",
    "nan_fraction_in_event",
    "n_valid_in_event",
    "duration_sec",
    "machine_type",
    "user_type",
    "note",
    "accepted",
}


def _norm_event_tuple(
    t_start: Optional[float],
    t_end: Optional[float],
    event_type: Optional[str],
    round_decimals: int = VELOCITY_EVENT_CSV_ROUND_DECIMALS,
) -> tuple:
    """Canonical tuple for staleness comparison. Rounds values; treats None and nan as equivalent for t_end and event_type."""
    rd = round_decimals
    ts = round(float(t_start), rd) if t_start is not None and not pd.isna(t_start) else None
    te = round(float(t_end), rd) if t_end is not None and not pd.isna(t_end) else None
    et = "" if event_type is None or pd.isna(event_type) else str(event_type)
    return (ts, te, et)


class VelocityEventDb:
    """Encapsulates CRUD and I/O for the velocity event database.

    Maintains a runtime cache of velocity events keyed by (path, roi).
    Persists to kym_event_db.csv in folder or file-list-from-CSV mode.
    """

    def __init__(
        self,
        db_path: Optional[Path],
        base_path_provider: Optional[Callable[[], Optional[Path]]] = None,
    ) -> None:
        """Initialize VelocityEventDb.

        Args:
            db_path: Path to kym_event_db.csv, or None if no DB (single-file, empty).
            base_path_provider: Optional callable returning base path for rel_path computation.
        """
        self._db_path: Optional[Path] = db_path
        self._base_path_provider: Optional[Callable[[], Optional[Path]]] = base_path_provider
        # Cache: list of row dicts (VelocityReportRow-like + _unique_row_id, rel_path)
        self._cache: List[dict] = []

    def get_db_path(self) -> Optional[Path]:
        """Path to kym_event_db.csv. None if no DB."""
        return self._db_path

    def load(
        self,
        images_provider: Callable[[], Iterable["KymImage"]],
        progress_cb: Optional[ProgressCallback] = None,
        cancel_event: Optional[object] = None,
    ) -> None:
        """Load velocity event DB from CSV if it exists; rebuild if missing or stale."""
        if self._db_path is None:
            return

        load_path = get_hidden_cache_path(self._db_path)

        need_rebuild = False
        rebuild_reason = ""

        if load_path.exists():
            try:
                df = pd.read_csv(load_path)
                missing = _EXPECTED_COLS - set(df.columns)
                if missing:
                    need_rebuild = True
                    rebuild_reason = "schema was stale"
                else:
                    self._cache = df.to_dict("records")
                    # Resolve rel_path to full path if base available
                    base = self._get_base_from_images(images_provider)
                    if base is not None:
                        for row in self._cache:
                            path_val = row.get("path")
                            rel = row.get("rel_path")
                            if (pd.isna(path_val) or path_val is None or path_val == "") and rel:
                                try:
                                    row["path"] = str(Path(base) / str(rel))
                                except Exception:
                                    pass
                    # Check staleness: compare cache vs current images
                    if self._is_cache_stale(images_provider):
                        need_rebuild = True
                        rebuild_reason = "cache was stale vs images"
            except Exception as e:
                logger.error("Failed to load velocity event DB from %s: %s", load_path, e)
                need_rebuild = True
                rebuild_reason = "load failed"
        else:
            need_rebuild = True
            rebuild_reason = "no DB file"

        if need_rebuild:
            images = list(images_provider())
            n = len(images)
            if progress_cb is not None:
                progress_cb(
                    ProgressMessage(
                        phase="rebuild_velocity_event_db",
                        done=0,
                        total=n,
                        detail="Rebuilding velocity event database...",
                    )
                )
            self.rebuild_from_images(
                images_provider=images_provider,
                progress_cb=progress_cb,
                cancel_event=cancel_event,
            )
            if cancel_event is not None and getattr(cancel_event, "is_set", lambda: False)():
                return

            # Persist to both visible and hidden CSV so they exist after first run or recovery.
            self.save()
            logger.info("Velocity event DB load complete (rebuilt from images: %s)", rebuild_reason)

            if progress_cb is not None and n > 0:
                progress_cb(
                    ProgressMessage(
                        phase="rebuild_velocity_event_db",
                        done=n,
                        total=n,
                        detail="Done",
                    )
                )

    def _get_base_from_images(
        self,
        images_provider: Callable[[], Iterable["KymImage"]],
    ) -> Optional[Path]:
        """Infer base path from images (common parent or first parent)."""
        images = list(images_provider())
        if not images:
            return None
        paths = []
        for img in images:
            if img.path is not None:
                paths.append(Path(img.path).resolve())
        if not paths:
            return None
        if len(paths) == 1:
            return paths[0].parent
        try:
            # return Path(paths[0].commonpath(paths))
            return Path(os.path.commonpath([str(p) for p in paths]))
        except (ValueError, TypeError):
            return paths[0].parent

    def _is_cache_stale(
        self,
        images_provider: Callable[[], Iterable["KymImage"]],
    ) -> bool:
        """Return True if cache does not match current KymAnalysis state for any (path, roi)."""
        images = list(images_provider())
        # Build current state: (path, roi_id) -> list of (t_start, t_end, event_type) for comparison
        current: Dict[tuple, List[tuple]] = {}
        for img in images:
            if img.path is None:
                continue
            path_str = str(img.path)
            try:
                ka = img.get_kym_analysis()
                for roi_id in img.rois.get_roi_ids():
                    events = ka.get_velocity_events(roi_id)
                    if events is None:
                        events = []
                    key = (path_str, roi_id)
                    current[key] = [
                        (e.t_start, e.t_end, getattr(e.event_type, "value", e.event_type))
                        for e in events
                    ]
            except Exception as e:
                logger.error("Failed to get velocity events for %s: %s", path_str, e)
                continue

        # Build cache state
        cache_by_key: Dict[tuple, List[tuple]] = {}
        for row in self._cache:
            path_val = row.get("path")
            roi_id = row.get("roi_id")
            if path_val is None or pd.isna(path_val) or roi_id is None:
                continue
            key = (str(path_val), int(roi_id))
            if key not in cache_by_key:
                cache_by_key[key] = []
            t_start = row.get("t_start")
            t_end = row.get("t_end")
            event_type = row.get("event_type")
            cache_by_key[key].append((t_start, t_end, event_type))

        # Compare: normalize both sides before comparison.
        # Sort key must handle None in t_start/t_end (from empty CSV cells) to avoid:
        # TypeError: '<' not supported between instances of 'float' and 'NoneType'
        def _sort_key(tup: tuple) -> tuple:
            ts, te, _ = tup
            return (
                ts if ts is not None else float("-inf"),
                te if te is not None else float("-inf"),
            )

        all_keys = set(current.keys()) | set(cache_by_key.keys())
        for key in all_keys:
            curr_list = current.get(key, [])
            cache_list = cache_by_key.get(key, [])
            if len(curr_list) != len(cache_list):
                return True
            curr_norm = [_norm_event_tuple(x[0], x[1], x[2]) for x in curr_list]
            cache_norm = [_norm_event_tuple(x[0], x[1], x[2]) for x in cache_list]
            curr_sorted = sorted(curr_norm, key=_sort_key)
            cache_sorted = sorted(cache_norm, key=_sort_key)
            if curr_sorted != cache_sorted:
                # logger.debug("STALE")
                # logger.debug("  curr_sorted:")
                # for _i in curr_sorted:
                #     print(_i)
                # logger.debug("  cache_sorted:")
                # for _i in cache_sorted:
                #     print(_i)
                return True
        return False

    def save(self) -> bool:
        """Persist cache to CSV. Returns True if saved, False if no DB path.

        When cache is empty, writes a CSV with correct column headers and 0 rows
        so the file reflects that all events were deleted (e.g. after remove-all script).
        """
        if self._db_path is None:
            return False
        try:
            if self._cache:
                df = pd.DataFrame(self._cache)
            else:
                col_order = [f.name for f in fields(VelocityEventReport)]
                df = pd.DataFrame(columns=col_order)
            logger.info("Saving velocity event DB to: %s", self._db_path)
            df.to_csv(self._db_path, index=False)

            # Also save a hidden copy under .kymflow_hidden for robust loading
            hidden_dir = ensure_hidden_cache_dir(self._db_path)
            hidden_path = hidden_dir / self._db_path.name
            df.to_csv(hidden_path, index=False)
            logger.warning("Saving velocity event DB to hidden path: %s", hidden_path)

            return True
        except Exception as e:
            logger.error("Failed to save velocity event DB: %s", e)
            return False

    def update_from_image(self, kym_image: "KymImage") -> None:
        """Replace all entries for (path, roi) in cache with current KymAnalysis data.

        In-memory only. Does NOT persist. Call save() or update_from_image_and_persist() to persist.
        """
        if kym_image.path is None:
            return
        path_str = str(kym_image.path)
        base = self._base_path_provider() if self._base_path_provider else None
        if base is None:
            base = self._get_base_from_images(lambda: [kym_image])
        rel_path = None
        if base is not None and kym_image.path is not None:
            try:
                base_res = Path(base).resolve()
                path_res = Path(kym_image.path).resolve()
                rel_path = str(path_res.relative_to(base_res))
            except ValueError as e:
                logger.error(f"Failed to get relative path for image {kym_image.path}, e is: {e}")
                rel_path = Path(kym_image.path).name

        parent_folder = None
        grandparent_folder = None
        if kym_image.path is not None:
            path_obj = Path(kym_image.path)
            if path_obj.parent:
                parent_folder = path_obj.parent.name
                if path_obj.parent.parent:
                    grandparent_folder = path_obj.parent.parent.name

        try:
            ka = kym_image.get_kym_analysis()
            accepted = ka.get_accepted()
            rows: List[dict] = []
            for roi_id in kym_image.rois.get_roi_ids():
                roi = kym_image.rois.get(roi_id)
                channel = roi.channel if roi is not None else None
                events = ka.get_velocity_events(roi_id)
                if events is None:
                    events = []
                for idx, event in enumerate(events):
                    report = VelocityEventReport.from_velocity_event(
                        event,
                        path_str,
                        roi_id,
                        idx,
                        rel_path=rel_path,
                        parent_folder=parent_folder,
                        grandparent_folder=grandparent_folder,
                        accepted=accepted,
                        channel=channel,
                    )
                    rows.append(report.to_dict())

            # Remove existing entries for this path
            self._cache = [r for r in self._cache if r.get("path") != path_str]
            self._cache.extend(rows)
        except Exception as e:
            logger.error("Failed to update velocity event cache for %s: %s", path_str, e)

    def update_from_image_and_persist(self, kym_image: "KymImage") -> None:
        """Update cache from image and persist to CSV."""
        self.update_from_image(kym_image)
        self.save()

    def rebuild_from_images(
        self,
        images_provider: Callable[[], Iterable["KymImage"]],
        progress_cb: Optional[ProgressCallback] = None,
        cancel_event: Optional[object] = None,
    ) -> None:
        """Rebuild cache from all images. Replaces entire cache."""
        self._cache = []
        images = list(images_provider())
        n = len(images)
        progress_every = max(1, n // 20) if n > 0 else 1

        for i, image in enumerate(images):
            if cancel_event is not None and getattr(cancel_event, "is_set", lambda: False)():
                raise CancelledError("Cancelled during velocity event DB rebuild")
            self.update_from_image(image)
            if progress_cb is not None and n > 0:
                if (i + 1) % progress_every == 0 or (i + 1) == n:
                    progress_cb(
                        ProgressMessage(
                            phase="rebuild_velocity_event_db",
                            done=i + 1,
                            total=n,
                            detail=f"{i + 1}/{n}",
                        )
                    )

    def get_all_events(self) -> List[dict]:
        """Return all cached events as list of row dicts (VelocityReportRow-like + _unique_row_id)."""
        return list(self._cache)

    def get_df(self) -> pd.DataFrame:
        """Return cached events as DataFrame. Columns include _unique_row_id, path, roi_id, etc."""
        if not self._cache:
            return pd.DataFrame()
        return pd.DataFrame(self._cache)
