# src/kymflow/core/user_config.py
"""
Per-user config persistence for kymflow (platformdirs + JSON).

Persisted items (schema v1):
- recent_folders: list[{path, depth}]  (each path has an associated folder_depth)
- last_folder: {path, depth}
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
SCHEMA_VERSION: int = 1

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
class LastFolder:
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
    last_folder: LastFolder = field(default_factory=LastFolder)

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

        # last_folder
        last_raw = d.get("last_folder", {})
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
            last_folder=LastFolder(path=last_path, depth=last_depth),
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
        # Normalize recent (dedupe, limit)
        norm_recent: List[RecentFolder] = []
        seen: set[str] = set()
        for rf in data.recent_folders:
            p = _normalize_folder_path(rf.path)
            if p in seen:
                continue
            seen.add(p)
            norm_recent.append(RecentFolder(path=p, depth=int(rf.depth)))
        data.recent_folders = norm_recent[:MAX_RECENTS]

        # Normalize last
        if data.last_folder.path.strip():
            data.last_folder.path = _normalize_folder_path(data.last_folder.path)
            try:
                data.last_folder.depth = int(data.last_folder.depth)
            except Exception:
                data.last_folder.depth = DEFAULT_FOLDER_DEPTH

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
        # logger.info(f'payload: {payload}')
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
    def push_recent_folder(self, folder_path: str | Path, *, depth: int) -> None:
        """
        Add/update a folder in the recents list, with associated depth.
        Also updates last_folder.
        """
        p = _normalize_folder_path(folder_path)
        depth_int = int(depth)

        self.data.last_folder = LastFolder(path=p, depth=depth_int)

        # Remove existing occurrence, insert at front, trim.
        self.data.recent_folders = [rf for rf in self.data.recent_folders if _normalize_folder_path(rf.path) != p]
        self.data.recent_folders.insert(0, RecentFolder(path=p, depth=depth_int))
        self.data.recent_folders = self.data.recent_folders[:MAX_RECENTS]

    def prune_missing_folders(self) -> int:
        """Remove recent/last folders that no longer exist on disk."""
        removed = 0
        kept: List[RecentFolder] = []
        for rf in self.data.recent_folders:
            try:
                exists = Path(rf.path).expanduser().exists()
            except Exception:
                exists = False
            if exists:
                kept.append(rf)
            else:
                removed += 1
        if removed:
            self.data.recent_folders = kept

        last_path = self.data.last_folder.path
        if last_path:
            try:
                last_exists = Path(last_path).expanduser().exists()
            except Exception:
                last_exists = False
            if not last_exists:
                self.data.last_folder = LastFolder(path="", depth=DEFAULT_FOLDER_DEPTH)
                removed += 1

        return removed

    def get_recent_folders(self) -> List[Tuple[str, int]]:
        """Return recent folders as list of (path, depth)."""
        return [(rf.path, int(rf.depth)) for rf in self.data.recent_folders]

    def get_last_folder(self) -> Tuple[str, int]:
        """Return (last_path, last_depth)."""
        return (self.data.last_folder.path, int(self.data.last_folder.depth))

    def get_depth_for_folder(self, folder_path: str | Path) -> int:
        """
        Return the remembered depth for a folder if present in recents,
        otherwise return default_folder_depth.
        """
        p = _normalize_folder_path(folder_path)
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

    def set_last_folder(self, folder_path: str | Path, *, depth: int) -> None:
        """Update last_folder without reordering recents."""
        p = _normalize_folder_path(folder_path)
        self.data.last_folder = LastFolder(path=p, depth=int(depth))

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
