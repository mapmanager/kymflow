# src/kymflow/core/user_config.py
"""
Per-user config persistence for kymflow (platformdirs + JSON).

Persisted items (schema v2):
- recent_folders: list[{path, depth}]  (folders only, each path has an associated folder_depth)
- recent_files: list[{path}]          (files only, no depth)
- last_path: {path, depth}             (most recently opened path, file or folder)
- window_rect: [x, y, w, h]            (native window geometry)
- default_folder_depth: int            (fallback for unseen folders)

Behavior:
- If config file missing or unreadable -> defaults are used
- If schema_version mismatches:
  - default: reset to defaults (safe for distributed desktop apps)
  - optional: keep loaded but update version
- Optional "create_if_missing" flag to write defaults on first run

Design:
- UserConfigData dataclass holds JSON-friendly data (dot access)
- UserConfig manager provides explicit API for load/save and common operations
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from platformdirs import user_config_dir

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

# Increment when you make a breaking change to the on-disk JSON schema.
SCHEMA_VERSION: int = 2

# Defaults
DEFAULT_FOLDER_DEPTH: int = 1
DEFAULT_WINDOW_RECT: List[int] = [100, 100, 1200, 800]  # x, y, w, h
DEFAULT_HOME_FILE_PLOT_SPLITTER: float = 15.0
DEFAULT_HOME_PLOT_EVENT_SPLITTER: float = 50.0
HOME_FILE_PLOT_SPLITTER_RANGE: tuple[float, float] = (0.0, 60.0)
HOME_PLOT_EVENT_SPLITTER_RANGE: tuple[float, float] = (30.0, 90.0)
MAX_RECENTS: int = 15


def _normalize_folder_path(path: str | Path) -> str:
    """Normalize folder path string for storage and comparisons."""
    p = Path(path).expanduser()
    try:
        # resolve() can fail for missing mount points; strict=False keeps it safe.
        p = p.resolve(strict=False)
    except Exception:
        pass
    return str(p)


def _clamp_float(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


@dataclass
class RecentFolder:
    path: str
    depth: int = DEFAULT_FOLDER_DEPTH


@dataclass
class RecentFile:
    path: str


@dataclass
class LastPath:
    path: str = ""
    depth: int = DEFAULT_FOLDER_DEPTH


@dataclass
class UserConfigData:
    """
    JSON-serializable config payload.

    Keep fields JSON-friendly:
    - primitives, lists, dicts
    - nested dataclasses are handled by asdict()
    """
    schema_version: int = SCHEMA_VERSION

    recent_folders: List[RecentFolder] = field(default_factory=list)
    recent_files: List[RecentFile] = field(default_factory=list)
    last_path: LastPath = field(default_factory=LastPath)

    # Native window geometry: [x, y, w, h]
    window_rect: List[int] = field(default_factory=lambda: list(DEFAULT_WINDOW_RECT))

    # Fallback depth when a folder hasn't been seen before.
    default_folder_depth: int = DEFAULT_FOLDER_DEPTH

    # Home page splitter positions (percentages).
    home_file_plot_splitter: float = DEFAULT_HOME_FILE_PLOT_SPLITTER
    home_plot_event_splitter: float = DEFAULT_HOME_PLOT_EVENT_SPLITTER

    def to_json_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json_dict(cls, d: Dict[str, Any]) -> "UserConfigData":
        """
        Tolerant loader:
        - ignores unknown keys
        - tolerates partially missing nested structures
        """
        schema_version = int(d.get("schema_version", -1))

        # recent_folders
        recent_raw = d.get("recent_folders", [])
        recent_folders: List[RecentFolder] = []
        if isinstance(recent_raw, list):
            for item in recent_raw:
                if not isinstance(item, dict):
                    continue
                path = item.get("path")
                depth = item.get("depth", DEFAULT_FOLDER_DEPTH)
                if isinstance(path, str) and path.strip():
                    try:
                        depth_int = int(depth)
                    except Exception:
                        depth_int = DEFAULT_FOLDER_DEPTH
                    recent_folders.append(RecentFolder(path=path, depth=depth_int))

        # recent_files
        recent_files_raw = d.get("recent_files", [])
        recent_files: List[RecentFile] = []
        if isinstance(recent_files_raw, list):
            for item in recent_files_raw:
                if not isinstance(item, dict):
                    continue
                path = item.get("path")
                if isinstance(path, str) and path.strip():
                    recent_files.append(RecentFile(path=path))

        # last_path (backward compatible with last_folder)
        last_raw = d.get("last_path", d.get("last_folder", {}))
        last_path = ""
        last_depth = DEFAULT_FOLDER_DEPTH
        if isinstance(last_raw, dict):
            lp = last_raw.get("path", "")
            ld = last_raw.get("depth", DEFAULT_FOLDER_DEPTH)
            if isinstance(lp, str):
                last_path = lp
            try:
                last_depth = int(ld)
            except Exception:
                last_depth = DEFAULT_FOLDER_DEPTH

        # window_rect
        rect = d.get("window_rect", list(DEFAULT_WINDOW_RECT))
        window_rect: List[int] = list(DEFAULT_WINDOW_RECT)
        if isinstance(rect, list) and len(rect) == 4:
            try:
                window_rect = [int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3])]
            except Exception:
                window_rect = list(DEFAULT_WINDOW_RECT)

        # default_folder_depth
        dfd = d.get("default_folder_depth", DEFAULT_FOLDER_DEPTH)
        try:
            default_folder_depth = int(dfd)
        except Exception:
            default_folder_depth = DEFAULT_FOLDER_DEPTH

        # home splitter positions
        hfps = d.get("home_file_plot_splitter", DEFAULT_HOME_FILE_PLOT_SPLITTER)
        hpse = d.get("home_plot_event_splitter", DEFAULT_HOME_PLOT_EVENT_SPLITTER)
        try:
            home_file_plot_splitter = float(hfps)
        except Exception:
            home_file_plot_splitter = DEFAULT_HOME_FILE_PLOT_SPLITTER
        try:
            home_plot_event_splitter = float(hpse)
        except Exception:
            home_plot_event_splitter = DEFAULT_HOME_PLOT_EVENT_SPLITTER

        return cls(
            schema_version=schema_version,
            recent_folders=recent_folders,
            recent_files=recent_files,
            last_path=LastPath(path=last_path, depth=last_depth),
            window_rect=window_rect,
            default_folder_depth=default_folder_depth,
            home_file_plot_splitter=home_file_plot_splitter,
            home_plot_event_splitter=home_plot_event_splitter,
        )


class UserConfig:
    """
    Manager for loading/saving UserConfigData to disk.
    """

    def __init__(self, *, path: Path, data: Optional[UserConfigData] = None):
        self.path = path
        self.data = data if data is not None else UserConfigData()

    # -----------------------------
    # Construction / persistence
    # -----------------------------
    @staticmethod
    def default_config_path(
        app_name: str = "kymflow",
        filename: str = "user_config.json",
        app_author: str | None = None,
    ) -> Path:
        """
        Determine OS-appropriate per-user config path.

        macOS:   ~/Library/Application Support/kymflow/user_config.json
        Linux:   ~/.config/kymflow/user_config.json
        Windows: %APPDATA%\\kymflow\\user_config.json
        """
        d = Path(user_config_dir(app_name, app_author))
        d.mkdir(parents=True, exist_ok=True)
        return d / filename

    @classmethod
    def load(
        cls,
        *,
        config_path: Optional[Path] = None,
        app_name: str = "kymflow",
        filename: str = "user_config.json",
        app_author: str | None = None,
        schema_version: int = SCHEMA_VERSION,
        reset_on_version_mismatch: bool = True,
        create_if_missing: bool = False,
    ) -> "UserConfig":
        """
        Load config from disk.

        If file doesn't exist or is unreadable -> defaults.
        If schema mismatch:
          - reset_on_version_mismatch=True -> defaults
          - else -> keep loaded but overwrite schema_version

        If create_if_missing=True and file is missing -> immediately write defaults.
        """
        path = config_path or cls.default_config_path(app_name=app_name, filename=filename, app_author=app_author)
        default_data = UserConfigData(schema_version=schema_version)

        try:
            raw = path.read_text(encoding="utf-8")
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                return cls(path=path, data=default_data)

            loaded = UserConfigData.from_json_dict(parsed)

            if int(loaded.schema_version) != int(schema_version):
                if reset_on_version_mismatch:
                    cfg = cls(path=path, data=default_data)
                    # If you want "reset implies overwrite", caller can call cfg.save().
                    return cfg
                loaded.schema_version = int(schema_version)

            cls._normalize_loaded_paths(loaded)
            return cls(path=path, data=loaded)

        except FileNotFoundError:
            cfg = cls(path=path, data=default_data)
            if create_if_missing:
                cfg.save()
            return cfg
        except Exception:
            return cls(path=path, data=default_data)

    @staticmethod
    def _normalize_loaded_paths(data: UserConfigData) -> None:
        # Normalize recent_folders (validate existence, dedupe, limit)
        norm_recent_folders: List[RecentFolder] = []
        seen_folders: set[str] = set()
        removed_folders: List[str] = []
        for rf in data.recent_folders:
            p = _normalize_folder_path(rf.path)
            if p in seen_folders:
                continue
            seen_folders.add(p)
            # Check if path exists
            try:
                path_obj = Path(p).expanduser()
                if not path_obj.exists() or not path_obj.is_dir():
                    removed_folders.append(p)
                    continue
            except Exception:
                removed_folders.append(p)
                continue
            norm_recent_folders.append(RecentFolder(path=p, depth=int(rf.depth)))
        if removed_folders:
            logger.info(f"Removed {len(removed_folders)} missing folder paths from recent_folders")
        data.recent_folders = norm_recent_folders

        # Normalize recent_files (validate existence, dedupe, limit)
        norm_recent_files: List[RecentFile] = []
        seen_files: set[str] = set()
        removed_files: List[str] = []
        for rf in data.recent_files:
            p = _normalize_folder_path(rf.path)
            if p in seen_files:
                continue
            seen_files.add(p)
            # Check if path exists
            try:
                path_obj = Path(p).expanduser()
                if not path_obj.exists() or not path_obj.is_file():
                    removed_files.append(p)
                    continue
            except Exception:
                removed_files.append(p)
                continue
            norm_recent_files.append(RecentFile(path=p))
        if removed_files:
            logger.info(f"Removed {len(removed_files)} missing file paths from recent_files")
        data.recent_files = norm_recent_files

        # Apply MAX_RECENTS limit to combined total
        combined = len(data.recent_folders) + len(data.recent_files)
        if combined > MAX_RECENTS:
            # Trim from oldest (end of lists)
            excess = combined - MAX_RECENTS
            # Remove from folders first, then files
            if len(data.recent_folders) > 0:
                folders_to_remove = min(excess, len(data.recent_folders))
                data.recent_folders = data.recent_folders[:-folders_to_remove]
                excess -= folders_to_remove
            if excess > 0 and len(data.recent_files) > 0:
                files_to_remove = min(excess, len(data.recent_files))
                data.recent_files = data.recent_files[:-files_to_remove]

        # Normalize last_path
        if data.last_path.path.strip():
            p = _normalize_folder_path(data.last_path.path)
            # Check if path exists
            try:
                path_obj = Path(p).expanduser()
                if not path_obj.exists():
                    logger.info(f"Removed missing last_path: {p}")
                    data.last_path = LastPath(path="", depth=DEFAULT_FOLDER_DEPTH)
                else:
                    data.last_path.path = p
                    try:
                        data.last_path.depth = int(data.last_path.depth)
                    except Exception:
                        data.last_path.depth = DEFAULT_FOLDER_DEPTH
            except Exception:
                logger.info(f"Removed invalid last_path: {p}")
                data.last_path = LastPath(path="", depth=DEFAULT_FOLDER_DEPTH)

        # Normalize window rect
        if not (isinstance(data.window_rect, list) and len(data.window_rect) == 4):
            data.window_rect = list(DEFAULT_WINDOW_RECT)

        # Normalize home splitter positions
        try:
            data.home_file_plot_splitter = float(data.home_file_plot_splitter)
        except Exception:
            data.home_file_plot_splitter = DEFAULT_HOME_FILE_PLOT_SPLITTER
        try:
            data.home_plot_event_splitter = float(data.home_plot_event_splitter)
        except Exception:
            data.home_plot_event_splitter = DEFAULT_HOME_PLOT_EVENT_SPLITTER

        data.home_file_plot_splitter = _clamp_float(
            data.home_file_plot_splitter,
            HOME_FILE_PLOT_SPLITTER_RANGE[0],
            HOME_FILE_PLOT_SPLITTER_RANGE[1],
        )
        data.home_plot_event_splitter = _clamp_float(
            data.home_plot_event_splitter,
            HOME_PLOT_EVENT_SPLITTER_RANGE[0],
            HOME_PLOT_EVENT_SPLITTER_RANGE[1],
        )

    def save(self) -> None:
        """Write config to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = self.data.to_json_dict()
        logger.info('saving user_config to disk')
        logger.info(f'  path: {self.path}')
        from pprint import pprint
        pprint(payload, sort_dicts=False, indent=4)
        
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def ensure_exists(self) -> None:
        """Create the config file on disk if it doesn't exist (writes current data)."""
        if not self.path.exists():
            self.save()

    # -----------------------------
    # Public API: folders/recents
    # -----------------------------
    def push_recent_path(self, path: str | Path, *, depth: int) -> None:
        """
        Add/update a path (folder or file) in the recents list.
        - Files go to recent_files (depth ignored, stored as 0)
        - Folders go to recent_folders (with depth)
        Also updates last_path.
        """
        p = _normalize_folder_path(path)
        path_obj = Path(p)
        depth_int = int(depth)

        # Determine if path is file or folder
        is_file = path_obj.is_file()
        
        if is_file:
            # File: add to recent_files, remove from both lists first
            self.data.recent_files = [rf for rf in self.data.recent_files if _normalize_folder_path(rf.path) != p]
            self.data.recent_folders = [rf for rf in self.data.recent_folders if _normalize_folder_path(rf.path) != p]
            self.data.recent_files.insert(0, RecentFile(path=p))
            # Update last_path with depth=0 for files
            self.data.last_path = LastPath(path=p, depth=0)
        else:
            # Folder: add to recent_folders, remove from both lists first
            self.data.recent_folders = [rf for rf in self.data.recent_folders if _normalize_folder_path(rf.path) != p]
            self.data.recent_files = [rf for rf in self.data.recent_files if _normalize_folder_path(rf.path) != p]
            self.data.recent_folders.insert(0, RecentFolder(path=p, depth=depth_int))
            # Update last_path with actual depth
            self.data.last_path = LastPath(path=p, depth=depth_int)

        # Apply MAX_RECENTS limit to combined total
        combined = len(self.data.recent_folders) + len(self.data.recent_files)
        if combined > MAX_RECENTS:
            excess = combined - MAX_RECENTS
            # Trim from oldest (end of lists)
            if len(self.data.recent_folders) > 0:
                folders_to_remove = min(excess, len(self.data.recent_folders))
                self.data.recent_folders = self.data.recent_folders[:-folders_to_remove]
                excess -= folders_to_remove
            if excess > 0 and len(self.data.recent_files) > 0:
                files_to_remove = min(excess, len(self.data.recent_files))
                self.data.recent_files = self.data.recent_files[:-files_to_remove]

    def prune_missing_folders(self) -> int:
        """Remove recent/last paths that no longer exist on disk."""
        removed = 0
        
        # Prune missing folders
        kept_folders: List[RecentFolder] = []
        for rf in self.data.recent_folders:
            try:
                path_obj = Path(rf.path).expanduser()
                exists = path_obj.exists() and path_obj.is_dir()
            except Exception:
                exists = False
            if exists:
                kept_folders.append(rf)
            else:
                removed += 1
        if removed:
            self.data.recent_folders = kept_folders

        # Prune missing files
        kept_files: List[RecentFile] = []
        for rf in self.data.recent_files:
            try:
                path_obj = Path(rf.path).expanduser()
                exists = path_obj.exists() and path_obj.is_file()
            except Exception:
                exists = False
            if exists:
                kept_files.append(rf)
            else:
                removed += 1
        if kept_files != self.data.recent_files:
            self.data.recent_files = kept_files

        # Check last_path
        last_path = self.data.last_path.path
        if last_path:
            try:
                path_obj = Path(last_path).expanduser()
                last_exists = path_obj.exists()
            except Exception:
                last_exists = False
            if not last_exists:
                self.data.last_path = LastPath(path="", depth=DEFAULT_FOLDER_DEPTH)
                removed += 1

        return removed

    def get_recent_folders(self) -> List[Tuple[str, int]]:
        """Return recent folders as list of (path, depth)."""
        return [(rf.path, int(rf.depth)) for rf in self.data.recent_folders]

    def get_recent_files(self) -> List[str]:
        """Return recent files as list of paths."""
        return [rf.path for rf in self.data.recent_files]

    def get_last_path(self) -> Tuple[str, int]:
        """Return (last_path, last_depth)."""
        return (self.data.last_path.path, int(self.data.last_path.depth))

    def get_depth_for_folder(self, folder_path: str | Path) -> int:
        """
        Return the remembered depth for a folder if present in recents,
        otherwise return default_folder_depth.
        
        For file paths, returns 0 (sentinel value, depth is ignored when loading files).
        """
        p = _normalize_folder_path(folder_path)
        path_obj = Path(p)
        
        # If path is a file, return 0 (depth is ignored for files)
        if path_obj.is_file():
            return 0
        
        # For folders, look up depth in recents or use default
        for rf in self.data.recent_folders:
            if _normalize_folder_path(rf.path) == p:
                return int(rf.depth)
        return int(self.data.default_folder_depth)

    def get_home_splitter_positions(self) -> tuple[float, float]:
        """Return (file_plot_splitter, plot_event_splitter)."""
        return (
            float(self.data.home_file_plot_splitter),
            float(self.data.home_plot_event_splitter),
        )

    def set_home_splitter_positions(self, file_plot: float, plot_event: float) -> None:
        self.data.home_file_plot_splitter = _clamp_float(
            float(file_plot),
            HOME_FILE_PLOT_SPLITTER_RANGE[0],
            HOME_FILE_PLOT_SPLITTER_RANGE[1],
        )
        self.data.home_plot_event_splitter = _clamp_float(
            float(plot_event),
            HOME_PLOT_EVENT_SPLITTER_RANGE[0],
            HOME_PLOT_EVENT_SPLITTER_RANGE[1],
        )

    def set_default_folder_depth(self, depth: int) -> None:
        self.data.default_folder_depth = int(depth)

    def set_last_path(self, path: str | Path, *, depth: int) -> None:
        """Update last_path without reordering recents."""
        p = _normalize_folder_path(path)
        self.data.last_path = LastPath(path=p, depth=int(depth))

    def clear_recent_paths(self) -> None:
        """Clear all recent folders and files, and reset last_path."""
        self.data.recent_folders = []
        self.data.recent_files = []
        self.data.last_path = LastPath(path="", depth=DEFAULT_FOLDER_DEPTH)

    # -----------------------------
    # Public API: window geometry
    # -----------------------------
    def set_window_rect(self, x: int, y: int, w: int, h: int) -> None:
        self.data.window_rect = [int(x), int(y), int(w), int(h)]

    def get_window_rect(self) -> Tuple[int, int, int, int]:
        r = self.data.window_rect
        if not (isinstance(r, list) and len(r) == 4):
            return (DEFAULT_WINDOW_RECT[0], DEFAULT_WINDOW_RECT[1], DEFAULT_WINDOW_RECT[2], DEFAULT_WINDOW_RECT[3])
        try:
            return (int(r[0]), int(r[1]), int(r[2]), int(r[3]))
        except Exception:
            return (DEFAULT_WINDOW_RECT[0], DEFAULT_WINDOW_RECT[1], DEFAULT_WINDOW_RECT[2], DEFAULT_WINDOW_RECT[3])
