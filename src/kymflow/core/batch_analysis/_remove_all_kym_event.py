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

def getKymFileList(path:str, depth:int = 4):
    path = Path(path)
    parent_dir = path.parent
    # grandparent_dir = p.parent.parent
    
    logger.info(f"building KymImageList: {parent_dir}")
    kymList = KymImageList(path, file_extension=".tif", depth=depth)
    return kymList

def _inspect_kym_event(kymImage:KymImage):

    parent_folder = kymImage.path.parent.name
    grandparent_folder = kymImage.path.parent.parent.name
    rel_path = (grandparent_folder, parent_folder, kymImage.path.name)

    # load an inspect kym analysis kym event
    ka = kymImage.get_kym_analysis()

    _showed_first = False
    for roi_id in kymImage.rois.get_roi_ids():
        # n_user_events = ka.num_user_added_velocity_events(roi_id)
        n_total_events = ka.num_velocity_events(roi_id)
        
        if n_total_events == 0:
            # logger.info(f"  no velocity events for roi {roi_id}")
            continue

        velEvents = ka.get_velocity_report(roi_id)

        if not _showed_first:
            logger.info(f"  {rel_path}")
            _showed_first = True

        logger.info(f"  velocity events for roi {roi_id}: {len(velEvents)}")
        # for velEvent in velEvents:
        #     logger.info(f"  velEvent: {velEvent}")

if __name__ == "__main__":
    path = "/Users/cudmore/Dropbox/data/declan/2026/compare-condiitons/v2-analysis"
    kymList = getKymFileList(path)
    
    # for kymImage in kymList:
    #     _inspect_kym_event(kymImage)