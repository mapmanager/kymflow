"""Folder-scoped catalog of image files with lazy metadata and loaders.

This module is for **filesystem-backed** discovery and
:class:`~kymflow.core.image_loaders.image_loader_plugins.my_image_import.ImageLoaderBase`
instances. It is independent of upload or GUI code paths.

``MyImageList.__init__`` only walks the tree (bounded depth). Header reads for
OIR/CZI are deferred until :meth:`MyImageList.header_records` (or
:meth:`MyImageList.get_loader_for_path`) needs them. TIFF rows may load metadata
from an Olympus ``.txt`` sidecar without reading pixels; otherwise the header is
filled when a :class:`~kymflow.core.image_loaders.image_loader_plugins.my_image_import.MyTifImage`
is constructed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from kymflow.core.image_loaders.image_loader_plugins.my_image_import import (
    ImageHeader,
    ImageLoaderBase,
    MyCziImage,
    MyOirImage,
    MyTifImage,
    image_header_from_olympus_dict,
)
from kymflow.core.image_loaders.image_loader_plugins.olympus_txt_kym import (
    read_olympus_txt_dict,
)

from kymflow.core.utils.logging import get_logger
logger = get_logger(__name__)

_OME_NOT_SUPPORTED_MSG = "OME-TIFF is not supported for this catalog."


@dataclass(frozen=True)
class PixelLoadPolicy:
    """Whether pixel loading is allowed for a catalog row (see :meth:`MyImageList.describe_pixel_load`)."""

    allowed: bool
    code: str
    message: str | None = None


def _relative_path_str(catalog_root: Path, file_path: Path) -> str:
    """Path of ``file_path`` relative to ``catalog_root``, POSIX ``/`` separators."""
    root = catalog_root.resolve()
    resolved = file_path.resolve()
    return resolved.relative_to(root).as_posix()


def _folder_ancestry(file_path: Path) -> tuple[str, str]:
    """Absolute parent directory and grandparent directory of ``file_path``."""
    resolved = file_path.resolve()
    parent = resolved.parent
    grandparent = parent.parent
    return str(parent), str(grandparent)


def _shape_display(shape: object) -> str:
    if shape is None:
        return ""
    if isinstance(shape, list):
        return "×".join(str(x) for x in shape)
    return str(shape)


def _dims_display(dims: object) -> str:
    if dims is None:
        return ""
    if isinstance(dims, list):
        return ", ".join(str(d) for d in dims)
    return str(dims)


def _normalize_extension_token(ext: str) -> str:
    return ext.lower().lstrip(".")


def _suffix_set_from_find_these(find_these_extensions: list[str]) -> set[str]:
    return {f".{_normalize_extension_token(e)}" for e in find_these_extensions}


def _bounded_file_paths(root: Path, max_depth: int) -> list[Path]:
    """List files under ``root`` whose parent directory depth is at most ``max_depth``.

    Depth of ``root`` is ``0``; each step into a child directory adds ``1``.
    Files directly in ``root`` are included when ``max_depth >= 0``. Subdirectories
    at depth ``max_depth`` are listed for files but not descended further.

    If ``root`` does not exist (e.g. fixtures not checked out), returns an empty list
    so callers like :class:`MyImageList` can still construct with an empty catalog.
    """
    root = root.resolve()
    if not root.exists():
        return []
    if not root.is_dir():
        raise ValueError(f"Expected a directory: {root}")
    out: list[Path] = []
    stack: list[tuple[Path, int]] = [(root, 0)]
    while stack:
        dirpath, depth = stack.pop()
        try:
            children = sorted(dirpath.iterdir(), key=lambda p: p.name.lower())
        except OSError:
            continue
        for p in children:
            if p.is_dir():
                if depth < max_depth:
                    stack.append((p, depth + 1))
            elif p.is_file():
                out.append(p.resolve())
    out.sort(key=lambda x: str(x).lower())
    return out


@dataclass
class _CatalogRow:
    """One discovered file; header read is lazy for OIR/CZI and optional TIFF Olympus txt."""

    path: str
    relative_path: str
    format: str
    parent_dir: str
    grandparent_dir: str
    _header: ImageHeader | None = None
    _header_error: str | None = None
    _header_attempted: bool = False
    _tif_olympus_attempted: bool = False

    def _ensure_header_read(self) -> None:
        if self._header_attempted:
            return
        if self.format in ("tif", "tiff"):
            return
        if self.format == "ome-tiff":
            self._header_attempted = True
            return
        self._header_attempted = True
        try:
            if self.format == "czi":
                self._header = MyCziImage.read_header_from_path(self.path)
            elif self.format == "oir":
                self._header = MyOirImage.read_header_from_path(self.path)
            else:
                self._header_error = f"Unexpected format {self.format!r}"
        except BaseException as exc:
            self._header_error = f"{type(exc).__name__}: {exc}"

    def _ensure_tif_olympus_header(self) -> None:
        if self.format not in ("tif", "tiff"):
            return
        if self._tif_olympus_attempted:
            return
        self._tif_olympus_attempted = True
        odict = read_olympus_txt_dict(self.path)
        if odict is None:
            return
        try:
            self._header = image_header_from_olympus_dict(self.path, odict)
        except (ValueError, TypeError, KeyError) as exc:
            self._header_error = f"{type(exc).__name__}: {exc}"
            logger.warning(
                "Olympus txt present for %s but ImageHeader build failed: %s",
                self.path,
                exc,
            )

    def ensure_metadata(self) -> None:
        """Load lazy header metadata appropriate for this row's format."""
        if self.format in ("tif", "tiff"):
            self._ensure_tif_olympus_header()
        else:
            self._ensure_header_read()

    def _ancestry_fields(self) -> dict[str, Any]:
        pdir = Path(self.parent_dir)
        gdir = Path(self.grandparent_dir)
        return {
            "parent_dir": self.parent_dir,
            "grandparent_dir": self.grandparent_dir,
            "parent_name": pdir.name,
            "grandparent_name": gdir.name,
        }

    def as_flat_record(self) -> dict[str, Any]:
        """Flattened row for APIs / JSON-like consumers."""
        self.ensure_metadata()
        fp = Path(self.path)
        base: dict[str, Any] = {
            "path": self.path,
            "relative_path": self.relative_path,
            "file_name": fp.name,
            **self._ancestry_fields(),
            "format": self.format,
            "header_loaded": False,
            "error": None,
            "dims_display": "",
            "shape_display": "",
        }
        if self.format in ("tif", "tiff"):
            if self._header_error is not None:
                base["error"] = self._header_error
                base.update(
                    {
                        "shape": None,
                        "dims": None,
                        "sizes": None,
                        "dtype": None,
                        "num_channels": None,
                        "num_scenes": None,
                        "physical_units": None,
                        "physical_units_labels": None,
                    }
                )
                return base
            if self._header is not None:
                hdr = self._header.as_json_dict()
                base["header_loaded"] = True
                base.update(hdr)
                base["path"] = self.path
                base["relative_path"] = self.relative_path
                base["file_name"] = fp.name
                base.update(self._ancestry_fields())
                base["dims_display"] = _dims_display(hdr.get("dims"))
                base["shape_display"] = _shape_display(hdr.get("shape"))
                return base
            base["header_loaded"] = False
            base.update(
                {
                    "shape": None,
                    "dims": None,
                    "sizes": None,
                    "dtype": None,
                    "num_channels": None,
                    "num_scenes": None,
                    "physical_units": None,
                    "physical_units_labels": None,
                }
            )
            return base
        if self.format == "ome-tiff":
            base["header_loaded"] = False
            base["error"] = _OME_NOT_SUPPORTED_MSG
            base.update(
                {
                    "shape": None,
                    "dims": None,
                    "sizes": None,
                    "dtype": None,
                    "num_channels": None,
                    "num_scenes": None,
                    "physical_units": None,
                    "physical_units_labels": None,
                }
            )
            return base
        if self._header_error is not None:
            base["error"] = self._header_error
            base.update(
                {
                    "shape": None,
                    "dims": None,
                    "sizes": None,
                    "dtype": None,
                    "num_channels": None,
                    "num_scenes": None,
                    "physical_units": None,
                    "physical_units_labels": None,
                }
            )
            return base
        assert self._header is not None
        hdr = self._header.as_json_dict()
        base["header_loaded"] = True
        base.update(hdr)
        base["path"] = self.path
        base["relative_path"] = self.relative_path
        base["file_name"] = fp.name
        base.update(self._ancestry_fields())
        base["dims_display"] = _dims_display(hdr.get("dims"))
        base["shape_display"] = _shape_display(hdr.get("shape"))
        return base


