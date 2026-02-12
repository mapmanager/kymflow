# src/kymflow/core/user_config.py
"""
Per-user config persistence for kymflow (platformdirs + JSON).

Persisted items (schema v3):
- recent_folders: list[{path, depth}]  (folders only, each path has an associated folder_depth)
- recent_files: list[{path}]          (files only, no depth)
- last_path: {path, depth}             (most recently opened path, file or folder)
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
SCHEMA_VERSION: int = 3

# Defaults
DEFAULT_FOLDER_DEPTH: int = 1
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


def _path_to_display(path: str | Path) -> str:
    """Convert full path to display-friendly ~ notation.
    
    If the path is under the user's home directory, replaces the home directory
    portion with ~. If the path is outside the home directory, returns it unchanged.
    Works cross-platform (macOS, Linux, Windows).
    
    Args:
        path: Full path to convert.
    
    Returns:
        Path with home directory replaced by ~, or original path if outside home.
    
    Examples:
        /Users/username/Dropbox/file.tif -> ~/Dropbox/file.tif
        /usr/local/bin -> /usr/local/bin (unchanged, outside home)
        C:\\Users\\username\\Documents -> ~\\Documents (Windows)
    """
    try:
        path_obj = Path(path).expanduser()
        home = Path.home()
        
        # Try to make paths relative to home directory
        try:
            # Use resolve() to handle symlinks and normalize paths
            path_resolved = path_obj.resolve(strict=False)
            home_resolved = home.resolve(strict=False)
            
            # Check if path is under home directory
            try:
                # Check if resolved path is under resolved home
                path_resolved.relative_to(home_resolved)
                # If we get here, path is under home directory
                # Use path_obj (not resolved) to preserve original format
                # but still get relative path correctly
                relative_original = Path(path).expanduser().relative_to(home)
                return str(Path("~") / relative_original)
            except ValueError:
                # Path is not under home directory, return as-is
                return str(path_obj)
        except Exception:
            # If resolve fails, try simpler comparison
            try:
                path_str = str(path_obj)
                home_str = str(home)
                if path_str.startswith(home_str):
                    # Replace home directory with ~
                    remainder = path_str[len(home_str):].lstrip("/").lstrip("\\")
                    if remainder:
                        return str(Path("~") / remainder)
                    else:
                        return "~"
                return str(path_obj)
            except Exception:
                # Fallback: return original path as string
                return str(path)
    except Exception:
        # If anything fails, return original path as string
        return str(path)


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
class RecentCsv:
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
    recent_csvs: List[RecentCsv] = field(default_factory=list)
    last_path: LastPath = field(default_factory=LastPath)

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

        # recent_csvs
        recent_csvs_raw = d.get("recent_csvs", [])
        recent_csvs: List[RecentCsv] = []
        if isinstance(recent_csvs_raw, list):
            for item in recent_csvs_raw:
                if not isinstance(item, dict):
                    continue
                path = item.get("path")
                if isinstance(path, str) and path.strip():
                    recent_csvs.append(RecentCsv(path=path))

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
            recent_csvs=recent_csvs,
            last_path=LastPath(path=last_path, depth=last_depth),
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
        for rf in data.recent_folders:
            p = _normalize_folder_path(rf.path)
            if p in seen_folders:
                continue
            seen_folders.add(p)
            try:
                path_obj = Path(p).expanduser()
                if not path_obj.exists() or not path_obj.is_dir():
                    logger.warning("Removed from recent path (folder): %s", p)
                    continue
            except Exception:
                logger.warning("Removed from recent path (folder): %s", p)
                continue
            norm_recent_folders.append(RecentFolder(path=p, depth=int(rf.depth)))
        data.recent_folders = norm_recent_folders

        # Normalize recent_files (validate existence, dedupe, limit)
        norm_recent_files: List[RecentFile] = []
        seen_files: set[str] = set()
        for rf in data.recent_files:
            p = _normalize_folder_path(rf.path)
            if p in seen_files:
                continue
            seen_files.add(p)
            try:
                path_obj = Path(p).expanduser()
                if not path_obj.exists() or not path_obj.is_file():
                    logger.warning("Removed from recent path (file tif): %s", p)
                    continue
            except Exception:
                logger.warning("Removed from recent path (file tif): %s", p)
                continue
            norm_recent_files.append(RecentFile(path=p))
        data.recent_files = norm_recent_files

        # Normalize recent_csvs (validate existence, dedupe, limit)
        norm_recent_csvs: List[RecentCsv] = []
        seen_csvs: set[str] = set()
        for rc in data.recent_csvs:
            p = _normalize_folder_path(rc.path)
            if p in seen_csvs:
                continue
            seen_csvs.add(p)
            try:
                path_obj = Path(p).expanduser()
                if not path_obj.exists() or not path_obj.is_file() or path_obj.suffix.lower() != ".csv":
                    logger.warning("Removed from recent path (csv): %s", p)
                    continue
            except Exception:
                logger.warning("Removed from recent path (csv): %s", p)
                continue
            norm_recent_csvs.append(RecentCsv(path=p))
        data.recent_csvs = norm_recent_csvs

        # Apply MAX_RECENTS limit to combined total
        combined = len(data.recent_folders) + len(data.recent_files) + len(data.recent_csvs)
        if combined > MAX_RECENTS:
            # Trim from oldest (end of lists)
            excess = combined - MAX_RECENTS
            if len(data.recent_folders) > 0:
                folders_to_remove = min(excess, len(data.recent_folders))
                data.recent_folders = data.recent_folders[:-folders_to_remove]
                excess -= folders_to_remove
            if excess > 0 and len(data.recent_files) > 0:
                files_to_remove = min(excess, len(data.recent_files))
                data.recent_files = data.recent_files[:-files_to_remove]
                excess -= files_to_remove
            if excess > 0 and len(data.recent_csvs) > 0:
                csvs_to_remove = min(excess, len(data.recent_csvs))
                data.recent_csvs = data.recent_csvs[:-csvs_to_remove]

        # Normalize last_path
        if data.last_path.path.strip():
            p = _normalize_folder_path(data.last_path.path)
            try:
                path_obj = Path(p).expanduser()
                if not path_obj.exists():
                    logger.warning("Removed missing last_path: %s", p)
                    data.last_path = LastPath(path="", depth=DEFAULT_FOLDER_DEPTH)
                else:
                    data.last_path.path = p
                    try:
                        data.last_path.depth = int(data.last_path.depth)
                    except Exception:
                        data.last_path.depth = DEFAULT_FOLDER_DEPTH
            except Exception:
                logger.warning("Removed invalid last_path: %s", p)
                data.last_path = LastPath(path="", depth=DEFAULT_FOLDER_DEPTH)

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
        Add/update a path (folder, file, or CSV) in the recents list.
        - CSV files go to recent_csvs (depth ignored, stored as 0)
        - Other files go to recent_files (depth ignored, stored as 0)
        - Folders go to recent_folders (with depth)
        Also updates last_path.
        """
        p = _normalize_folder_path(path)
        path_obj = Path(p)
        depth_int = int(depth)

        # Check if CSV file
        is_csv = path_obj.is_file() and path_obj.suffix.lower() == '.csv'
        
        if is_csv:
            # CSV: delegate to push_recent_csv
            self.push_recent_csv(path)
            return

        # Determine if path is file or folder
        is_file = path_obj.is_file()
        
        if is_file:
            # File: add to recent_files, remove from all lists first
            self.data.recent_files = [rf for rf in self.data.recent_files if _normalize_folder_path(rf.path) != p]
            self.data.recent_folders = [rf for rf in self.data.recent_folders if _normalize_folder_path(rf.path) != p]
            self.data.recent_csvs = [rc for rc in self.data.recent_csvs if _normalize_folder_path(rc.path) != p]
            self.data.recent_files.append(RecentFile(path=p))
            # Update last_path with depth=0 for files
            self.data.last_path = LastPath(path=p, depth=0)
        else:
            # Folder: add to recent_folders, remove from all lists first
            self.data.recent_folders = [rf for rf in self.data.recent_folders if _normalize_folder_path(rf.path) != p]
            self.data.recent_files = [rf for rf in self.data.recent_files if _normalize_folder_path(rf.path) != p]
            self.data.recent_csvs = [rc for rc in self.data.recent_csvs if _normalize_folder_path(rc.path) != p]
            self.data.recent_folders.append(RecentFolder(path=p, depth=depth_int))
            # Update last_path with actual depth
            self.data.last_path = LastPath(path=p, depth=depth_int)

        # Apply MAX_RECENTS limit to combined total
        combined = len(self.data.recent_folders) + len(self.data.recent_files) + len(self.data.recent_csvs)
        if combined > MAX_RECENTS:
            excess = combined - MAX_RECENTS
            # Trim from oldest (beginning of lists, since we append new items to end)
            if len(self.data.recent_folders) > 0:
                folders_to_remove = min(excess, len(self.data.recent_folders))
                self.data.recent_folders = self.data.recent_folders[folders_to_remove:]
                excess -= folders_to_remove
            if excess > 0 and len(self.data.recent_files) > 0:
                files_to_remove = min(excess, len(self.data.recent_files))
                self.data.recent_files = self.data.recent_files[files_to_remove:]
                excess -= files_to_remove
            if excess > 0 and len(self.data.recent_csvs) > 0:
                csvs_to_remove = min(excess, len(self.data.recent_csvs))
                self.data.recent_csvs = self.data.recent_csvs[csvs_to_remove:]

    def push_recent_csv(self, csv_path: str | Path) -> None:
        """
        Add/update a CSV file in the recents list.
        Also updates last_path.
        """
        p = _normalize_folder_path(csv_path)
        
        # Remove from all lists first
        self.data.recent_csvs = [rc for rc in self.data.recent_csvs if _normalize_folder_path(rc.path) != p]
        self.data.recent_folders = [rf for rf in self.data.recent_folders if _normalize_folder_path(rf.path) != p]
        self.data.recent_files = [rf for rf in self.data.recent_files if _normalize_folder_path(rf.path) != p]
        
        # Append to end (maintains ordering, newest at end)
        self.data.recent_csvs.append(RecentCsv(path=p))
        
        # Update last_path with depth=0 for CSVs (like files)
        self.data.last_path = LastPath(path=p, depth=0)
        
        # Apply MAX_RECENTS limit to combined total
        combined = len(self.data.recent_folders) + len(self.data.recent_files) + len(self.data.recent_csvs)
        if combined > MAX_RECENTS:
            excess = combined - MAX_RECENTS
            # Trim from oldest (beginning of lists, since we append new items to end)
            if len(self.data.recent_folders) > 0:
                folders_to_remove = min(excess, len(self.data.recent_folders))
                self.data.recent_folders = self.data.recent_folders[folders_to_remove:]
                excess -= folders_to_remove
            if excess > 0 and len(self.data.recent_files) > 0:
                files_to_remove = min(excess, len(self.data.recent_files))
                self.data.recent_files = self.data.recent_files[files_to_remove:]
                excess -= files_to_remove
            if excess > 0 and len(self.data.recent_csvs) > 0:
                csvs_to_remove = min(excess, len(self.data.recent_csvs))
                self.data.recent_csvs = self.data.recent_csvs[csvs_to_remove:]

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

        # Prune missing CSVs
        kept_csvs: List[RecentCsv] = []
        for rc in self.data.recent_csvs:
            try:
                path_obj = Path(rc.path).expanduser()
                exists = path_obj.exists() and path_obj.is_file() and path_obj.suffix.lower() == '.csv'
            except Exception:
                exists = False
            if exists:
                kept_csvs.append(rc)
            else:
                removed += 1
        if kept_csvs != self.data.recent_csvs:
            self.data.recent_csvs = kept_csvs

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

    def get_recent_csvs(self) -> List[str]:
        """Return recent CSV files as list of paths."""
        return [rc.path for rc in self.data.recent_csvs]
    
    def get_recent_folders_display(self) -> List[Tuple[str, int]]:
        """Return recent folders with display-friendly paths (using ~ notation).
        
        Returns:
            List of (display_path, depth) tuples where display_path uses ~ notation
            for paths under the home directory.
        """
        return [(_path_to_display(rf.path), int(rf.depth)) for rf in self.data.recent_folders]

    def get_recent_files_display(self) -> List[str]:
        """Return recent files with display-friendly paths (using ~ notation).
        
        Returns:
            List of display paths where paths under the home directory use ~ notation.
        """
        return [_path_to_display(rf.path) for rf in self.data.recent_files]

    def get_recent_csvs_display(self) -> List[str]:
        """Return recent CSV files with display-friendly paths (using ~ notation).
        
        Returns:
            List of display paths where paths under the home directory use ~ notation.
        """
        return [_path_to_display(rc.path) for rc in self.data.recent_csvs]

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