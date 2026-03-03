# External Kymograph API Guide

This document describes the **recommended way for external tools and analysis
code** to access kymograph images using the kymflow image loader APIs.

It is intended for:

- Human developers integrating kymflow into other projects.
- LLMs generating analysis code that uses kym images.

## 1. Core concepts

- `AcqImage` / `AcqImageList` are the **generic image and image-list APIs**.
- `KymImage` / `KymImageList` are **specialized for kymographs**, but should be
  used **via the AcqImage/AcqImageList API** in most external code.
- Kymograph semantics (when using KymImage and KymImageList):

  - `header.shape == (num_lines, pixels_per_line)`
    - axis 0 (rows) is **time**
    - axis 1 (columns) is **space**
  - `header.voxels == (seconds_per_line, micrometers_per_pixel)`

- Images are created **without loading pixel data**; channel data is loaded
  lazily via `load_channel()` / `getChannelData()`.

- **ROIs** are rectangular regions in the image (row/col pixel bounds). For
  `KymImage` (from KymImageList), metadata and ROIs are loaded automatically
  during construction. For other AcqImage subclasses, call `acq.load_metadata()`
  first if ROIs are needed.

- **Channels** are 1-based integer IDs. Use `channels_available()` or
  `get_channel_ids()` to list available channels; use `load_channel()` then
  `getChannelData()` for lazy loading.

## 2. Recommended usage recipe

### 2.1 Load a kymograph list (lazy)

```python
from kymflow.core.api.kym_external import load_kym_list

klist = load_kym_list("/path/to/kymographs")  # no image data loaded yet
```

### 2.2 Find a specific kymograph by path

```python
from kymflow.core.api.kym_external import get_kym_by_path

kimg = get_kym_by_path(klist, "/path/to/kymographs/foo.tif")
if kimg is None:
    raise RuntimeError("kym image not found")
```

### 2.3 Get geometry, voxel sizes, and physical extents

```python
from kymflow.core.api.kym_external import get_kym_geometry, get_kym_physical_size

(shape, dt, dx) = get_kym_geometry(kimg)
(num_lines, pixels_per_line) = shape

(duration_s, length_um) = get_kym_physical_size(kimg)
```

Semantics:

- `shape == (num_lines, pixels_per_line)`
- `dt` = seconds per line (time axis voxel size)
- `dx` = micrometers per pixel (space axis voxel size)
- `duration_s` = total time in seconds (for plotting y-axis range)
- `length_um` = total scan length in micrometers (for plotting x-axis range)

### 2.4 Lazy load channel data

```python
from kymflow.core.api.kym_external import load_kym_channel

img = load_kym_channel(kimg, channel=1)  # np.ndarray, shape matches header.shape
```

- The first call to `load_kym_channel` will load from disk.
- Subsequent calls for the same channel are **no-ops** and return cached data.

### 2.5 Channels

```python
from kymflow.core.api.kym_external import get_channel_ids, load_kym_channel

channel_ids = get_channel_ids(kimg)  # e.g. [1, 2]
arr = load_kym_channel(kimg, channel=1)
```

- `get_channel_ids(acq)` returns available channel IDs (1-based).
- `load_kym_channel(acq, channel)` loads and returns the numpy array.

### 2.6 ROIs (rectangular regions)

```python
from kymflow.core.api.kym_external import (
    get_roi_ids,
    get_roi_pixel_bounds,
    get_roi_physical_bounds,
    RoiPixelBounds,
    create_roi,
    edit_roi,
    delete_roi,
)

ids = get_roi_ids(kimg)
for roi_id in ids:
    bounds = get_roi_pixel_bounds(kimg, roi_id)
    # bounds.row_start, bounds.row_stop, bounds.col_start, bounds.col_stop

phys = get_roi_physical_bounds(kimg, roi_id)
# phys.axis0_start, phys.axis0_stop (time for kymographs)
# phys.axis1_start, phys.axis1_stop (space for kymographs)

# Create ROI
new_bounds = create_roi(kimg, bounds=RoiPixelBounds(0, 10, 0, 20))
edit_roi(kimg, roi_id, bounds=RoiPixelBounds(5, 15, 5, 25))
delete_roi(kimg, roi_id)
```

- ROIs use `RoiPixelBounds` (row_start, row_stop, col_start, col_stop) and
  `RoiPhysicalBounds` (axis0_start/stop, axis1_start/stop in physical units).

## 3. What to avoid

When writing new analysis code or external integrations:

- Prefer the **generic AcqImage/AcqImageList API** and the helpers in
  `kymflow.core.api.kym_external`.
- **Avoid** directly indexing `header.shape` and `header.voxels` in external code;
  use `get_kym_geometry()` and `get_kym_physical_size()` instead.
- **Avoid using these KymImage-specific convenience properties** in external
  modules:

  - `KymImage.num_lines`
  - `KymImage.pixels_per_line`
  - `KymImage.seconds_per_line`
  - `KymImage.um_per_pixel`

  They are thin wrappers over `header.shape` and `header.voxels` and are kept
  mainly for backwards compatibility and internal readability.

## 4. LLM guidance

When generating new code that uses kym images:

- Import from `kymflow.core.api.kym_external`:

  - `load_kym_list`, `get_kym_by_path`, `get_kym_geometry`, `get_kym_physical_size`
  - `load_kym_channel`, `get_channel_ids`
  - `get_roi_ids`, `get_roi_pixel_bounds`, `get_roi_physical_bounds`
  - `create_roi`, `edit_roi`, `delete_roi`, `RoiPixelBounds`, `RoiPhysicalBounds`

- Treat `KymImage` and `KymImageList` as concrete implementations, but base your
  logic on the **AcqImage/AcqImageList-style API** and the helpers above.
- Do not depend on additional KymImage convenience properties from external
  modules.