class MyImageList:
    """Catalog image files under a folder with lazy headers and cached loaders.

    Attributes:
        folder: Absolute resolved directory passed to the constructor.
    """

    def __init__(
        self,
        folder: str | Path,
        *,
        find_these_extensions: list[str],
        max_depth: int = 4,
    ) -> None:
        if not find_these_extensions:
            raise ValueError("find_these_extensions must be non-empty")
        if max_depth < 0:
            raise ValueError(f"max_depth must be >= 0, got {max_depth}")
        self.folder = Path(folder).expanduser().resolve()
        self._max_depth = max_depth
        self._allowed_suffixes = _suffix_set_from_find_these(find_these_extensions)
        self._wants_tif = ".tif" in self._allowed_suffixes or ".tiff" in self._allowed_suffixes
        self._rows: list[_CatalogRow] = []
        self._row_by_relative_path: dict[str, _CatalogRow] = {}
        self._loader_cache: dict[str, ImageLoaderBase] = {}
        self._build_rows()

    def _build_rows(self) -> None:
        want_czi = ".czi" in self._allowed_suffixes
        want_oir = ".oir" in self._allowed_suffixes
        for fp in _bounded_file_paths(self.folder, self._max_depth):
            parent_dir, grandparent_dir = _folder_ancestry(fp)
            rel = _relative_path_str(self.folder, fp)
            name_lower = fp.name.lower()
            if self._wants_tif and (
                name_lower.endswith(".ome.tif") or name_lower.endswith(".ome.tiff")
            ):
                row = _CatalogRow(
                    path=str(fp),
                    relative_path=rel,
                    format="ome-tiff",
                    parent_dir=parent_dir,
                    grandparent_dir=grandparent_dir,
                    _header_error=_OME_NOT_SUPPORTED_MSG,
                    _header_attempted=True,
                )
                self._rows.append(row)
                self._row_by_relative_path[rel] = row
                continue
            suf = fp.suffix.lower()
            if suf == ".tif" or suf == ".tiff":
                if not self._wants_tif:
                    continue
                fmt = "tiff" if suf == ".tiff" else "tif"
                row = _CatalogRow(
                    path=str(fp),
                    relative_path=rel,
                    format=fmt,
                    parent_dir=parent_dir,
                    grandparent_dir=grandparent_dir,
                )
                self._rows.append(row)
                self._row_by_relative_path[rel] = row
                continue
            if suf == ".czi" and want_czi:
                row = _CatalogRow(
                    path=str(fp),
                    relative_path=rel,
                    format="czi",
                    parent_dir=parent_dir,
                    grandparent_dir=grandparent_dir,
                )
                self._rows.append(row)
                self._row_by_relative_path[rel] = row
                continue
            if suf == ".oir" and want_oir:
                row = _CatalogRow(
                    path=str(fp),
                    relative_path=rel,
                    format="oir",
                    parent_dir=parent_dir,
                    grandparent_dir=grandparent_dir,
                )
                self._rows.append(row)
                self._row_by_relative_path[rel] = row
                continue

    def __len__(self) -> int:
        return len(self._rows)

    def __iter__(self) -> Iterator[dict[str, Any]]:
        yield from self.header_records()

    def header_records(self) -> list[dict[str, Any]]:
        """One flattened dict per catalog row (lazy OIR/CZI header read).

        Each dict includes ``relative_path`` (POSIX path relative to :attr:`folder`),
        plus filesystem context: ``parent_dir``, ``grandparent_dir``,
        ``parent_name``, ``grandparent_name``, ``file_name``. When a header is
        loaded, it also includes ``ImageHeader.as_json_dict()`` fields plus
        display helpers: ``shape_display``, ``dims_display`` (``physical_units`` and
        ``physical_units_labels`` come from the header as separate fields).
        """
        return [row.as_flat_record() for row in self._rows]

    def get_loader_for_path(self, path: str | Path) -> ImageLoaderBase:
        """Return a cached :class:`ImageLoaderBase` for ``path`` (create on first use).

        Raises:
            ValueError: If ``path`` is not in the catalog, is OME-TIFF, or had a
                prior header read error (no disk retry).
        """
        key = str(Path(path).expanduser().resolve())
        if key in self._loader_cache:
            return self._loader_cache[key]
        row = self._row_for_path(key)
        if row is None:
            raise ValueError(f"Path not in catalog: {path!r}")
        if row.format == "ome-tiff":
            raise ValueError(_OME_NOT_SUPPORTED_MSG)
        row.ensure_metadata()
        if row._header_error is not None:
            raise ValueError(row._header_error)
        loader: ImageLoaderBase
        if row.format == "czi":
            assert row._header is not None
            loader = MyCziImage(row.path, header=row._header)
        elif row.format == "oir":
            assert row._header is not None
            loader = MyOirImage(row.path, header=row._header)
        elif row.format in ("tif", "tiff"):
            if row._header is not None:
                loader = MyTifImage(
                    row.path,
                    header=row._header,
                    load_olympus_header=False,
                )
            else:
                loader = MyTifImage(row.path, load_olympus_header=True)
        else:
            raise ValueError(f"Unsupported catalog format: {row.format!r}")
        self._loader_cache[key] = loader
        return loader

    def get_loader_at_index(self, index: int) -> ImageLoaderBase:
        """Same as :meth:`get_loader_for_path` using the catalog order (sorted paths)."""
        if index < 0 or index >= len(self._rows):
            raise IndexError(f"Catalog index out of range: {index} (len={len(self._rows)})")
        return self.get_loader_for_path(self._rows[index].path)

    def get_loader_for_relative_path(self, relative_path: str) -> ImageLoaderBase:
        """Return a loader for the file identified by catalog-relative ``relative_path``.

        ``relative_path`` matches :meth:`header_records` ``\"relative_path\"`` (POSIX-style).
        """
        row = self._row_for_relative_path(relative_path)
        if row is None:
            raise ValueError(f"Path not in catalog: {relative_path!r}")
        return self.get_loader_for_path(row.path)

    def describe_pixel_load(self, relative_path: str) -> PixelLoadPolicy:
        """Return whether opening a loader / loading pixels is allowed for ``relative_path``.

        Olympus-only TIFF metadata (no pixel read) still yields ``allowed=True`` when
        the header was parsed successfully; shape validation happens when pixels load.
        """
        row = self._row_for_relative_path(relative_path)
        if row is None:
            return PixelLoadPolicy(
                False,
                "not_in_catalog",
                f"Path not in catalog: {relative_path!r}",
            )
        row.ensure_metadata()
        if row.format == "ome-tiff":
            return PixelLoadPolicy(False, "ome_tiff_unsupported", _OME_NOT_SUPPORTED_MSG)
        if row._header_error is not None:
            return PixelLoadPolicy(False, "header_error", row._header_error)
        return PixelLoadPolicy(True, "ok", None)

    def record_for_relative_path(self, relative_path: str) -> dict[str, Any] | None:
        """Return :meth:`_CatalogRow.as_flat_record` for ``relative_path``, or ``None`` if unknown."""
        row = self._row_for_relative_path(relative_path)
        if row is None:
            return None
        return row.as_flat_record()

    def _row_for_path(self, resolved_key: str) -> _CatalogRow | None:
        for row in self._rows:
            if row.path == resolved_key:
                return row
        return None

    def _row_for_relative_path(self, rel: str) -> _CatalogRow | None:
        key = rel.replace("\\", "/").strip()
        return self._row_by_relative_path.get(key)

