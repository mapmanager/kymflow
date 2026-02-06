# src/kymflow/gui_v2/app_config.py
"""
App-wide config persistence for kymflow (platformdirs + JSON).

Persisted items (schema v2):
- text_size: str                    (font size for UI controls)
- blinded: bool                     (blinded analysis mode)
- window_rect: List[int]            (native window geometry: [x, y, w, h])

Behavior:
- If config file missing or unreadable -> defaults are used
- If schema_version mismatches:
  - default: reset to defaults (safe for distributed desktop apps)
  - optional: keep loaded but update version
- Optional "create_if_missing" flag to write defaults on first run

Design:
- AppConfigData dataclass holds JSON-friendly data (dot access)
- AppConfig manager provides explicit API for load/save and common operations
- Field metadata drives GUI widget generation
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from platformdirs import user_config_dir

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

# Increment when you make a breaking change to the on-disk JSON schema.
SCHEMA_VERSION: int = 2

# Defaults
DEFAULT_TEXT_SIZE: str = "text-sm"
DEFAULT_BLINDED: bool = False
DEFAULT_WINDOW_RECT: List[int] = [100, 100, 1200, 800]  # x, y, w, h


@dataclass
class AppConfigData:
    """
    JSON-serializable config payload.

    Keep fields JSON-friendly:
    - primitives, lists, dicts
    - Field metadata is used to drive GUI widget generation
    """
    schema_version: int = SCHEMA_VERSION

    text_size: str = field(
        default=DEFAULT_TEXT_SIZE,
        metadata={
            "widget_type": "select",
            "label": "Text Size",
            "options": ["text-xs", "text-sm", "text-base", "text-lg"],
            "requires_restart": True,
        },
    )

    blinded: bool = field(
        default=DEFAULT_BLINDED,
        metadata={
            "widget_type": "checkbox",
            "label": "Blinded Analysis",
            "requires_restart": False,
        },
    )

    window_rect: List[int] = field(
        default_factory=lambda: list(DEFAULT_WINDOW_RECT),
        metadata={
            "widget_type": "display",
            "label": "Window Rect",
            "requires_restart": False,
        },
    )

    def to_json_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict, excluding metadata."""
        result = {}
        for f in fields(self):
            # Skip metadata when serializing
            if f.name == "schema_version":
                result[f.name] = getattr(self, f.name)
            else:
                result[f.name] = getattr(self, f.name)
        return result

    @classmethod
    def from_json_dict(cls, d: Dict[str, Any]) -> "AppConfigData":
        """
        Tolerant loader:
        - ignores unknown keys
        - tolerates partially missing values
        """
        schema_version = int(d.get("schema_version", -1))

        # text_size
        text_size_raw = d.get("text_size", DEFAULT_TEXT_SIZE)
        text_size = DEFAULT_TEXT_SIZE
        if isinstance(text_size_raw, str):
            # Validate against known options - must match the options in the field metadata
            valid_options = ["text-xs", "text-sm", "text-base", "text-lg"]
            if text_size_raw in valid_options:
                text_size = text_size_raw
            else:
                logger.warning(f"Invalid text_size '{text_size_raw}', using default '{DEFAULT_TEXT_SIZE}'")

        # blinded
        blinded_raw = d.get("blinded", DEFAULT_BLINDED)
        blinded = DEFAULT_BLINDED
        if isinstance(blinded_raw, bool):
            blinded = blinded_raw
        elif isinstance(blinded_raw, str):
            blinded = blinded_raw.lower() in ("true", "1", "yes", "on")
        elif isinstance(blinded_raw, (int, float)):
            blinded = bool(blinded_raw)

        # window_rect
        rect = d.get("window_rect", list(DEFAULT_WINDOW_RECT))
        window_rect: List[int] = list(DEFAULT_WINDOW_RECT)
        if isinstance(rect, list) and len(rect) == 4:
            try:
                window_rect = [int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3])]
            except Exception:
                window_rect = list(DEFAULT_WINDOW_RECT)

        return cls(
            schema_version=schema_version,
            text_size=text_size,
            blinded=blinded,
            window_rect=window_rect,
        )


