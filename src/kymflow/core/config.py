# nicewidgets/config.py
"""
Reusable TOML configuration system (scaffold template + auto-fill defaults).

Features
- TOML on disk (human-editable, supports comments)
- Pydantic models in memory (typed defaults, validation)
- Pattern B:
  - Keep a small scaffold template (comments + ordering).
  - Auto-fill missing keys from the schema defaults.
- Lenient load:
  - Unknown keys do NOT crash.
  - Unknown keys DO warn (helps catch typos).
- Aliases for renamed keys (no migration loop).
- Save modes:
  - keep_unknown_keys=True  -> round-trip update existing file (preserves unknown keys + comments)
  - keep_unknown_keys=False -> rebuild from scaffold (drops unknown keys; keeps scaffold comments)

Dependencies:
- pydantic>=2
- tomlkit>=0.12
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Generic, Mapping, Optional, Sequence, Tuple, Type, TypeVar, Union, List

import logging

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic.aliases import AliasChoices

from tomlkit import parse, dumps
from tomlkit.toml_document import TOMLDocument


T = TypeVar("T", bound=BaseModel)


# -----------------------------------------------------------------------------
# Base model: lenient parsing but observable unknown keys
# -----------------------------------------------------------------------------

class LenientConfigModel(BaseModel):
    """
    Base class for config models.

    We use extra="allow" so that unknown keys are retained in `model_extra`,
    enabling warnings (instead of silently dropping).
    """
    model_config = ConfigDict(extra="allow")


# -----------------------------------------------------------------------------
# Registry types
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class ConfigSpec(Generic[T]):
    """
    Specification for a config type.

    Attributes:
        model_cls: Pydantic model class.
        scaffold_toml: Small TOML template defining ordering + comments.
        default_path: Default path for the TOML file.
        deprecated_keys: Dotted keys removable during normalization.
    """
    model_cls: Type[T]
    scaffold_toml: str
    default_path: str
    deprecated_keys: Tuple[str, ...] = ()


@dataclass(frozen=True)
class LoadResult(Generic[T]):
    """
    Result of loading a config.

    Attributes:
        config: Validated config instance.
        path: File path used.
        wrote_scaffold: True if scaffold was written because the file didn't exist.
        warnings: Collected warnings (unknown keys, deprecated keys removed, etc.).
    """
    config: T
    path: Path
    wrote_scaffold: bool
    warnings: Tuple[str, ...]


# -----------------------------------------------------------------------------
# TOML document helpers
# -----------------------------------------------------------------------------

def _read_toml_doc(path: Path) -> TOMLDocument:
    """
    Read a TOML file into a tomlkit document (round-trip capable).

    Args:
        path: TOML file path.

    Returns:
        TOMLDocument preserving comments/formatting.
    """
    return parse(path.read_text(encoding="utf-8"))


def _write_toml_doc(path: Path, doc: TOMLDocument) -> None:
    """
    Write a tomlkit document back to disk.

    Args:
        path: TOML file path.
        doc: TOMLDocument to write.
    """
    path.write_text(dumps(doc), encoding="utf-8")


def _doc_to_plain_dict(doc: TOMLDocument) -> Dict[str, Any]:
    """
    Convert a tomlkit document into plain Python types.

    Args:
        doc: TOMLDocument.

    Returns:
        Plain dict of builtin Python types.
    """
    return doc.unwrap()  # type: ignore[attr-defined]


def _ensure_scaffold_file(path: Path, scaffold_toml: str) -> bool:
    """
    Ensure the config file exists. If missing, write the scaffold template.

    Args:
        path: TOML file path.
        scaffold_toml: Scaffold TOML string.

    Returns:
        True if scaffold was written, False otherwise.
    """
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(scaffold_toml, encoding="utf-8")
    return True


# -----------------------------------------------------------------------------
# Unknown key warnings
# -----------------------------------------------------------------------------

def _collect_unknown_key_warnings(cfg: BaseModel) -> Sequence[str]:
    """
    Recursively collect warnings about unknown keys preserved in model_extra.

    Args:
        cfg: Pydantic model instance.

    Returns:
        Warning strings like "Unknown config key ignored: roi.opactiy".
    """
    warnings: list[str] = []
    _walk_model_for_unknowns(cfg, prefix="", warnings=warnings)
    return warnings


def _walk_model_for_unknowns(model: BaseModel, prefix: str, warnings: list[str]) -> None:
    """
    Walk a Pydantic model recursively collecting unknown keys.

    Args:
        model: Current model node.
        prefix: Dotted prefix for nested models.
        warnings: Output list to append to.
    """
    extras = getattr(model, "model_extra", None) or {}
    for k in sorted(extras.keys()):
        loc = f"{prefix}{k}" if prefix else k
        warnings.append(f"Unknown config key ignored: {loc}")

    for name, value in model.__dict__.items():
        if isinstance(value, BaseModel):
            new_prefix = f"{prefix}{name}." if prefix else f"{name}."
            _walk_model_for_unknowns(value, new_prefix, warnings)


# -----------------------------------------------------------------------------
# Pattern B: scaffold + auto-fill defaults
# -----------------------------------------------------------------------------

def _merge_missing_defaults_into_doc(doc: Any, defaults: Dict[str, Any]) -> bool:
    """
    Merge missing keys from defaults into a TOML document/table (in-place).

    This is the auto-fill part of Pattern B.

    Args:
        doc: TOMLDocument or tomlkit table-like object.
        defaults: Defaults dict from cfg.model_dump().

    Returns:
        True if any key was added, False otherwise.
    """
    changed = False
    for key, val in defaults.items():
        if isinstance(val, dict):
            if key not in doc:
                doc[key] = {}
                changed = True
            changed = _merge_missing_defaults_into_doc(doc[key], val) or changed  # type: ignore[index]
        else:
            if key not in doc:
                doc[key] = val
                changed = True
    return changed


def _set_known_values_into_doc(doc: Any, values: Dict[str, Any]) -> bool:
    """
    Set/overwrite known keys in an existing TOML document/table (in-place).

    Useful for save/normalize: ensure file reflects current model values.

    Args:
        doc: TOMLDocument or tomlkit table-like object.
        values: Values dict from cfg.model_dump().

    Returns:
        True if any value was written/changed, False otherwise.
    """
    changed = False
    for key, val in values.items():
        if isinstance(val, dict):
            if key not in doc:
                doc[key] = {}
                changed = True
            changed = _set_known_values_into_doc(doc[key], val) or changed  # type: ignore[index]
        else:
            if key not in doc or doc[key] != val:
                doc[key] = val
                changed = True
    return changed


def _build_doc_from_scaffold(scaffold_toml: str, values: Dict[str, Any]) -> TOMLDocument:
    """
    Build a fresh TOMLDocument from scaffold and write in known values.

    This is the clean way to "drop unknown keys on save" while preserving
    scaffold comments and ordering.

    Args:
        scaffold_toml: Scaffold template (comments/layout).
        values: Known config values (cfg.model_dump()).

    Returns:
        New TOMLDocument containing only scaffold + known keys.
    """
    doc = parse(scaffold_toml)
    _merge_missing_defaults_into_doc(doc, values)
    _set_known_values_into_doc(doc, values)
    return doc


def _delete_dotted_key(doc: Any, dotted_key: str) -> bool:
    """
    Delete a dotted key from a TOML doc/table, if present.

    Example:
        dotted_key="roi.stroke_width"

    Args:
        doc: TOMLDocument or table-like.
        dotted_key: Dotted path key.

    Returns:
        True if deleted, False otherwise.
    """
    parts = dotted_key.split(".")
    cur = doc
    for i, part in enumerate(parts):
        if part not in cur:
            return False
        if i == len(parts) - 1:
            try:
                del cur[part]
                return True
            except Exception:
                return False
        cur = cur[part]
    return False

def _dump_known_fields(model: BaseModel) -> Dict[str, Any]:
    """
    Dump only declared (schema) fields from a Pydantic model, excluding model_extra.

    This is critical because we use extra="allow" to *warn* about unknown keys,
    but we do NOT want unknown keys to be persisted when keep_unknown_keys=False.

    Args:
        model: Pydantic model.

    Returns:
        Dict containing only declared fields, recursively for nested models.
    """
    out: Dict[str, Any] = {}
    for name in model.model_fields.keys():
        value = getattr(model, name)
        if isinstance(value, BaseModel):
            out[name] = _dump_known_fields(value)
        elif isinstance(value, list):
            # If you later use lists of models, support that too.
            out[name] = [
                _dump_known_fields(v) if isinstance(v, BaseModel) else v
                for v in value
            ]
        else:
            out[name] = value
    return out

# -----------------------------------------------------------------------------
# Public API (generic): load / save / normalize
# -----------------------------------------------------------------------------

def load_config(
    *,
    spec: ConfigSpec[T],
    path: Optional[Union[str, Path]] = None,
    logger: Optional[logging.Logger] = None,
    autofill_missing_defaults: bool = True,
    warn_unknown_keys: bool = True,
) -> LoadResult[T]:
    """
    Load a TOML config using Pattern B (scaffold + auto-fill) and validate via Pydantic.

    Steps:
      1) Ensure file exists (write scaffold if missing)
      2) Parse TOML preserving comments
      3) Validate with Pydantic (typed config)
      4) Warn on unknown keys (lenient parsing)
      5) Optionally auto-fill missing defaults into TOML (preserving comments)

    Args:
        spec: ConfigSpec for the config type.
        path: Optional path override; defaults to spec.default_path.
        logger: Optional logger; defaults to module logger.
        autofill_missing_defaults: If True, add missing known keys into the file.
        warn_unknown_keys: If True, emit warnings for unknown keys.

    Returns:
        LoadResult with validated config instance and warnings.

    Raises:
        ValidationError: If known fields have invalid types/ranges.
    """
    log = logger or logging.getLogger(__name__)
    p = Path(path) if path is not None else Path(spec.default_path)

    wrote_scaffold = _ensure_scaffold_file(p, spec.scaffold_toml)

    doc = _read_toml_doc(p)
    data = _doc_to_plain_dict(doc)

    cfg = spec.model_cls.model_validate(data)

    warnings: list[str] = []
    if warn_unknown_keys:
        warnings.extend(_collect_unknown_key_warnings(cfg))
        for w in warnings:
            log.warning(w)

    if autofill_missing_defaults:
        # changed = _merge_missing_defaults_into_doc(doc, cfg.model_dump())
        changed = _merge_missing_defaults_into_doc(doc, _dump_known_fields(cfg))
        if changed:
            _write_toml_doc(p, doc)

    return LoadResult(config=cfg, path=p, wrote_scaffold=wrote_scaffold, warnings=tuple(warnings))


def save_config(
    *,
    spec: ConfigSpec[T],
    cfg: T,
    path: Optional[Union[str, Path]] = None,
    logger: Optional[logging.Logger] = None,
    keep_unknown_keys: bool = True,
) -> None:
    """
    Save a validated config back to TOML.

    Two modes:
    - keep_unknown_keys=True:
        Round-trip update the existing file, preserving comments and any unknown keys.
    - keep_unknown_keys=False:
        Rebuild the document from the scaffold, dropping unknown keys while keeping
        scaffold comments/order.

    Args:
        spec: ConfigSpec for this config type.
        cfg: Validated config model instance.
        path: Optional path override.
        logger: Optional logger.
        keep_unknown_keys: Whether to preserve unknown keys already present in the file.

    Raises:
        ValueError: If cfg is not an instance of spec.model_cls.
    """
    log = logger or logging.getLogger(__name__)
    p = Path(path) if path is not None else Path(spec.default_path)

    if not isinstance(cfg, spec.model_cls):
        raise ValueError(f"cfg must be instance of {spec.model_cls.__name__}")

    _ensure_scaffold_file(p, spec.scaffold_toml)

    # values = cfg.model_dump()
    values = _dump_known_fields(cfg)
    if keep_unknown_keys:
        doc = _read_toml_doc(p)
        changed = _set_known_values_into_doc(doc, values)
        if changed:
            _write_toml_doc(p, doc)
    else:
        doc = _build_doc_from_scaffold(spec.scaffold_toml, values)
        _write_toml_doc(p, doc)

    for w in _collect_unknown_key_warnings(cfg):
        log.warning(w)


def normalize_config(
    *,
    spec: ConfigSpec[T],
    path: Optional[Union[str, Path]] = None,
    logger: Optional[logging.Logger] = None,
    remove_deprecated_keys: bool = True,
    autofill_missing_defaults: bool = True,
    overwrite_known_values: bool = True,
    drop_unknown_keys: bool = False,
) -> LoadResult[T]:
    """
    Normalize a config file while preserving scaffold comments as much as possible.

    - remove deprecated alias keys (optional)
    - ensure all known keys exist (optional)
    - overwrite known values with canonical values (optional)
    - optionally drop unknown keys by rebuilding from scaffold

    Args:
        spec: ConfigSpec.
        path: Path override.
        logger: Logger for warnings.
        remove_deprecated_keys: If True, remove spec.deprecated_keys from file.
        autofill_missing_defaults: If True, fill missing keys from schema defaults.
        overwrite_known_values: If True, set known values from validated model into file.
        drop_unknown_keys: If True, rebuild file from scaffold (drops unknown keys).

    Returns:
        LoadResult after normalization (validated config + warnings).

    Raises:
        ValidationError: If known fields are invalid.
    """
    log = logger or logging.getLogger(__name__)
    p = Path(path) if path is not None else Path(spec.default_path)

    wrote_scaffold = _ensure_scaffold_file(p, spec.scaffold_toml)
    doc = _read_toml_doc(p)
    data = _doc_to_plain_dict(doc)

    cfg = spec.model_cls.model_validate(data)

    warnings: list[str] = list(_collect_unknown_key_warnings(cfg))
    for w in warnings:
        log.warning(w)

    changed = False

    if remove_deprecated_keys and spec.deprecated_keys:
        for dk in spec.deprecated_keys:
            if _delete_dotted_key(doc, dk):
                msg = f"Removed deprecated config key: {dk}"
                warnings.append(msg)
                log.warning(msg)
                changed = True

    if autofill_missing_defaults:
        changed = _merge_missing_defaults_into_doc(doc, _dump_known_fields(cfg)) or changed

    if overwrite_known_values:
        changed = _set_known_values_into_doc(doc, _dump_known_fields(cfg)) or changed

    if drop_unknown_keys:
        doc2 = _build_doc_from_scaffold(spec.scaffold_toml, _dump_known_fields(cfg))
        if dumps(doc2) != dumps(doc):
            doc = doc2
            changed = True

    if changed:
        _write_toml_doc(p, doc)

    return LoadResult(config=cfg, path=p, wrote_scaffold=wrote_scaffold, warnings=tuple(warnings))


# -----------------------------------------------------------------------------
# Example config models + registry (ROI + Image display)
# -----------------------------------------------------------------------------

class RoiStyle(LenientConfigModel):
    """
    Style options for rectangular ROIs.

    Demonstrates aliases so you can rename keys without a migration loop.
    Old keys accepted:
      - stroke_color -> line_color
      - stroke_width -> line_width
      - fill_alpha -> opacity
    """
    stroke_color: str = Field(
        default="#00FF00",
        # validation_alias=AliasChoices("line_color", "stroke_color"),
    )
    stroke_width: float = Field(
        default=2.0,
        ge=0.0,
        # validation_alias=AliasChoices("line_width", "stroke_width"),
    )
    fill_color: str = "#00FF00"
    opacity: float = Field(
        default=0.25,
        ge=0.0,
        le=1.0,
        # validation_alias=AliasChoices("opacity", "fill_alpha"),
    )
    # show_handles: bool = True
    # hit_slop_px: int = Field(default=6, ge=0)


class RoiGuiConfig(LenientConfigModel):
    """Config for ROI GUI styling + interaction defaults."""
    version: int = Field(default=1, ge=1)
    roi: RoiStyle = Field(default_factory=RoiStyle)
    # canvas_bg: str = "#000000"
    # zoom_wheel_sensitivity: float = Field(default=1.0, gt=0.0)


ROI_GUI_SCAFFOLD_TOML = """\
# ROI GUI config (scaffold)
# - Scaffold defines ordering + comments.
# - Missing keys are auto-filled from schema defaults (Pattern B).
# - Unknown keys are tolerated but warned about.

