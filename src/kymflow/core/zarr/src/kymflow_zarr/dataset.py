# Filename: src/kymflow_zarr/dataset.py
"""ZarrDataset: dataset-level API.

Provides:
  - Open/create dataset (Zarr v2 directory store)
  - Schema versioning + validation
  - ZarrImageRecord object layer
  - Dataset-level manifest (index/manifest.json.gz)

Design notes:
  - `add_image(...)` always generates a uuid4 id (v0.1 safety).
  - Deletions are explicit via `delete_image(image_id)`.
  - `ingest_image(src_img)` is a high-level ingest helper for AcqImage-like objects.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Iterator, Optional, Sequence, Literal
from uuid import uuid4

import numpy as np
import pandas as pd
import zarr
from zarr.storage import DirectoryStore

from .io_export import export_legacy_folder as _export_legacy_folder
from .io_import import SOURCES_COLUMNS, ingest_legacy_file as _ingest_legacy_file, ingest_legacy_folder as _ingest_legacy_folder
from .manifest import Manifest, load_manifest, rebuild_manifest, save_manifest
from .record import ZarrImageRecord
from .schema import DatasetSchema
from .utils import normalize_id, require_pyarrow, utc_now_iso


OrderBy = Literal["image_id", "created_utc", "acquired_local_epoch_ns"]


@dataclass
class ZarrDataset:
    """High-level wrapper for a Zarr v2 dataset on disk.

    Args:
        path: Path to a .zarr directory (created if mode allows).
        mode: Zarr open mode ('r', 'a', 'w').
        schema: DatasetSchema defining format name + schema_version.

    Notes:
        Root attributes used:
            format: schema.format_name
            schema_version: schema.schema_version
            created_utc, updated_utc: timestamps for bookkeeping
    """

    path: str
    mode: str = "a"
    schema: DatasetSchema = DatasetSchema()

    def __post_init__(self) -> None:
        self.store = DirectoryStore(self.path)
        self.root = zarr.open_group(store=self.store, mode=self.mode)

        if self.mode in ("a", "w"):
            now = utc_now_iso()
            self.root.attrs.setdefault("format", self.schema.format_name)
            self.root.attrs.setdefault("schema_version", int(self.schema.schema_version))
            self.root.attrs.setdefault("created_utc", now)
            self.root.attrs["updated_utc"] = now

            # Ensure top-level groups exist
            self.root.require_group("images")
            self.root.require_group("index")

    # ---- Validation ----
    def validate(self) -> None:
        """Validate dataset against schema."""
        self.schema.validate_root(self.root)

    def validate_image(self, image_id: str) -> None:
        """Validate a specific image record."""
        self.schema.validate_image_record(self.root, image_id)

    # ---- Records ----
    def record(self, image_id: str) -> ZarrImageRecord:
        """Get a ZarrImageRecord wrapper for an image id."""
        return ZarrImageRecord(self.root, image_id)

    def list_image_ids(self) -> list[str]:
        """List image ids currently present under /images."""
        images = self.root.get("images", None)
        if images is None:
            return []
        return sorted(images.group_keys())

    def iter_records(self, *, order_by: OrderBy = "image_id", missing: Literal["last", "first"] = "last") -> Iterator[ZarrImageRecord]:
        """Iterate records in a deterministic order.

        Args:
            order_by: Field to order by. Uses manifest if present.
            missing: Placement for missing sort keys (only relevant for acquired_local_epoch_ns).

        Yields:
            ZarrImageRecord objects.
        """
        m = self.load_manifest()
        if m is None:
            # fallback
            for image_id in self.list_image_ids():
                yield self.record(image_id)
            return

        def sort_key(rec: dict[str, Any]) -> Any:
            if order_by == "image_id":
                return rec.get("image_id", "")
            if order_by == "created_utc":
                return rec.get("created_utc", "") or ""
            if order_by == "acquired_local_epoch_ns":
                val = rec.get("acquired_local_epoch_ns")
                if val is None:
                    return (1 if missing == "last" else -1, 0)
                return (0, int(val))
            return rec.get("image_id", "")

        for rec_d in sorted(m.images, key=sort_key):
            yield self.record(str(rec_d["image_id"]))

    def add_image(
        self,
        arr: np.ndarray,
        *,
        axes: Sequence[str] | None = None,
        chunks: tuple[int, ...] | None = None,
    ) -> ZarrImageRecord:
        """Add a new image record (uuid4 id) and save its pixels.

        Args:
            arr: N-dimensional numpy array (2D..5D).
            axes: Optional axes labels. If omitted, inferred from arr.ndim.
            chunks: Optional chunk shape. If omitted, inferred from shape+axes.

        Returns:
            ZarrImageRecord for the newly added image.
        """
        if self.mode == "r":
            raise PermissionError("Dataset opened read-only; cannot add images")
        image_id = str(uuid4())
        rec = self.record(image_id)
        rec.save_array(arr, axes=axes, chunks=chunks, overwrite=True)
        # record created_utc is set by rec.save_array; touch dataset updated_utc too
        self._touch_updated()
        return rec

    def delete_image(self, image_id: str) -> None:
        """Delete an image record group and all its artifacts."""
        if self.mode == "r":
            raise PermissionError("Dataset opened read-only; cannot delete images")
        grp_path = f"images/{image_id}"
        if grp_path in self.root:
            del self.root[grp_path]
        # remove any remaining analysis keys in store
        prefix = f"images/{image_id}/analysis/"
        for k in list(self.store.keys()):
            if k.startswith(prefix):
                del self.store[k]
        self._touch_updated()

    def ingest_image(self, src_img: Any) -> ZarrImageRecord:
        """Ingest an AcqImage-like object into this dataset.

        The source image must provide:
            - getChannelData(channel:int=1) -> np.ndarray   (or get_channel)
            - header/experiment/roi accessors OR metadata payload

        This method is designed to be called from GUI-level code using AcqImageV01.

        Args:
            src_img: Source image object (typically AcqImageV01).

        Returns:
            The newly created record.
        """
        # pixels
        if hasattr(src_img, "getChannelData"):
            arr = src_img.getChannelData(1)
        elif hasattr(src_img, "get_channel"):
            arr = src_img.get_channel(1)
        else:
            raise TypeError("src_img must provide getChannelData(1) or get_channel(1)")

        rec = self.add_image(arr)

        # metadata objects/payload (optional)
        header = src_img.getHeader() if hasattr(src_img, "getHeader") else None
        experiment = src_img.getExperimentMetadata() if hasattr(src_img, "getExperimentMetadata") else None
        rois = src_img.rois() if hasattr(src_img, "rois") else None

        acquired_ns = None
        if header is not None and hasattr(header, "acquired_local_epoch_ns"):
            acquired_ns = getattr(header, "acquired_local_epoch_ns")

        if header is not None or experiment is not None or rois is not None:
            rec.save_metadata_objects(
                header=header,
                experiment=experiment,
                rois=rois,
                auto_header_from_array=True,
                acquired_local_epoch_ns=acquired_ns,
            )
            return rec

        if hasattr(src_img, "load_metadata_payload"):
            payload = src_img.load_metadata_payload()
            if payload:
                rec.save_metadata_payload(payload)
                return rec

        return rec

    # ---- Manifest ----
    def load_manifest(self) -> Optional[Manifest]:
        """Load manifest if present."""
        return load_manifest(self.store)

    def rebuild_manifest(self, *, include_analysis_keys: bool = True) -> Manifest:
        """Rebuild manifest by scanning dataset and store keys."""
        return rebuild_manifest(self.root, include_analysis_keys=include_analysis_keys)

    def save_manifest(self, manifest: Manifest) -> None:
        """Save manifest to store."""
        save_manifest(self.store, manifest)
        self._touch_updated()

    def update_manifest(self, *, include_analysis_keys: bool = True) -> Manifest:
        """Rebuild and save the manifest."""
        m = self.rebuild_manifest(include_analysis_keys=include_analysis_keys)
        self.save_manifest(m)
        return m

    # ---- Dataset-level tables ----
    def _table_key(self, name: str) -> str:
        safe = normalize_id(name)
        return f"tables/{safe}.parquet"

    def list_table_names(self) -> list[str]:
        """List dataset-level table names stored under tables/*.parquet."""
        out: list[str] = []
        for k in self.store.keys():
            if not k.startswith("tables/") or not k.endswith(".parquet"):
                continue
            out.append(k[len("tables/") : -len(".parquet")])
        return sorted(out)

    def load_table(self, name: str) -> pd.DataFrame:
        """Load a dataset-level Parquet table."""
        require_pyarrow()
        key = self._table_key(name)
        if key not in self.store:
            raise FileNotFoundError(f"Missing dataset table: {name}")
        return pd.read_parquet(BytesIO(self.store[key]))

    def save_table(self, name: str, df: pd.DataFrame) -> None:
        """Save a dataset-level table as Parquet bytes."""
        require_pyarrow()
        key = self._table_key(name)
        buf = BytesIO()
        df.to_parquet(buf, index=False)
        self.store[key] = buf.getvalue()
        self._touch_updated()

    def replace_rows_for_image_id(
        self,
        name: str,
        image_id: str,
        df_rows: pd.DataFrame,
        *,
        image_id_col: str = "image_id",
    ) -> None:
        """Replace rows in a dataset table for a specific image_id."""
        if image_id_col not in df_rows.columns:
            raise ValueError(f"df_rows must contain column '{image_id_col}'")
        try:
            existing = self.load_table(name)
        except FileNotFoundError:
            existing = pd.DataFrame(columns=list(df_rows.columns))

        if image_id_col in existing.columns:
            existing = existing[existing[image_id_col] != image_id].copy()

        merged = pd.concat([existing, df_rows], ignore_index=True)
        self.save_table(name, merged)

    def load_sources_index(self) -> pd.DataFrame:
        """Load dataset sources index table.

        Returns:
            DataFrame with columns:
                source_primary_path, image_id, source_mtime_ns, source_size_bytes, ingested_epoch_ns
            Returns empty DataFrame with required columns if the table does not exist yet.
        """
        try:
            df = self.load_table("sources")
        except FileNotFoundError:
            return pd.DataFrame(columns=SOURCES_COLUMNS)

        for col in SOURCES_COLUMNS:
            if col not in df.columns:
                df[col] = pd.Series(dtype="object")
        return df[SOURCES_COLUMNS].copy()

    def save_sources_index(self, df: pd.DataFrame) -> None:
        """Save dataset sources index table."""
        for col in SOURCES_COLUMNS:
            if col not in df.columns:
                raise ValueError(f"sources index missing required column: {col}")
        self.save_table("sources", df[SOURCES_COLUMNS].copy())

    def refresh_from_folder(
        self,
        folder: str | Path,
        pattern: str = "*.tif",
        *,
        mode: str = "skip",
    ) -> list[str]:
        """Refresh ingest from a folder by adding only new (or changed) TIFF files.

        Args:
            folder: Legacy folder to scan recursively.
            pattern: Glob pattern for TIFF files.
            mode: Ingest behavior.
                - "skip": ingest files not present in sources index.
                - "reingest_if_changed": ingest files that are new or whose mtime/size changed.

        Returns:
            List of newly ingested image_id values.
        """
        if mode not in {"skip", "reingest_if_changed"}:
            raise ValueError(f"Unsupported refresh mode: {mode}")

        source_df = self.load_sources_index()
        existing_paths = set(source_df["source_primary_path"].astype(str)) if len(source_df) else set()

        ingested_ids: list[str] = []
        new_rows: list[dict[str, int | str]] = []

        root = Path(folder).resolve()
        for tif_path in sorted(root.rglob(pattern)):
            if not tif_path.is_file():
                continue
            src_path = str(tif_path.resolve())

            should_ingest = False
            if src_path not in existing_paths:
                should_ingest = True
            elif mode == "reingest_if_changed":
                stat = tif_path.stat()
                mtime_ns = int(getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000)))
                size_b = int(stat.st_size)
                latest = source_df[source_df["source_primary_path"] == src_path].tail(1)
                if len(latest) == 0:
                    should_ingest = True
                else:
                    old_mtime = int(latest.iloc[0]["source_mtime_ns"])
                    old_size = int(latest.iloc[0]["source_size_bytes"])
                    should_ingest = (mtime_ns != old_mtime) or (size_b != old_size)

            if not should_ingest:
                continue

            image_id, row = _ingest_legacy_file(self, tif_path, include_sidecars=True)
            ingested_ids.append(image_id)
            new_rows.append(row)

        if new_rows:
            new_df = pd.DataFrame(new_rows, columns=SOURCES_COLUMNS)
            merged = pd.concat([source_df, new_df], ignore_index=True)
            self.save_sources_index(merged)
            self.update_manifest()

        return ingested_ids

    # ---- Import / export ----
    def export_legacy_folder(
        self,
        export_dir: str | Path,
        *,
        include_tiff: bool = True,
        include_tables: bool = True,
    ) -> None:
        """Export dataset records/artifacts/tables to TIFF+CSV+JSON folder layout."""
        _export_legacy_folder(self, export_dir, include_tiff=include_tiff, include_tables=include_tables)

    def ingest_legacy_folder(
        self,
        legacy_root: str | Path,
        *,
        pattern: str = "*.tif",
        include_sidecars: bool = True,
    ) -> None:
        """One-time ingest from legacy TIFF + sidecar folder structure."""
        rows = _ingest_legacy_folder(self, legacy_root, pattern=pattern, include_sidecars=include_sidecars)
        if not rows:
            return

        source_df = self.load_sources_index()
        new_df = pd.DataFrame([r for _, r in rows], columns=SOURCES_COLUMNS)
        merged = pd.concat([source_df, new_df], ignore_index=True)
        self.save_sources_index(merged)
        self.update_manifest()

    # ---- Internals ----
    def _touch_updated(self) -> None:
        self.root.attrs["updated_utc"] = utc_now_iso()
