from __future__ import annotations

import dataclasses
import types
from dataclasses import MISSING
from enum import Enum
from typing import Any, Union, get_args, get_origin, get_type_hints

import numpy as np


def _strip_optional(tp: Any) -> tuple[Any, bool]:
    origin = get_origin(tp)
    if origin in {Union, types.UnionType}:
        args = [a for a in get_args(tp) if a is not type(None)]
        if len(args) == 1:
            return args[0], True
    return tp, False


def _is_dataclass_type(tp: Any) -> bool:
    return isinstance(tp, type) and dataclasses.is_dataclass(tp)


def _is_enum_type(tp: Any) -> bool:
    return isinstance(tp, type) and issubclass(tp, Enum)


def _serialize_value(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return dataclass_to_dict(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, tuple):
        return [_serialize_value(v) for v in value]
    if isinstance(value, list):
        return [_serialize_value(v) for v in value]
    if isinstance(value, dict):
        return {k: _serialize_value(v) for k, v in value.items()}
    return value


def dataclass_to_dict(obj: Any) -> dict[str, Any]:
    """Convert a dataclass instance into JSON-safe nested dictionaries/lists.

    Args:
        obj: Dataclass instance to serialize.

    Returns:
        Dictionary representation with enums/NumPy scalars normalized.
    """
    if not dataclasses.is_dataclass(obj):
        raise TypeError("dataclass_to_dict expects a dataclass instance")

    out: dict[str, Any] = {}
    for f in dataclasses.fields(obj):
        out[f.name] = _serialize_value(getattr(obj, f.name))
    return out


def _coerce_scalar(tp: Any, value: Any) -> Any:
    if value is None:
        return None
    if tp is bool:
        if isinstance(value, str):
            v = value.strip().lower()
            if v in {"true", "1", "yes", "y"}:
                return True
            if v in {"false", "0", "no", "n"}:
                return False
        return bool(value)
    if tp is int:
        return int(value)
    if tp is float:
        return float(value)
    if tp is str:
        return str(value)
    return value


def _deserialize_value(tp: Any, value: Any) -> Any:
    inner_tp, _optional = _strip_optional(tp)
    if value is None:
        return None

    if _is_enum_type(inner_tp):
        try:
            return inner_tp(value)
        except Exception as e:
            raise ValueError(f"Invalid enum value {value!r} for {inner_tp.__name__}") from e

    if _is_dataclass_type(inner_tp):
        if not isinstance(value, dict):
            raise ValueError(f"Expected object for nested dataclass {inner_tp.__name__}")
        return dataclass_from_dict(inner_tp, value)

    origin = get_origin(inner_tp)
    args = get_args(inner_tp)
    if origin is tuple and args:
        if not isinstance(value, (list, tuple)):
            return value
        return tuple(value)

    if inner_tp in {bool, int, float, str}:
        return _coerce_scalar(inner_tp, value)

    return value


def dataclass_from_dict(cls: type[Any], payload: dict[str, Any]) -> Any:
    """Instantiate a dataclass from a dictionary payload.

    Args:
        cls: Target dataclass type.
        payload: Source dictionary payload.

    Returns:
        Dataclass instance with basic scalar/enum coercions applied.
    """
    if not (isinstance(cls, type) and dataclasses.is_dataclass(cls)):
        raise TypeError("dataclass_from_dict expects a dataclass class")
    if not isinstance(payload, dict):
        raise TypeError("payload must be a dictionary")

    type_hints = get_type_hints(cls)
    kwargs: dict[str, Any] = {}
    for f in dataclasses.fields(cls):
        if f.name not in payload:
            if f.default is not MISSING or f.default_factory is not MISSING:
                continue
            continue
        raw = payload[f.name]
        field_tp = type_hints.get(f.name, f.type)
        kwargs[f.name] = _deserialize_value(field_tp, raw)

    return cls(**kwargs)
