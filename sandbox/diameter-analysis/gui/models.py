from __future__ import annotations

from dataclasses import dataclass, field, asdict, is_dataclass, fields
from typing import Any, Optional, Callable, Type, TypeVar, get_origin, get_args
from enum import Enum

import numpy as np

T = TypeVar("T")

def _is_enum_type(tp: Any) -> bool:
    try:
        return isinstance(tp, type) and issubclass(tp, Enum)
    except Exception:
        return False

def _unwrap_optional(tp: Any) -> Any:
    origin = get_origin(tp)
    if origin is None:
        return tp
    if origin is Optional or origin is list or origin is dict:
        return tp
    if origin is type(Optional[int]).__origin__:  # Union
        args = [a for a in get_args(tp) if a is not type(None)]
        if len(args) == 1:
            return args[0]
    return tp

def dataclass_to_dict(obj: Any) -> dict[str, Any]:
    if not is_dataclass(obj):
        raise TypeError("dataclass_to_dict expects a dataclass instance")
    out: dict[str, Any] = {}
    for f in fields(obj):
        v = getattr(obj, f.name)
        if isinstance(v, Enum):
            out[f.name] = v.value
        elif is_dataclass(v):
            out[f.name] = dataclass_to_dict(v)
        elif isinstance(v, (np.floating, np.integer)):
            out[f.name] = v.item()
        else:
            out[f.name] = v
    return out

def dataclass_from_dict(cls: Type[T], payload: dict[str, Any]) -> T:
    if not isinstance(payload, dict):
        raise TypeError("payload must be a dict")
    kwargs: dict[str, Any] = {}
    for f in fields(cls):
        if f.name not in payload:
            continue
        raw = payload[f.name]
        tp = _unwrap_optional(f.type)
        if _is_enum_type(tp):
            kwargs[f.name] = tp(raw)
        elif isinstance(tp, type) and is_dataclass(tp) and isinstance(raw, dict):
            kwargs[f.name] = dataclass_from_dict(tp, raw)
        else:
            kwargs[f.name] = raw
    return cls(**kwargs)  # type: ignore[arg-type]


@dataclass
class GuiConfig:
    """Execution-level GUI settings."""
    show_center_overlay: bool = True
    auto_link_xaxis: bool = True


@dataclass
class AppState:
    """App state for one GUI session."""
    # Data
    img: Optional[np.ndarray] = None              # (time, space) as per project convention
    seconds_per_line: float = 0.001
    um_per_pixel: float = 0.15
    polarity: str = "bright_on_dark"
    source: str = "synthetic"
    loaded_path: Optional[str] = None

    # Analysis
    results: Optional[Any] = None                # analyzer results object / dict / DataFrame; kept opaque here

    # Params (opaque; comes from your core modules)
    synthetic_params: Optional[Any] = None
    detection_params: Optional[Any] = None
    post_filter_params: Optional[Any] = None

    gui: GuiConfig = field(default_factory=GuiConfig)

    # View state
    x_range: Optional[tuple[float, float]] = None  # seconds
