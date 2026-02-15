"""Build and inspect radon_report_db.csv for a KymImageList folder.

Usage:
    cd kymflow && uv run python declan-analysis/build_radon_db.py

This script:
- Loads KymImageList from a hardcoded path
- Verifies radon DB path and state
- Saves a KymAnalysis (if dirty) and inspects the DB
"""

from pathlib import Path

import pandas as pd

from kymflow.core.image_loaders.kym_image_list import KymImageList
from kymflow.core.utils.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)

# Hardcoded path for local testing
FOLDER_PATH = Path(
    "/Users/cudmore/Dropbox/data/declan/2026/compare-condiitons/v2-analysis"
)


def load_and_check_db() -> KymImageList | None:
    """Load KymImageList and verify radon DB path / existence."""
    if not FOLDER_PATH.exists():
        logger.error(f"Folder does not exist: {FOLDER_PATH}")
        return None

    image_list = KymImageList(
        path=FOLDER_PATH,
        file_extension=".tif",
        depth=3,
    )
    db_path = image_list._get_radon_db_path()

    logger.info(f"Loaded {len(image_list)} images from {FOLDER_PATH}")
    logger.info(f"Radon DB path: {db_path}")
    
    saved = image_list.save_radon_report_db()
    logger.info(f"save_radon_report_db() -> {saved}")

    if not saved:
        logger.error("Failed to save radon report DB")
        return None
    if db_path is not None:
        logger.info(f"Radon DB exists: {db_path.exists()}")
    logger.info(f"Cache entries: {len(image_list._radon_report_cache)}")
    if image_list._radon_report_cache:
        total_reports = sum(len(v) for v in image_list._radon_report_cache.values())
        logger.info(f"Total reports in cache: {total_reports}")

    return image_list


def save_analysis_and_inspect_db(image_list: KymImageList) -> None:
    """Save analysis for one image with ROIs and inspect the DB."""
    # Pick first image that has ROIs; prefer one with dirty (unsaved) analysis
    target = None
    dirty_target = None
    for kym_image in image_list:
        roi_ids = kym_image.rois.get_roi_ids()
        ka = kym_image.get_kym_analysis()
        if roi_ids and ka.get_radon_report():
            if ka.is_dirty:
                dirty_target = kym_image
                break
            if target is None:
                target = kym_image

    chosen = dirty_target if dirty_target is not None else target
    if chosen is None:
        logger.warning(
            "No image with ROIs and radon reports found. Skipping save_and_inspect."
        )
        return

    logger.info(f"Selected image: {chosen.path}")
    ka = chosen.get_kym_analysis()

    # Save analysis (same as GUI Save Selected) if dirty
    if ka.is_dirty:
        success = ka.save_analysis()
        logger.info(f"save_analysis() -> {success}")

    # Update radon report cache and persist DB
    image_list.update_radon_report_for_image(chosen)
    logger.info("update_radon_report_for_image() called")

    # Inspect DB
    db_path = image_list._get_radon_db_path()
    if db_path is not None and db_path.exists():
        df = pd.read_csv(db_path)
        logger.info(f"DB has {len(df)} rows, columns: {list(df.columns)}")
        if len(df) > 0:
            logger.info("\nSample row:")
            logger.info(df.iloc[0].to_dict())
    else:
        logger.warning("No DB file to inspect")


def main() -> None:
    """Run load check and optional save+inspect."""
    logger.info("=== load_and_check_db ===")
    image_list = load_and_check_db()
    if image_list is None:
        return

    if 0:
        logger.info("\n=== save_analysis_and_inspect_db ===")
        save_analysis_and_inspect_db(image_list)


if __name__ == "__main__":
    main()
