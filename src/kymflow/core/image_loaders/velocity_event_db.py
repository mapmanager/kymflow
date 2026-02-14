"""Velocity event database for KymImageList.

Maintains a denormalized cache of VelocityEvent across all (path, roi) in a KymImageList.
Persisted as kym_event_db.csv. Follows the same patterns as radon_report_db but encapsulates
all CRUD and I/O in this class.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict, Iterable, List, Optional

import pandas as pd

from kymflow.core.utils.logging import get_logger
from kymflow.core.utils.progress import CancelledError, ProgressCallback, ProgressMessage

if TYPE_CHECKING:
    from kymflow.core.image_loaders.kym_image import KymImage

logger = get_logger(__name__)

# Required columns for CSV schema validation (from VelocityEvent + identity)
_EXPECTED_COLS = {
    "kym_event_id",
    "path",
    "roi_id",
    "rel_path",
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
}


def _kym_event_id(path: str, roi_id: int, event_idx: int) -> str:
    """Generate kym_event_id: path|roi_id|event_idx."""
    return f"{path}|{roi_id}|{event_idx}"


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
        # Cache: list of row dicts (VelocityReportRow-like + kym_event_id, rel_path)
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

        need_rebuild = False
        rebuild_reason = ""

        if self._db_path.exists():
            try:
                df = pd.read_csv(self._db_path)
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
                logger.warning("Failed to load velocity event DB from %s: %s", self._db_path, e)
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
            return Path(paths[0].commonpath(paths))
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
                        (e.t_start, e.t_end or e.t_start, e.event_type) for e in events
                    ]
            except Exception as e:
                logger.warning("Failed to get velocity events for %s: %s", path_str, e)
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
            t_end = row.get("t_end", t_start)
            event_type = row.get("event_type", "")
            cache_by_key[key].append((t_start, t_end, event_type))

        # Compare
        all_keys = set(current.keys()) | set(cache_by_key.keys())
        for key in all_keys:
            curr_list = current.get(key, [])
            cache_list = cache_by_key.get(key, [])
            if len(curr_list) != len(cache_list):
                return True
            curr_sorted = sorted(curr_list, key=lambda x: (x[0], x[1]))
            cache_sorted = sorted(cache_list, key=lambda x: (x[0], x[1]))
            if curr_sorted != cache_sorted:
                return True
        return False

    def save(self) -> bool:
        """Persist cache to CSV. Returns True if saved, False if no DB path."""
        if self._db_path is None:
            return False
        if not self._cache:
            return False
        try:
            df = pd.DataFrame(self._cache)
            logger.info("Saving velocity event DB to: %s", self._db_path)
            df.to_csv(self._db_path, index=False)
            return True
        except Exception as e:
            logger.warning("Failed to save velocity event DB: %s", e)
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
            except ValueError:
                rel_path = Path(kym_image.path).name

        try:
            ka = kym_image.get_kym_analysis()
            rows: List[dict] = []
            for roi_id in kym_image.rois.get_roi_ids():
                events = ka.get_velocity_events(roi_id)
                if events is None:
                    events = []
                for idx, event in enumerate(events):
                    kym_event_id = _kym_event_id(path_str, roi_id, idx)
                    d = event.to_dict(round_decimals=3)
                    row = {
                        "kym_event_id": kym_event_id,
                        "path": path_str,
                        "roi_id": roi_id,
                        "rel_path": rel_path,
                        **d,
                    }
                    rows.append(row)

            # Remove existing entries for this path
            self._cache = [r for r in self._cache if r.get("path") != path_str]
            self._cache.extend(rows)
        except Exception as e:
            logger.warning("Failed to update velocity event cache for %s: %s", path_str, e)

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
        """Return all cached events as list of row dicts (VelocityReportRow-like + kym_event_id)."""
        return list(self._cache)

    def get_df(self) -> pd.DataFrame:
        """Return cached events as DataFrame. Columns include kym_event_id, path, roi_id, etc."""
        if not self._cache:
            return pd.DataFrame()
        return pd.DataFrame(self._cache)
