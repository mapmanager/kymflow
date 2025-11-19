from pathlib import Path
from pprint import pprint

from kymflow_core.kym_file import (
    KymFile,
    ExperimentMetadata,
    OlympusHeader,
    AnalysisParameters,
    _get_analysis_folder_path
)

from kymflow_core.utils.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)

def test_get_analysis_folder_path():
    tif_path = Path("/Users/cudmore/Dropbox/data/declan/data/20221102/Capillary1_0001.tif")
    path = _get_analysis_folder_path(tif_path)
    logger.info(f'analysis folder path: {path}')


# def test_get_analysis_payload_or_load():
#     tif_path = Path("/Users/cudmore/Dropbox/data/declan/data/20221102/Capillary1_0001.tif")
#     kym_file = KymFile(tif_path)
#     payload = kym_file.get_analysis_payload_or_load()
#     logger.info(f'payload: {payload}')

def test_save_analysis():
    tif_path = Path("/Users/cudmore/Dropbox/data/declan/data/20221102/Capillary1_0001.tif")
    kym_file = KymFile(tif_path)
    kym_file.save_analysis()

def test_kym_file():
    tif_path = Path("/Users/cudmore/Dropbox/data/declan/data/20221102/Capillary1_0001.tif")
    kym_file = KymFile(tif_path)
    
    #pprint(kym_file.to_metadata_dict())
    logger.info(f'numlines: {kym_file.num_lines}')
    logger.info(f'pixels_per_line: {kym_file.pixels_per_line}')
    logger.info(f'duration_seconds: {kym_file.duration_seconds}')
    logger.info(f'experiment_metadata: {kym_file.experiment_metadata}')
    # logger.info(f'header: {kym_file.header}')
    # logger.info(f'analysis: {kym_file.analysis}')
    # logger.info(f'analysis_payload: {kym_file.analysis_payload}')
    # logger.info(f'image: {kym_file.image}')

    # logger.info(f'analysis_payload:')
    # pprint(kym_file.get_analysis_payload())

if __name__ == "__main__":
    # test_get_analysis_folder_path()
    # test_kym_file()
    # test_get_analysis_payload_or_load()
    test_save_analysis()