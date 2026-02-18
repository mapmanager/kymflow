"""
Randomize and subsample Declan kymograph data for blinded analysis.

This script uses the kymflow API to:
1. Load kymograph images from a directory using AcqImageList
2. Collect metadata via collect_metadata()
3. Randomize image order within groups (Grandparent Folder)
4. Subsample images per group
5. Export results to CSV files

Future API Extension Opportunities:
- Path utilities: A utility function for computing relative paths could be added to
  kymflow.core.utils.path_utils (see rel_path calculation in _randomize_declan)
- Date utilities: A date string generator could be added to kymflow.core.utils.date_utils
  (currently using inline datetime.now().strftime('%Y%m%d'))
- AcqImageList methods: Grouping, randomization, and subsampling operations could be
  added as methods on AcqImageList (currently implemented as separate functions)
- CSV export: Metadata export with transformations could be added as an AcqImageList
  method (currently using pandas DataFrame operations)
"""

import pandas as pd
import os
from datetime import datetime
from pathlib import Path

from kymflow.core.image_loaders.kym_image_list import KymImageList
from kymflow.core.utils.logging import get_logger, setup_logging
logger = get_logger(__name__)

setup_logging()

def _get_versioned_folder_name(base_folder_name: str) -> str:
    """
    Get a versioned folder name that doesn't already exist.
    
    Checks if base_folder_name exists, and if so, appends version suffixes
    (_v1, _v2, etc.) until finding one that doesn't exist.
    
    Args:
        base_folder_name: str
            Base folder name (e.g., 'declan-random-20250206')
    
    Returns:
        str
            Folder name with version suffix if needed (e.g., 'declan-random-20250206_v1')
    """
    if not os.path.exists(base_folder_name):
        return base_folder_name
    
    # Find the highest existing version
    version = 1
    while os.path.exists(f"{base_folder_name}_v{version}"):
        version += 1
    
    return f"{base_folder_name}_v{version}"

def makeRandomAcqImageList(_random_path: str) -> KymImageList:
    """
    Load randomized CSV file and create a KymImageList.
    
    Uses KymImageList.file_path_list parameter to load images from a CSV file
    containing a 'path' column with full file paths.
    
    Args:
        _random_path: str
            Path to CSV file with 'path' column containing full file paths
    
    Returns:
        KymImageList
            KymImageList instance loaded from CSV paths
    
    Note:
        This function demonstrates using KymImageList with file_path_list parameter.
        Future API extension: KymImageList.load_from_csv() could simplify this pattern.
    """
    df = pd.read_csv(_random_path)
    
    print(df)

    path_list = df['path'].tolist()
    
    # Load from a list of paths using KymImageList API
    # Future API extension: KymImageList.load_from_csv(csv_path) could wrap this
    acqImageList = KymImageList(file_path_list=path_list, file_extension=".tif")

    print(acqImageList)

    return acqImageList

def subsample_from_random_csv(_random_path: str, n: int, output_folder: str | None = None) -> str:
    """
    Load randomized CSV file and subsample n rows per 'Grandparent Folder'.
    
    Uses pandas groupby().sample() to randomly select n rows from each group.
    If a group has fewer than n rows, all rows from that group are included.
    Saves results to a new CSV file with '-n-{n}' suffix.
    
    Args:
        _random_path: str
            Path to the randomized CSV file (must contain 'Grandparent Folder' column)
        n: int
            Number of rows to subsample per 'Grandparent Folder'
        output_folder: str | None
            Optional output folder. If provided, saves the subsampled CSV to this folder.
            If None, saves in the same directory as _random_path.

    Returns:
        str
            Path to the subsampled CSV file
    
    Note:
        This is a script-level function for CSV manipulation.
        Future API extension: AcqImageList.subsample_by_group(group_column, n) could
        provide this functionality at the API level.
    """
    df = pd.read_csv(_random_path)
    
    logger.info('orig df is:')
    
    print(df[['File Name', 'Grandparent Folder', 'path']])


    # Log group information before subsampling
    group_counts = df['Grandparent Folder'].value_counts()
    logger.info(f'Subsampling: {len(group_counts)} groups found')
    logger.info(f'Group sizes: {dict(group_counts)}')
    
    # Sample n rows from each group
    # If a group has fewer than n rows, sample() will return all rows from that group
    df_sampled = df.groupby('Grandparent Folder', group_keys=False).sample(n=n, replace=False)
    
    # Log results after subsampling
    sampled_counts = df_sampled['Grandparent Folder'].value_counts()
    logger.info(f'After subsampling: {len(df_sampled)} total rows')
    logger.info(f'Sampled group sizes: {dict(sampled_counts)}')
    
    # Determine output path
    if output_folder is not None:
        # Use the same filename as input but in the specified output folder
        input_filename = os.path.basename(_random_path)
        _subsampled_filename = input_filename.replace('.csv', f'-n-{n}.csv')
        _subsampled_path = os.path.join(output_folder, _subsampled_filename)
    else:
        # Save to a new CSV with '-n-{n}' suffix in same directory as input
        _subsampled_path = _random_path.replace('.csv', f'-n-{n}.csv')
    
    df_sampled.to_csv(_subsampled_path, index=False)
    
    return _subsampled_path

