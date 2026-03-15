import os
import shutil
from pathlib import Path

from kymflow.core.image_loaders.kym_image_list import KymImageList  # , KymAnalysis
from kymflow.core.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)

def danger_delete_kym_analysis(path, dry_run:bool = True):
    """Delete all kym analysis for all KymImage in the given path."""
    
    # when no flow-analysis/ folder, calls KymAnalysis.import_v0_analysis()
    kymList = KymImageList(path=path, file_extension=".tif", depth=4)
    num_acq_image_json = 0
    num_kym_image_folders = 0

    for _idx, kymImage in enumerate(kymList):
        
        # ka = kymImage.get_kym_analysis()

        # delete acqimage json
        acqimage_json_path = kymImage._get_metadata_path()
        # if acqimage_json_path is not None:
        if os.path.exists(acqimage_json_path):
            num_acq_image_json += 1
            if dry_run:
                logger.info(f'{_idx+1}/{len(kymList)} would delete acqimage json: {acqimage_json_path}')
            else:
                logger.info(f'{_idx+1}/{len(kymList)} DELETING acqimage json: {acqimage_json_path}')
                os.remove(acqimage_json_path)
        
        # delete entire kym analysis folder, folder name is `flow-analysis`
        kym_analysis_folder = kymImage.path.parent / 'flow-analysis'
        if kym_analysis_folder.exists():
            num_kym_image_folders += 1
            if dry_run:
                logger.info(f'  would delete kym analysis folder: {kym_analysis_folder}')
            else:
                logger.info(f'  DELETING kym analysis folder: {kym_analysis_folder}')
                shutil.rmtree(kym_analysis_folder)

    
    # delete (radon_report_db, kym_event_db) in root and .kymflow_hidden
    radon_db_path = Path(path) / 'radon_report_db.csv'
    kym_event_db_path = Path(path) / 'kym_event_db.csv'
    if radon_db_path.exists():
        if dry_run:
            logger.info(f'  would delete radon_report_db: {radon_db_path}')
        else:
            logger.info(f'  DELETING radon_report_db: {radon_db_path}')
        os.remove(radon_db_path)
    if kym_event_db_path.exists():
        if dry_run:
            logger.info(f'  would delete kym_event_db: {kym_event_db_path}')
        else:
            logger.info(f'  DELETING kym_event_db: {kym_event_db_path}')
        os.remove(kym_event_db_path)
    radon_db_hidden_path = Path(path) / '.kymflow_hidden' / 'radon_report_db.csv'
    if radon_db_hidden_path.exists():
        if dry_run:
            logger.info(f'  would delete radon_report_db_hidden: {radon_db_hidden_path}')
        else:
            logger.info(f'  DELETING radon_report_db_hidden: {radon_db_hidden_path}')
        os.remove(radon_db_hidden_path)
    kym_event_db_hidden_path = Path(path) / '.kymflow_hidden' / 'kym_event_db.csv'
    if kym_event_db_hidden_path.exists():
        if dry_run:
            logger.info(f'  would delete kym_event_db_hidden: {kym_event_db_hidden_path}')
        else:
            logger.info(f'  DELETING kym_event_db_hidden: {kym_event_db_hidden_path}')
        os.remove(kym_event_db_hidden_path)

    logger.info(f'=== DONE')
    logger.info(f'num_acq_image_json: {num_acq_image_json}')
    logger.info(f'num_kym_image_folders: {num_kym_image_folders}')

if __name__ == "__main__":
    setup_logging()

    path = '/Users/cudmore/Downloads/kymflow_app/declan_20260313/small-data'
    
    dry_run = False
    danger_delete_kym_analysis(path, dry_run=dry_run)