from kymflow.core.image_loaders.acq_image_list import AcqImageList
from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.utils.logging import get_logger, setup_logging
logger = get_logger(__name__)

def declan_report(path: str) -> None:
    logger.info(f"Generating declan report for {path}")

    depth = 2
    kymList = AcqImageList(path, image_cls=KymImage, file_extension=".tif", depth=depth)
    for kymImage in kymList:
        logger.info(kymImage.path)
        ka = kymImage.get_kym_analysis()
        for roi_id in kymImage.rois.get_roi_ids():
            velEvents = ka.get_velocity_report(roi_id)
            if velEvents is None:
                logger.info(f"no velocity events for roi {roi_id}")
                continue
            logger.info(f"velocity events for roi {roi_id}: {len(velEvents)}")
            for velEvent in velEvents:
                # velocity events are xxx, they do not have roi_id, path, etc
                # velEvent['roi_id'] = roi_id
                # velEvent['path'] = kymImage.path
                # logger.info(f"velEvent: {velEvent}")
                from pprint import pprint
                pprint(velEvent, sort_dicts=False, indent=4)


if __name__ == "__main__":
    setup_logging()
    path = "/Users/cudmore/Dropbox/data/declan/2026/declan-data-analyzed"
    path = '/Users/cudmore/Dropbox/data/declan/2026/data/20251204'

    # analyze_flow(path)

    # analyze_stalls(path)
    
    declan_report(path)