def _randomize_declan(path: str, results_folder: str, date_str: str) -> str:
    """
    Load kymograph images from a directory, randomize order within groups, and export to CSV.
    
    Process:
    1. Load images using AcqImageList with depth=3
    2. Collect metadata via collect_metadata()
    3. Add relative path column (post-processing step)
    4. Randomize row order within each 'Grandparent Folder' group
    5. Export original and randomized data to CSV files
    
    Args:
        path: str
            Path to directory containing kymograph images (.tif files)
            This path is used as the base for computing relative paths
        results_folder: str
            Output folder name for CSV files (e.g., 'declan-random-20250206_v1')
        date_str: str
            Date string in yyyymmdd format for filename generation

    Returns:
        str
            Path to the randomized CSV file
    
    Note:
        This function demonstrates:
        - Using AcqImageList.collect_metadata() to get all metadata
        - Post-processing metadata DataFrame (adding rel_path, dropping columns)
        - Group-based randomization using pandas operations
        
        Future API extensions:
        - AcqImageList.export_metadata_to_csv() could handle CSV export with options
        - AcqImageList.randomize_by_group() could provide group-based randomization
        - Path utility function could simplify rel_path calculation
    """
    # Create results folder if it doesn't exist
    os.makedirs(results_folder, exist_ok=True)

    # Normalize the base path for relative path calculation
    # This path will be stripped from each file path to create rel_path column
    base_path = Path(path).expanduser().resolve()

    logger.info('loading from raw data path:')
    print(path)
    
    # Load images using KymImageList API
    # depth=3 scans base folder and 2 levels of subfolders
    depth = 3
    kymList = KymImageList(path, file_extension=".tif", depth=depth)

    # Collect metadata using AcqImageList API
    # This returns a list of dictionaries, one per image
    allMetadata = kymList.collect_metadata()
    df = pd.DataFrame(allMetadata)

    logger.info('original df is:')
    print(df[['File Name', 'Parent Folder', 'Grandparent Folder', 'path']])

    # Drop columns that are not needed for analysis
    # These are analysis status columns, not needed for randomization
    df = df.drop(columns=['Analyzed', 'Saved'])

    # Post-processing: Add rel_path column by stripping base_path from each path
    # This creates relative paths that are portable across systems
    # Future API extension: kymflow.core.utils.path_utils.compute_relative_paths() could provide this
    if 'path' in df.columns:
        df['rel_path'] = df['path'].apply(
            lambda p: str(Path(p).relative_to(base_path)) if p and Path(p).is_relative_to(base_path) else p
        )

    # Save original (non-randomized) DataFrame to CSV
    _original_filename = f'original-declan-data-{date_str}.csv'
    df.to_csv(os.path.join(results_folder, _original_filename), index=False)

    # Determine group order based on first appearance in the DataFrame
    # drop_duplicates() preserves first-seen order, maintaining stable group ordering
    group_order = df['Grandparent Folder'].drop_duplicates().tolist()

    nGrandparent = len(group_order)
    randomized_chunks = []  # Collect randomized group dataframes

    # Loop through each grandparent folder in stable, first-seen order
    # This ensures groups appear in the same order as in the original data
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
        # sample(frac=1) shuffles all rows, reset_index() creates clean sequential index
        # Future API extension: AcqImageList.randomize_by_group(group_column) could provide this
        dfRandomGrandparent = (
            dfOriginalGrandparent
            .sample(frac=1)             # Shuffle rows randomly
            .reset_index(drop=True)     # Reset index for this chunk
        )

        # Append shuffled chunk to list
        randomized_chunks.append(dfRandomGrandparent)

    # Concatenate all shuffled chunks into one DataFrame
    # ignore_index=True creates a new sequential index for the combined DataFrame
    df_randomized = (
        pd.concat(randomized_chunks, ignore_index=True)
    )

    logger.info(f'Final randomized dataframe has {len(df_randomized)} rows')

    # Save randomized DataFrame to CSV
    # Future API extension: AcqImageList.export_metadata_to_csv() could handle this
    _random_filename = f'randomized-declan-data-{date_str}.csv'
    _random_path = os.path.join(results_folder, _random_filename)
    df_randomized.to_csv(_random_path, index=False)

    return _random_path


if __name__ == "__main__":
    # Base path to directory containing kymograph images
    path = "/Users/cudmore/Dropbox/data/declan/2026/compare-condiitons/v3-analysis"
    
    # Generate date string in yyyymmdd format
    # Future API extension: kymflow.core.utils.date_utils.get_date_string() could provide this
    date_str = datetime.now().strftime('%Y%m%d')
    
    # Determine output folder with versioning to avoid overwriting existing folders
    # Base folder name: 'declan-random-yyyymmdd'
    base_folder_name = f'declan-random-{date_str}'
    results_folder = _get_versioned_folder_name(base_folder_name)
    logger.info(f'Using output folder: {results_folder}')
    
    # Step 1: Randomize data (run once, then disable)
    # This creates a randomized CSV file with images shuffled within each group
    _randomPath = _randomize_declan(path, results_folder, date_str)
    logger.info(f'Randomized data saved to: {_randomPath}')

    # Step 2: Subsample from randomized CSV
    # Save subsampled CSV to the same versioned folder
    nSamplePerGrandparent = 5
    _subsampledPath = subsample_from_random_csv(_randomPath, nSamplePerGrandparent, output_folder=results_folder)
    logger.info(f'Subsampled n={nSamplePerGrandparent} per group, saved to: "{_subsampledPath}"')

    # Step 3: Load subsampled CSV and create AcqImageList
    # This demonstrates loading images from a CSV file using the kymflow API
    acqImageList = makeRandomAcqImageList(_subsampledPath)
    logger.info(f'Loaded AcqImageList with {len(acqImageList)} images')