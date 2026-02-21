# API Contract

This page lists intended public APIs and current semantics.

## Stable Public Surface: `kymflow_zarr`

### `class ZarrDataset`
Import:
```python
from kymflow_zarr import ZarrDataset
```

Constructor:
```python
ZarrDataset(path: str, mode: str = "a", schema: DatasetSchema = DatasetSchema())
```
- Modes:
  - `"r"`: read-only (write methods raise `PermissionError`)
  - `"a"`: read/write create-or-open
  - `"w"`: truncate/create

Record access:
```python
record(image_id: str) -> ZarrImageRecord
list_image_ids() -> list[str]
iter_records(*, order_by: Literal["image_id", "created_utc", "acquired_local_epoch_ns"] = "image_id", missing: Literal["last", "first"] = "last") -> Iterator[ZarrImageRecord]
```

Image lifecycle:
```python
add_image(arr: np.ndarray, *, axes: Sequence[str] | None = None, chunks: tuple[int, ...] | None = None) -> ZarrImageRecord
delete_image(image_id: str) -> None
ingest_image(src_img: Any) -> ZarrImageRecord
```
- `add_image` always generates a UUID image id.
- `ingest_image` expects `getChannelData(1)` or `get_channel(1)` on source.

Manifest APIs:
```python
load_manifest() -> Manifest | None
rebuild_manifest(*, include_analysis_keys: bool = True) -> Manifest
save_manifest(manifest: Manifest) -> None
update_manifest(*, include_analysis_keys: bool = True) -> Manifest
```
- Manifest is derived cache/index, not source of truth.

Dataset tables:
```python
list_table_names() -> list[str]
load_table(name: str) -> pd.DataFrame
save_table(name: str, df: pd.DataFrame) -> None
replace_rows_for_image_id(name: str, image_id: str, df_rows: pd.DataFrame, *, image_id_col: str = "image_id") -> None
load_sources_index() -> pd.DataFrame
save_sources_index(df: pd.DataFrame) -> None
refresh_from_folder(folder: str | Path, pattern: str = "*.tif", *, mode: str = "skip") -> list[str]
```
- `load_table` raises `FileNotFoundError` if missing.
- `replace_rows_for_image_id` requires `image_id_col` in `df_rows`, else `ValueError`.

Import/export:
```python
export_legacy_folder(export_dir: str | Path, *, include_tiff: bool = True, include_tables: bool = True) -> None
ingest_legacy_folder(legacy_root: str | Path, *, pattern: str = "*.tif", include_sidecars: bool = True) -> None
```

Validation:
```python
validate() -> None
validate_image(image_id: str) -> None
```

### `class ZarrImageRecord`
Import:
```python
from kymflow_zarr import ZarrImageRecord
```

Array/group access:
```python
open_group() -> zarr.hierarchy.Group
require_group() -> zarr.hierarchy.Group
group: zarr.hierarchy.Group  # property, read-only safe
open_array() -> zarr.core.Array
load_array() -> np.ndarray
get_axes() -> list[str] | None
save_array(arr: np.ndarray, *, axes: Sequence[str] | None = None, chunks: tuple[int, ...] | None = None, compressor: Any | None = None, overwrite: bool = True, extra_attrs: dict[str, Any] | None = None) -> zarr.core.Array
get_image_bounds() -> dict[str, int]
```
- `group` uses `open_group()`; it does not create paths.
- `save_array` creates/updates record path and attrs.

Metadata payload/object helpers:
```python
save_metadata_payload(payload: dict[str, Any]) -> str
load_metadata_payload() -> dict[str, Any]
save_metadata_objects(*, header: Any | None = None, experiment: Any | None = None, rois: Any | None = None, auto_header_from_array: bool = True, acquired_local_epoch_ns: int | None = None) -> None
load_metadata_objects() -> tuple[Any, Any, Any]
```
- `load_metadata_payload` raises `MetadataNotFoundError` when missing.
- Object methods require `kymflow` metadata/ROI classes importable.

Per-record JSON + tabular artifacts:
```python
save_json(name: str, obj: Any, *, indent: int = 2) -> str
load_json(name: str) -> Any
save_df_parquet(name: str, df: pd.DataFrame, *, compression: str = "zstd") -> str
load_df_parquet(name: str) -> pd.DataFrame
save_df_csv_gz(name: str, df: pd.DataFrame, *, index: bool = False) -> str
load_df_csv_gz(name: str) -> pd.DataFrame
list_analysis_keys() -> list[str]
delete_analysis(*, suffixes: tuple[str, ...] | None = None) -> int
```
- `load_json` read order: `<name>.json` then legacy `<name>.json.gz`.

Per-record array artifacts:
```python
save_array_artifact(name: str, arr: np.ndarray, *, axes: list[str] | None = None, chunks: tuple[int, ...] | None = None) -> None
load_array_artifact(name: str) -> np.ndarray
list_array_artifacts() -> list[str]
```

### `MetadataNotFoundError`
Import:
```python
from kymflow_zarr import MetadataNotFoundError
```
- Raised by `ZarrImageRecord.load_metadata_payload()` when canonical metadata payload is absent.

## Related Public Surface: `kymflow.core.kym_dataset`

### Run marker helpers (`run_marker.py`)
Import:
```python
from kymflow.core.kym_dataset.run_marker import RUN_MARKER_VERSION, make_run_marker, validate_run_marker, marker_matches
```

Signatures:
```python
RUN_MARKER_VERSION: str
make_run_marker(*, indexer_name: str, params_hash: str, analysis_version: str, n_rows: int, ran_utc_epoch_ns: int | None = None, status: str = "ok") -> dict[str, object]
validate_run_marker(d: dict[str, object]) -> None
marker_matches(d: dict[str, object] | None, *, params_hash: str, analysis_version: str) -> bool
```

## Internal / Not Stable
- `experimental_stores/*` classes and interfaces are still evolving.
- Prompt files under `prompts/` are workflow scaffolding, not runtime APIs.
