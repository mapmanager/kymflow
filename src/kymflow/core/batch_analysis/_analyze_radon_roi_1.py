""" When importing declan tif that has v0 flowanalysis in roi 1

 - for each kym image
 - ensure 1 roi and it is mpRadon_v0

 - add a scond roi
 - analyze with new default v1 radon
 - save
 """

from kymflow.core.image_loaders.kym_image_list import KymImageList
from kymflow.core.utils.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)

def _analyze_flow(path: str, depth:int) -> None:
    """
    Analyze flow for a folder with depth.

    Args:
        path: str
            Path to the folder containing the KymImage files
        depth: int
            Depth of the folder structure

    Returns:
        None
    """

    kymList = KymImageList(path, file_extension=".tif", depth=depth)

    any_changes = False
    for _idx, kymImage in enumerate(kymList):
        
        # logger.info(f'=== {_idx+1}/{len(kymList)}: {kymImage.path}')

        # Delete any existing ROIs (start fresh)
        # deleted_count = kymImage.rois.clear()
        # logger.info(f"Deleted {deleted_count} existing ROI(s)")

        # ensure only 1 roi
        _numRois = kymImage.rois.numRois()
        if _numRois != 1:
            # logger.error(f'{kymImage.path.name} has {_numRois} rois, expected 1')
            continue

        # ensure roi 1 is mpRadon_v0
        meta = kymImage.get_kym_analysis().get_analysis_metadata(1)
        if meta is None or meta.algorithm != "mpRadon_v0":
            # logger.error(f'{kymImage.path.name} roi 1 is not mpRadon_v0, it is {meta.algorithm}')
            continue

        logger.info(f'{kymImage.path.name} has 1 roi and roi 1 is algorithm is: {meta.algorithm}')

        # ensure img data is loaded
        kymImage.load_channel(channel=1)

        # Calculate image stats for all ROIs (required for RadonReport img_min, img_max, etc.)
        for roi_id in kymImage.rois.get_roi_ids():
            roi = kymImage.rois.get(roi_id)
            if roi is not None:
                try:
                    roi.calculate_image_stats(kymImage)
                except ValueError as e:
                    logger.warning(f"Could not calculate image stats for ROI {roi_id}: {e}")


        # windows = [16, 32, 64]
        windows = [16]
        for _idx, window in enumerate(windows):
            # create roi for the window
            roi = kymImage.rois.create_roi()
            logger.info(f'  created roi: {roi.id} to run radon flow analysis')

            roi.calculate_image_stats(kymImage)
            
            # analyze flow
            logger.info(f'   analyze flow for roi {roi.id} window:{window}...')
            kymImage.get_kym_analysis().analyze_roi(roi.id, window)
            any_changes = True

            # update the radon cache
            kymList.update_radon_report_cache_only(kymImage)

        # save analysis
        logger.info(f'  saving analysis for {kymImage.path.name}')
        kymImage.get_kym_analysis().save_analysis()

    if any_changes:
        logger.info('-->> saving kymlist radon report db to csv')
        kymList.save_radon_report_db()
    else:
        logger.info('no changes detected')

if __name__ == "__main__":
    path = "/Users/cudmore/Dropbox/data/declan/2026/compare-condiitons/v3-analysis"
    depth = 3
    _analyze_flow(path, depth)