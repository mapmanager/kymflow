# src/kymflow/core/plotting/pool/pool_plot_config.py
"""
Pool plot config persistence for kymflow (platformdirs + JSON).

Persisted items (schema v1):
- plot_state: PlotState dict representation

Behavior:
- If config file missing or unreadable -> defaults are used
- If schema_version mismatches:
  - default: reset to defaults (safe for distributed desktop apps)
  - optional: keep loaded but update version
- Unknown keys in loaded JSON are ignored with warnings

Design:
- PoolPlotConfigData dataclass holds JSON-friendly data
- PoolPlotConfig manager provides explicit API for load/save
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from platformdirs import user_config_dir

from kymflow.core.utils.logging import get_logger
from kymflow.core.plotting.pool.plot_state import PlotState

logger = get_logger(__name__)

# Increment when you make a breaking change to the on-disk JSON schema.
SCHEMA_VERSION: int = 2


@dataclass
class PoolPlotConfigData:
    """
    JSON-serializable config payload.
    
    Keep fields JSON-friendly:
    - primitives, lists, dicts
    
    Schema v2:
    - layout: str (e.g., "1x1", "1x2", "2x1", "2x2")
    - plot_states: List[Dict[str, Any]] - list of PlotState dicts (one per plot in layout)
    
    Schema v1 (backward compatibility):
    - plot_state: Dict[str, Any] - single PlotState dict (converted to plot_states list)
    """
    schema_version: int = SCHEMA_VERSION
    layout: str = "1x1"
    plot_states: list[Dict[str, Any]] = field(default_factory=list)

    def to_json_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "schema_version": self.schema_version,
            "layout": self.layout,
            "plot_states": self.plot_states,
        }

    @classmethod
    def from_json_dict(cls, d: Dict[str, Any]) -> "PoolPlotConfigData":
        """
        Tolerant loader:
        - ignores unknown keys
        - tolerates partially missing values
        - handles backward compatibility with schema v1
        """
        schema_version = int(d.get("schema_version", -1))
        
        # layout - extract with default
        layout = str(d.get("layout", "1x1"))
        
        # plot_states - extract and validate
        plot_states_list: list[Dict[str, Any]] = []
        
        # Schema v2: plot_states is a list
        if "plot_states" in d:
            plot_states_raw = d.get("plot_states", [])
            if isinstance(plot_states_raw, list):
                plot_states_list = plot_states_raw
            else:
                logger.warning(f"plot_states is not a list, using empty list")
        
        # Schema v1 backward compatibility: plot_state is a dict
        elif "plot_state" in d:
            plot_state_raw = d.get("plot_state", {})
            if isinstance(plot_state_raw, dict) and plot_state_raw:
                plot_states_list = [plot_state_raw]
                logger.info("Loaded schema v1 config (plot_state), converted to v2 format (plot_states)")
            else:
                logger.warning(f"plot_state is not a dict or is empty, using empty list")
        
        # Warn about unknown keys in the root level
        known_keys = {"schema_version", "layout", "plot_state", "plot_states"}
        for key in d.keys():
            if key not in known_keys:
                logger.warning(f"Unknown key '{key}' in pool plot config, ignoring")
        
        return cls(
            schema_version=schema_version,
            layout=layout,
            plot_states=plot_states_list,
        )


class PoolPlotConfig:
    """
    Manager for loading/saving PoolPlotConfigData to disk.
    """

    def __init__(self, *, path: Path, data: Optional[PoolPlotConfigData] = None):
        self.path = path
        self.data = data if data is not None else PoolPlotConfigData()

    # -----------------------------
    # Construction / persistence
    # -----------------------------
    @staticmethod
    def default_config_path(
        app_name: str = "kymflow",
        filename: str = "pool_plot_config.json",
        app_author: str | None = None,
    ) -> Path:
        """
        Determine OS-appropriate per-user config path.

        macOS:   ~/Library/Application Support/kymflow/pool_plot_config.json
        Linux:   ~/.config/kymflow/pool_plot_config.json
        Windows: %APPDATA%\\kymflow\\pool_plot_config.json
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
        filename: str = "pool_plot_config.json",
        app_author: str | None = None,
        schema_version: int = SCHEMA_VERSION,
        reset_on_version_mismatch: bool = True,
        create_if_missing: bool = False,
    ) -> "PoolPlotConfig":
        """
        Load config from disk.

        If file doesn't exist or is unreadable -> defaults.
        If schema mismatch:
          - reset_on_version_mismatch=True -> defaults
          - else -> keep loaded but overwrite schema_version

        If create_if_missing=True and file is missing -> immediately write defaults.
        """
        path = config_path or cls.default_config_path(app_name=app_name, filename=filename, app_author=app_author)
        default_data = PoolPlotConfigData(schema_version=schema_version)

        try:
            raw = path.read_text(encoding="utf-8")
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                logger.warning(f"Pool plot config file at {path} does not contain a dict, using defaults")
                return cls(path=path, data=default_data)

            loaded = PoolPlotConfigData.from_json_dict(parsed)

            if int(loaded.schema_version) != int(schema_version):
                if reset_on_version_mismatch:
                    logger.warning(
                        f"Pool plot config schema version mismatch: loaded={loaded.schema_version}, "
                        f"expected={schema_version}, resetting to defaults"
                    )
                    cfg = cls(path=path, data=default_data)
                    if create_if_missing:
                        cfg.save()
                    return cfg
                loaded.schema_version = int(schema_version)

            return cls(path=path, data=loaded)
        except FileNotFoundError:
            logger.debug(f"Pool plot config file not found at {path}, using defaults")
            cfg = cls(path=path, data=default_data)
            if create_if_missing:
                cfg.save()
            return cfg
        except json.JSONDecodeError as e:
            logger.warning(f"Pool plot config file at {path} is not valid JSON: {e}, using defaults")
            return cls(path=path, data=default_data)
        except Exception as e:
            logger.warning(f"Error loading pool plot config from {path}: {e}, using defaults")
            return cls(path=path, data=default_data)

    def save(self) -> None:
        """Write config to disk."""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            json_str = json.dumps(self.data.to_json_dict(), indent=2)
            self.path.write_text(json_str, encoding="utf-8")
            logger.info(f"Saved pool plot config to {self.path}")
        except Exception as e:
            logger.error(f"Error saving pool plot config to {self.path}: {e}")
            raise

    def get_layout(self) -> str:
        """Get layout string from config."""
        return self.data.layout
    
    def set_layout(self, layout: str) -> None:
        """Set layout string in config."""
        self.data.layout = layout
    
    def get_plot_states(self) -> list[PlotState]:
        """Get list of PlotState objects from config."""
        result = []
        for plot_state_dict in self.data.plot_states:
            try:
                result.append(PlotState.from_dict(plot_state_dict))
            except Exception as e:
                logger.warning(f"Error deserializing PlotState from config: {e}")
        return result
    
    def set_plot_states(self, plot_states: list[PlotState]) -> None:
        """Set list of PlotState objects in config."""
        self.data.plot_states = [ps.to_dict() for ps in plot_states]
    
    # Backward compatibility methods (deprecated, use get_plot_states/set_plot_states)
    def get_plot_state(self) -> Optional[PlotState]:
        """Get first PlotState from config (backward compatibility).
        
        Deprecated: Use get_plot_states() instead.
        """
        plot_states = self.get_plot_states()
        return plot_states[0] if plot_states else None

    def set_plot_state(self, plot_state: PlotState) -> None:
        """Set single PlotState in config (backward compatibility).
        
        Deprecated: Use set_plot_states() instead.
        """
        self.set_plot_states([plot_state])
