"""
randomize the declan data
"""

import pandas as pd
import random
import os

from kymflow.core.image_loaders.acq_image_list import AcqImageList
from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.utils.logging import get_logger, setup_logging
logger = get_logger(__name__)

setup_logging()

def makeRandomAcqImageList(_random_path:str) -> AcqImageList:
    """
    Load randomized csv file and create an AcqImageList.
    """
    df = pd.read_csv(_random_path)
    
    print(df)

    path_list = df['path'].tolist()
    
    # load from a list of paths (new api 20260206)
    acqImageList = AcqImageList(file_path_list=path_list, image_cls=KymImage, file_extension=".tif")

    print(acqImageList)


    return acqImageList

def subsample_from_random_csv(_random_path:str, n:int) -> str:
    """
    Load randomized csv file and subsample n rows per 'Grandparent Folder'.

    save the results to a csv file named 'randomized-declan-data-subsampled-20260206.csv'
    with the number of rows subsampled per 'Grandparent Folder'.
    
    For example, if n=5, the file will be named:
    'randomized-declan-data-subsampled-20260206-n-5.csv'
    
    Args:
        _random_path: str
            The path to the randomized csv file
        n: int
            The number of rows to subsample per 'Grandparent Folder'

    Returns:
        str
            The path to the subsampled csv file
    """
    df = pd.read_csv(_random_path)
    df = df.groupby('Grandparent Folder').sample(n=n)
    
    # save to a new csv 'randomize-declan-data-subsampled-20260206.csv'
    _subsampled_path = _random_path.replace('.csv', f'-n-{n}.csv')
    df.to_csv(_subsampled_path, index=False)
    
    return _subsampled_path

def _randomize_declan(path: str) -> str:
    """
    Load original kymanalysis from a path
    randomize the order of the rows for each 'Grandparent Folder'
    save the results to a csv file

    Args:
        path: str
            The path to the kymanalysis data

    Returns:
        str
            The path to the randomized csv file
    """

    _dateStr = '20260206b'
    # save results to folder 'declan-random-20260206'
    results_folder = f'declan-random-{_dateStr}'
    os.makedirs(results_folder, exist_ok=True)

    depth = 3
    kymList = AcqImageList(path, image_cls=KymImage, file_extension=".tif", depth=depth)

    # get unique grandparent folder from acqimagelist
    # grandparent_folders = kymList.getRowDict().get('Grandparent Folder').unique()

    allMetadata = kymList.collect_metadata()
    df = pd.DataFrame(allMetadata)

    # drop Analyzed and Saved columns
    df = df.drop(columns=['Analyzed', 'Saved'])

    # save original df to csv
    _original_filename = f'original-declan-data-{_dateStr}.csv'
    df.to_csv(os.path.join(results_folder, _original_filename), index=False)

    # Determine group order based on first appearance in the DataFrame
    # - drop_duplicates() preserves first-seen order
    group_order = df['Grandparent Folder'].drop_duplicates().tolist()

    nGrandparent = len(group_order)
    randomized_chunks = []  # collect randomized group dataframes

    # Loop through each grandparent folder in stable, first-seen order
    for _idx, grandparent_folder in enumerate(group_order):

        # Select rows belonging to this grandparent folder
        dfOriginalGrandparent = df[df['Grandparent Folder'] == grandparent_folder]

        n = len(dfOriginalGrandparent)
        logger.info(
            f'{_idx + 1} of {nGrandparent} '
            f'grandparent_folder:"{grandparent_folder}" '
            f'with {n} kymograph images'
        )

        # Randomize row order within this grandparent folder
        dfRandomGrandparent = (
            dfOriginalGrandparent
            .sample(frac=1)             # shuffle rows
            .reset_index(drop=True)     # reset index for this chunk
        )

        # Append shuffled chunk to list
        randomized_chunks.append(dfRandomGrandparent)

    # Concatenate all shuffled chunks into one DataFrame
    df_randomized = (
        pd.concat(randomized_chunks, ignore_index=True)
    )

    logger.info(f'Final randomized dataframe has {len(df_randomized)} rows')

    # save df_randomized to csv
    _random_filename = f'randomized-declan-data-{_dateStr}.csv'
    _random_path = os.path.join(results_folder, _random_filename)
    df_randomized.to_csv(_random_path, index=False)

    return _random_path


if __name__ == "__main__":
    path = "/Users/cudmore/Dropbox/data/declan/2026/compare-condiitons/v1-analysis"
    
    # do this once, do not repeat
    if 0:
        _randomPath = _randomize_declan(path)
        logger.info(f'build this file once: {_randomPath}')

    # on 20260206 we generate a random file named
    # declan-random-20260206b/randomized-declan-data-20260206b.csv

    _randomPath = 'declan-random-20260206b/randomized-declan-data-20260206b.csv'
    
    nSamplePerGrandparent = 5
    _subsampledPath = subsample_from_random_csv(_randomPath, nSamplePerGrandparent)
    logger.info(f'subsampled n={nSamplePerGrandparent} file: "{_subsampledPath}"')

    makeRandomAcqImageList(_subsampledPath)