version = 1

[roi]
# Stroke (outline)
stroke_color = "#00FF00"
stroke_width = 2.0

# Fill (interior)
fill_color = "#00FF00"
opacity = 0.25
"""


class ImageDisplayConfig(LenientConfigModel):
    """Options controlling how an image is displayed."""
    version: int = Field(default=1, ge=1)
    x_axis: bool = True
    y_axis: bool = True
    x_label: str = "x"
    y_label: str = "y"
    color_lut: str = "gray"
    show_toolbar: bool = True


IMAGE_DISPLAY_SCAFFOLD_TOML = """\
# Image display options (scaffold)
# Missing keys are auto-filled from schema defaults.

version = 1

# Axes
x_axis = true
y_axis = true
x_label = "x"
y_label = "y"

# Color / UI
color_lut = "gray"
show_toolbar = true
"""


CONFIGS: Mapping[str, ConfigSpec[Any]] = {
    "roi_gui": ConfigSpec(
        model_cls=RoiGuiConfig,
        scaffold_toml=ROI_GUI_SCAFFOLD_TOML,
        default_path="config/roi_gui.toml",
        deprecated_keys=("roi.stroke_color", "roi.stroke_width", "roi.fill_alpha"),
    ),
    "image_display": ConfigSpec(
        model_cls=ImageDisplayConfig,
        scaffold_toml=IMAGE_DISPLAY_SCAFFOLD_TOML,
        default_path="config/image_display.toml",
    ),
}


# -----------------------------------------------------------------------------
# Named API (small public surface)
# -----------------------------------------------------------------------------

def list_configs() -> List[str]:
    """
    List registered config names.

    Returns:
        Sorted list of registry keys (e.g. ["image_display", "roi_gui"]).
    """
    return sorted(CONFIGS.keys())


def get_spec(name: str) -> ConfigSpec[Any]:
    """
    Fetch a ConfigSpec by registry name.

    Args:
        name: Registry key (e.g. "roi_gui", "image_display").

    Returns:
        ConfigSpec.

    Raises:
        KeyError: If name is not registered.
    """
    return CONFIGS[name]


def load_named(
    name: str,
    *,
    path: Optional[Union[str, Path]] = None,
    logger: Optional[logging.Logger] = None,
    autofill_missing_defaults: bool = True,
    warn_unknown_keys: bool = True,
) -> LoadResult[Any]:
    """
    Load a named config from the registry.

    Args:
        name: Registry key.
        path: Optional path override.
        logger: Optional logger.
        autofill_missing_defaults: Auto-fill missing known keys from schema defaults into the TOML file.
        warn_unknown_keys: Emit warnings for unknown keys.

    Returns:
        LoadResult with validated config instance.
    """
    return load_config(
        spec=get_spec(name),
        path=path,
        logger=logger,
        autofill_missing_defaults=autofill_missing_defaults,
        warn_unknown_keys=warn_unknown_keys,
    )


def save_named(
    name: str,
    cfg: BaseModel,
    *,
    path: Optional[Union[str, Path]] = None,
    logger: Optional[logging.Logger] = None,
    keep_unknown_keys: bool = True,
) -> None:
    """
    Save a named config back to TOML.

    Args:
        name: Registry key.
        cfg: Config model instance (must match the spec's model).
        path: Optional path override.
        logger: Optional logger.
        keep_unknown_keys: If False, rebuild from scaffold and drop unknown keys.
    """
    spec = get_spec(name)
    # type: ignore[arg-type] because cfg is BaseModel at signature
    save_config(spec=spec, cfg=cfg, path=path, logger=logger, keep_unknown_keys=keep_unknown_keys)  # type: ignore[arg-type]


def normalize_named(
    name: str,
    *,
    path: Optional[Union[str, Path]] = None,
    logger: Optional[logging.Logger] = None,
    remove_deprecated_keys: bool = True,
    autofill_missing_defaults: bool = True,
    overwrite_known_values: bool = True,
    drop_unknown_keys: bool = False,
) -> LoadResult[Any]:
    """
    Normalize a named config file.

    Args:
        name: Registry key.
        path: Optional path override.
        logger: Optional logger.
        remove_deprecated_keys: Remove deprecated alias keys listed in the spec.
        autofill_missing_defaults: Fill missing keys from defaults.
        overwrite_known_values: Overwrite known keys with validated model values.
        drop_unknown_keys: If True, rebuild from scaffold to drop unknown keys.

    Returns:
        LoadResult after normalization.
    """
    return normalize_config(
        spec=get_spec(name),
        path=path,
        logger=logger,
        remove_deprecated_keys=remove_deprecated_keys,
        autofill_missing_defaults=autofill_missing_defaults,
        overwrite_known_values=overwrite_known_values,
        drop_unknown_keys=drop_unknown_keys,
    )
