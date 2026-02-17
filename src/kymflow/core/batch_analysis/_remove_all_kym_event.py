"""Remove all kym analysis
Optionally save each kym image
update kym analysis db and saved csv
"""

from pathlib import Path

from kymflow.core.image_loaders.kym_image_list import KymImageList
from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.utils.logging import get_logger, setup_logging
logger = get_logger(__name__)

setup_logging()

def _delete_all_kym_event(path:str):
    """Delete all kym velocity events for all KymImage in the given path.
    
    if any changes, rebuild velocity event cache and save to CSV
    """
    logger.info(f'loading kymimagelist from path:{path}')
    kymList = KymImageList(file_path_list=path, file_extension=".tif", depth=4)
    
    any_changes = False
    for kymImage in kymList:
        image_needs_saving = False
        ka = kymImage.get_kym_analysis()
        for roi_id in kymImage.rois.get_roi_ids():
            n_total_events = ka.num_velocity_events(roi_id)
            if n_total_events == 0:
                continue
            logger.info("=== removing all velocity events for")
            logger.info(f"  roi {roi_id} n_total_events:{n_total_events} in image {kymImage.get_file_name()}")
            ka.remove_velocity_event(roi_id, remove_these="_remove_all")
            image_needs_saving = True

        if image_needs_saving:
            logger.info(f"  saving analysis for image {kymImage.get_file_name()}")
            ka.save_analysis()
            any_changes = True

    if any_changes:
        logger.info("rebuilding velocity event cache and saving to CSV")
        kymList.rebuild_velocity_event_db_and_save()
    else:
        logger.info("no changes detected")

if __name__ == "__main__":
    reply = input("[[DANGER]] This will modify existing analysis. Do you want to proceed? (y/n): ").strip().lower()
    if reply != "y":
        print("Aborted.")
        raise SystemExit(0)

    # path = "/Users/cudmore/Dropbox/data/declan/2026/compare-condiitons/v2-analysis"
    
    path = '/Users/cudmore/Dropbox/data/declan/2026/compare-condiitons/v2-analysis/randomized-declan-20260208-n-5.csv'

    _delete_all_kym_event(path)