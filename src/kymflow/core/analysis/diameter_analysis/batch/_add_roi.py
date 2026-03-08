"""Given a folder path, add one roi if it does not exist.
"""
from __future__ import annotations

import os
import logging

logger = logging.getLogger(__name__)

def configure_logging() -> None:

    level = logging.INFO

    root = logging.getLogger()
    if root.handlers:
        root.setLevel(level)
        return

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

def _add_roi(path:str, dry_run:bool):
    """Load a KymImageList, for each kymimage, if no roi then add one roi.
    """
    from kymflow.core.image_loaders.kym_image_list import KymImageList

    kymImageList = KymImageList(path=path)
    logger.info(f'loaded:')
    logger.info(kymImageList)

    for kymImage in kymImageList:
        numRoi = kymImage.rois.numRois()
        logger.info(f'  num roi:{numRoi} for {kymImage.path.name}')

        if numRoi == 0:
            # before we create roi, need image data
            # load channel is idempotence, kymimage holds a pointer during runtime
            # and will not load again, e.g. lazy loading, so we can call load_channel multiple times without penalty
            _loaded = kymImage.load_channel(1)
            if not _loaded:
                logger.error('  kymImage.load_channel failed???')
                continue
            
            new_roi_id = kymImage.rois.create_roi()
            logger.info(f' add roi {new_roi_id}')

            if not dry_run:
                kymImage.save_metadata()
                logger.info(f'  saved acqimage save_metadata for {kymImage.path.name}')

if __name__ == "__main__":
    configure_logging()

    SEED_FOLDER = "/Users/cudmore/Downloads/kymflow_app/cell-shortening/fig1"
    dry_run = False
    _add_roi(SEED_FOLDER, dry_run=dry_run)
