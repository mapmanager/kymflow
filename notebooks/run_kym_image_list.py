"""Debug script for KymImageList and _radon_report_cache.

Run from CLI: uv run python notebooks/run_kym_image_list.py

Linear script for manual debugging. No CLI arguments.
"""

from __future__ import annotations

from pathlib import Path

from kymflow.core.image_loaders.kym_image_list import KymImageList
from kymflow.core.utils.hidden_cache_paths import get_hidden_cache_path
from kymflow.core.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)


def run() -> None:
    # Hardcoded path for debugging
    
    # folder path
    path = "/Users/cudmore/Desktop/kymflow-stall/declan-stall-v1"

    # random csv path
    path = '/Users/cudmore/Desktop/kymflow-stall/declan-stall-v1/declan-random-v1.csv'

    path_resolved = Path(path).resolve()
    print("=" * 80)
    print("KymImageList debug script")
    print("=" * 80)

    # Step 1: Load KymImageList (use load_from_path as recommended external API; it calls __init__ internally)
    print("\n--- Step 1: Load KymImageList ---")
    print(f"path: {path}")
    print(f"path exists: {path_resolved.exists()}")
    print(f"path is_dir: {path_resolved.is_dir()}")
    kil = KymImageList.load_from_path(path)

    # Step 2: Basic attributes
    print("\n--- Step 2: Basic attributes ---")
    print(f"len(kil): {len(kil)}")
    print(f"kil.images count: {len(kil.images) if hasattr(kil, 'images') else 'N/A'}")

    # Step 3: Mode and paths (affects _get_radon_db_path)
    print("\n--- Step 3: Mode and DB paths ---")
    mode = kil._get_mode() if hasattr(kil, "_get_mode") else "N/A"
    print(f"_get_mode(): {mode}")
    print(f"_folder: {getattr(kil, '_folder', 'N/A')}")
    db_path = kil._get_radon_db_path() if hasattr(kil, "_get_radon_db_path") else None
    print(f"_get_radon_db_path(): {db_path}")
    if db_path is not None:
        hidden_path = get_hidden_cache_path(db_path)
        print(f"hidden cache path: {hidden_path}")
        print(f"hidden cache exists: {hidden_path.exists()}")

    # Step 4: _radon_report_cache (main focus)
    print("\n--- Step 4: _radon_report_cache ---")
    cache = getattr(kil, "_radon_report_cache", None)
    if cache is None:
        print("_radon_report_cache: attribute not found")
    else:
        print(f"_radon_report_cache type: {type(cache)}")
        print(f"_radon_report_cache len (keys): {len(cache)}")
        if cache:
            for k, v in list(cache.items())[:5]:
                print(f"  key={k!r} -> {len(v)} reports")
            if len(cache) > 5:
                print(f"  ... and {len(cache) - 5} more keys")
        else:
            print("_radon_report_cache is EMPTY")

    # Step 5: Compare get_radon_report_df() vs get_velocity_event_df() (reproduces GUI behavior)
    print("\n--- Step 5: get_radon_report_df() vs get_velocity_event_df() ---")
    df_radon = kil.get_radon_report_df()
    df_velocity = kil.get_velocity_event_df() if hasattr(kil, "get_velocity_event_df") else None
    print(f"get_radon_report_df(): shape={df_radon.shape}, empty={df_radon.empty}")
    if df_velocity is not None:
        print(f"get_velocity_event_df(): shape={df_velocity.shape}, empty={df_velocity.empty}")
    else:
        print("get_velocity_event_df(): not available")
    if not df_radon.empty:
        print(f"  radon df head:\n{df_radon.head()}")
    else:
        print("  radon df is EMPTY (same as GUI bug)")
    if df_velocity is not None and not df_velocity.empty:
        print(f"  velocity df head:\n{df_velocity.head()}")
    else:
        print("  velocity df is empty")

    # Step 6: Cache key vs image.path match (explains empty radon when keys mismatch)
    print("\n--- Step 6: Cache key vs image.path match (radon path lookup) ---")
    cache = getattr(kil, "_radon_report_cache", {})
    if cache and kil.images:
        cache_keys = list(cache.keys())[:3]
        img_paths = [str(img.path) for img in kil.images[:3] if img.path is not None]
        print(f"Sample cache keys: {cache_keys}")
        print(f"Sample image.path: {img_paths}")
        matches = [kp in cache for kp in img_paths]
        print(f"image.path in cache?: {matches}")

    # Step 7: First few images (path, kym_analysis, radon)
    print("\n--- Step 7: Sample images ---")
    for i, img in enumerate(kil.images[:3]):
        print(f"\n  image[{i}]: path={img.path}")
        ka = img.get_kym_analysis() if hasattr(img, "get_kym_analysis") else None
        radon = ka.get_analysis_object("RadonAnalysis") if ka else None
        print(f"    kym_analysis: {ka is not None}")
        print(f"    RadonAnalysis: {radon is not None}")
        if radon is not None:
            print(f"    radon._analysis_metadata keys: {list(radon._analysis_metadata.keys())[:5]}")
        rois = img.rois.get_roi_ids() if hasattr(img, "rois") else []
        print(f"    roi_ids: {rois}")

    # Step 8: get_radon_report() result
    print("\n--- Step 8: get_radon_report() ---")
    reports = kil.get_radon_report() if hasattr(kil, "get_radon_report") else []
    print(f"get_radon_report() count: {len(reports)}")
    if reports:
        r0 = reports[0]
        print(f"  first report: roi_id={r0.roi_id}, channel={getattr(r0, 'channel', 'N/A')}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    setup_logging()
    run()
