"""
Using declan folder conventions

 parent folder: date
 grandparent folder: treatment

 special cases for each grandparent folder in _declan_folder_mapping: {}
"""

from typing import Dict

from kymflow.core.image_loaders.kym_image_list import KymImageList
from kymflow.core.utils.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)

_declan_folder_mapping: Dict[str, Dict[str, str]] = {
    "14d Saline": {
        "condition": "Control",
        "treatment": "14d Saline",
    },
    "28d AngII": {
        "condition": "AngII",
        "treatment": "28d AngII",
    },
    "28d AngII + Recovery": {
        "condition": "AngII",
        "treatment": "28d AngII + Recovery",
    },
    "28d Saline": {
        "condition": "Control",
        "treatment": "28d Saline",
    },
    "28d Saline + Recovery": {
        "condition": "Control",
        "treatment": "28d Saline + Recovery",
    },
}

def _add_metadata_from_folder(path: str):
    """
    Add metadata from folder to all KymImage in the given path.

    For declan data folders:
    - parent folder is date
    - grandparent folder is treatment (infer condition from (control, AngII))
    - special cases for each grandparent folder in _declan_folder_mapping
    - add metadata to all KymImage in the given path
    - save metadata to all KymImage in the given path

    Args:
        path: str
            Path to the folder containing the KymImage files

    Returns:
        None
    """
    kymList = KymImageList(path, file_extension=".tif", depth=3)
    for kymImage in kymList:
        if kymImage.path is None:
            logger.error(f'{kymImage.path} is None')
            continue
        
        # get mapping from kymImage grandparent_folder
        # parent_folder is date
        # grandparent_folder is treatment
        parent_folder, grandparent_folder, _ = kymImage._compute_parents_from_path(kymImage.path)

        if grandparent_folder is None:
            logger.error("Skipping %s: no grandparent folder", kymImage.path)
            continue

        mapping = _declan_folder_mapping.get(grandparent_folder, {})
        if mapping:
            kymImage.experiment_metadata.condition = mapping.get("condition", "")
            kymImage.experiment_metadata.treatment = mapping.get("treatment", "")
            kymImage.experiment_metadata.date = parent_folder
            kymImage.save_metadata()
        else:
            logger.error(f' no mapping for {grandparent_folder}, expected keys are {_declan_folder_mapping.keys()}')

if __name__ == "__main__":

    path = "/Users/cudmore/Dropbox/data/declan/2026/compare-condiitons/v2-analysis"

    _add_metadata_from_folder(path)