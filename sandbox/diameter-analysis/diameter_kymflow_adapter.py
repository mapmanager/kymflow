"""Compatibility shim for the GUI adapter.

Use ``gui.diameter_kymflow_adapter`` as the canonical adapter module.
"""

from __future__ import annotations

from gui.diameter_kymflow_adapter import (  # noqa: F401
    DEFAULT_CHANNEL_ID,
    DEFAULT_ROI_ID,
    get_channel_ids_for,
    get_kym_by_path,
    get_kym_geometry_for,
    get_kym_physical_size_for,
    get_roi_ids_for,
    get_roi_pixel_bounds_for,
    iter_kym_items,
    list_file_table_kym_images,
    load_channel_for,
    load_kym_list_for_folder,
    require_channel_and_roi,
)