class AppConfig:
    """
    Manager for loading/saving AppConfigData to disk.
    """

    def __init__(self, *, path: Path, data: Optional[AppConfigData] = None):
        self.path = path
        self.data = data if data is not None else AppConfigData()

    # -----------------------------
    # Construction / persistence
    # -----------------------------
    @staticmethod
    def default_config_path(
        app_name: str = "kymflow",
        filename: str = "app_config.json",
        app_author: str | None = None,
    ) -> Path:
        """
        Determine OS-appropriate per-user config path.

        macOS:   ~/Library/Application Support/kymflow/app_config.json
        Linux:   ~/.config/kymflow/app_config.json
        Windows: %APPDATA%\\kymflow\\app_config.json
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
        filename: str = "app_config.json",
        app_author: str | None = None,
        schema_version: int = SCHEMA_VERSION,
        reset_on_version_mismatch: bool = True,
        create_if_missing: bool = False,
    ) -> "AppConfig":
        """
        Load config from disk.

        If file doesn't exist or is unreadable -> defaults.
        If schema mismatch:
          - reset_on_version_mismatch=True -> defaults
          - else -> keep loaded but overwrite schema_version

        If create_if_missing=True and file is missing -> immediately write defaults.
        """
        path = config_path or cls.default_config_path(app_name=app_name, filename=filename, app_author=app_author)
        default_data = AppConfigData(schema_version=schema_version)

        try:
            raw = path.read_text(encoding="utf-8")
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                logger.warning(f"App config file at {path} does not contain a dict, using defaults")
                return cls(path=path, data=default_data)

            # logger.info(f"Loading app config from: {path}")
            # logger.debug(f"Loaded app config dict: {parsed}")

            loaded = AppConfigData.from_json_dict(parsed)

            if int(loaded.schema_version) != int(schema_version):
                if reset_on_version_mismatch:
                    logger.warning(
                        f"App config schema version mismatch: loaded={loaded.schema_version}, "
                        f"expected={schema_version}, resetting to defaults"
                    )
                    cfg = cls(path=path, data=default_data)
                    # If you want "reset implies overwrite", caller can call cfg.save().
                    return cfg
                loaded.schema_version = int(schema_version)

            cls._normalize_loaded_data(loaded)
            # logger.info(f"App config loaded successfully: {loaded.to_json_dict()}")
            return cls(path=path, data=loaded)

        except FileNotFoundError:
            logger.info(f"App config file not found at {path}, using defaults")
            cfg = cls(path=path, data=default_data)
            if create_if_missing:
                cfg.save()
            return cfg
        except Exception as e:
            logger.error(f"Failed to load app config from {path}: {e}", exc_info=True)
            logger.info("Using default app config")
            return cls(path=path, data=default_data)

    @staticmethod
    def _normalize_loaded_data(data: AppConfigData) -> None:
        """Normalize loaded config data."""
        # Validate text_size - must match the options in the field metadata
        valid_options = ["text-xs", "text-sm", "text-base", "text-lg"]
        if not isinstance(data.text_size, str) or data.text_size not in valid_options:
            logger.warning(f"Invalid text_size '{data.text_size}', using default '{DEFAULT_TEXT_SIZE}'")
            data.text_size = DEFAULT_TEXT_SIZE

        # Validate blinded
        if not isinstance(data.blinded, bool):
            data.blinded = DEFAULT_BLINDED

        # Validate window_rect
        if not (isinstance(data.window_rect, list) and len(data.window_rect) == 4):
            data.window_rect = list(DEFAULT_WINDOW_RECT)

    def save(self) -> None:
        """Write config to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = self.data.to_json_dict()
        logger.info("saving app_config to disk")
        logger.info(f"  path: {self.path}")
        from pprint import pprint

        pprint(payload, sort_dicts=False, indent=4)

        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def ensure_exists(self) -> None:
        """Create the config file on disk if it doesn't exist (writes current data)."""
        if not self.path.exists():
            self.save()

    # -----------------------------
    # Public API: attribute access
    # -----------------------------
    def get_attribute(self, key: str) -> Any:
        """
        Get attribute value by key.

        Args:
            key: Attribute name (e.g., 'text_size')

        Returns:
            Attribute value

        Raises:
            AttributeError: If key doesn't exist
        """
        if not hasattr(self.data, key):
            raise AttributeError(f"AppConfigData has no attribute '{key}'")
        return getattr(self.data, key)

    def set_attribute(self, key: str, value: Any) -> None:
        """
        Set attribute value by key with validation.

        Args:
            key: Attribute name (e.g., 'text_size')
            value: New value to set

        Raises:
            AttributeError: If key doesn't exist
            ValueError: If value is invalid for the attribute
        """
        if not hasattr(self.data, key):
            raise AttributeError(f"AppConfigData has no attribute '{key}'")

        # Validate based on field metadata
        field_info = None
        for f in fields(self.data):
            if f.name == key:
                field_info = f
                break

        if field_info is None:
            raise AttributeError(f"Field '{key}' not found in AppConfigData")

        # Type validation
        current_value = getattr(self.data, key)
        if not isinstance(value, type(current_value)):
            # Try to convert if types are compatible
            try:
                if isinstance(current_value, str):
                    value = str(value)
                elif isinstance(current_value, int):
                    value = int(value)
                elif isinstance(current_value, float):
                    value = float(value)
                elif isinstance(current_value, bool):
                    value = bool(value)
                else:
                    raise ValueError(f"Cannot convert {type(value)} to {type(current_value)}")
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid value type for '{key}': {e}")

        # Widget-specific validation
        metadata = field_info.metadata
        widget_type = metadata.get("widget_type")

        if widget_type == "select":
            options = metadata.get("options")
            if options and value not in options:
                raise ValueError(f"Value '{value}' not in allowed options: {options}")

        elif widget_type == "number" or widget_type == "slider":
            min_val = metadata.get("min")
            max_val = metadata.get("max")
            if min_val is not None and value < min_val:
                raise ValueError(f"Value '{value}' is less than minimum '{min_val}'")
            if max_val is not None and value > max_val:
                raise ValueError(f"Value '{value}' is greater than maximum '{max_val}'")

        # Set the value
        setattr(self.data, key, value)
        logger.debug(f"Set app_config.{key} = {value}")

    def get_field_metadata(self, key: str) -> Dict[str, Any]:
        """
        Get metadata for a field (used by GUI to generate widgets).

        Args:
            key: Attribute name (e.g., 'text_size')

        Returns:
            Metadata dict with widget_type, label, options, etc.

        Raises:
            AttributeError: If key doesn't exist
        """
        for f in fields(self.data):
            if f.name == key:
                return dict(f.metadata)
        raise AttributeError(f"AppConfigData has no attribute '{key}'")

    def get_all_fields_with_metadata(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all fields with their metadata (used by GUI to generate widgets).

        Returns:
            Dict mapping field names to their metadata dicts
        """
        result = {}
        for f in fields(self.data):
            if f.name != "schema_version":  # Skip schema_version in GUI
                result[f.name] = {
                    "metadata": dict(f.metadata),
                    "value": getattr(self.data, f.name),
                    "type": type(getattr(self.data, f.name)).__name__,
                }
        return result

    # -----------------------------
    # Public API: blinded analysis
    # -----------------------------
    def get_blinded(self) -> bool:
        """Return blinded analysis mode setting."""
        return bool(self.data.blinded)

    def set_blinded(self, blinded: bool) -> None:
        """Set blinded analysis mode."""
        self.data.blinded = bool(blinded)
        logger.debug(f"Set app_config.blinded = {blinded}")

    # -----------------------------
    # Public API: window geometry
    # -----------------------------
    def set_window_rect(self, x: int, y: int, w: int, h: int) -> None:
        """Set window rectangle [x, y, w, h]."""
        self.data.window_rect = [int(x), int(y), int(w), int(h)]

    def get_window_rect(self) -> Tuple[int, int, int, int]:
        """Return window rectangle as (x, y, w, h)."""
        r = self.data.window_rect
        if not (isinstance(r, list) and len(r) == 4):
            return (DEFAULT_WINDOW_RECT[0], DEFAULT_WINDOW_RECT[1], DEFAULT_WINDOW_RECT[2], DEFAULT_WINDOW_RECT[3])
        try:
            return (int(r[0]), int(r[1]), int(r[2]), int(r[3]))
        except Exception:
            return (DEFAULT_WINDOW_RECT[0], DEFAULT_WINDOW_RECT[1], DEFAULT_WINDOW_RECT[2], DEFAULT_WINDOW_RECT[3])
