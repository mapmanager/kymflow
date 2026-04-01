from pathlib import Path
import os
import sys
from typing import Iterable

import pandas as pd

from kymflow.core.image_loaders.kym_image_list import KymImageList
from kymflow.core.utils.logging import get_logger, setup_logging

from kymflow.core.analysis.heart_rate.heart_rate_pipeline import HRAnalysisConfig
from kymflow.core.analysis.heart_rate.heart_rate_pipeline import HeartRateAnalysis
from pprint import pprint

logger = get_logger(__name__)
setup_logging()

def _append_hr_columns(
    src_df: pd.DataFrame,
    hr_df: pd.DataFrame,
    *,
    key_cols: Iterable[str] = ("rel_path", "roi_id"),
    prefix: str = "hr_",
) -> pd.DataFrame:
    """Append heart-rate (HR) report columns to an existing dataframe by key.

    This function performs a left-join style augmentation of `src_df` with HR results
    stored in `hr_df`, matching rows by a composite key (default: (`rel_path`, `roi_id`)).

    It is designed for the common pipeline case where you have:
      - `src_df`: an existing table with many columns you want to preserve
      - `hr_df`: a table of HR analysis summaries (one row per (rel_path, roi_id))
    and you want to add the HR columns onto the corresponding rows of `src_df`
    without mutating or re-adding the key columns.

    Rules / behavior:
      1) Match rows using `key_cols`. `src_df` is preserved (left join).
      2) For each non-key column in `hr_df`, append it to `src_df` using a prefixed
         name: `f"{prefix}{col}"`.
      3) The key columns in `hr_df` are NOT appended (since they already exist in `src_df`).
      4) If any prefixed HR column already exists in `src_df`, raise `ValueError`
         (refuse to overwrite).
      5) If `hr_df` contains keys not found in `src_df`, log a warning. Those HR rows
         are ignored.
      6) Rows in `src_df` that have no matching HR row will have NaN in the new HR columns.
      7) Returns a new dataframe; does not modify `src_df` in-place.

    Args:
        src_df: Source dataframe to augment. Must contain all `key_cols`.
        hr_df: HR summary dataframe. Must contain all `key_cols` plus HR columns.
        key_cols: Column names used to match rows between dataframes. Default is
            ("rel_path", "roi_id").
        prefix: Prefix added to each appended HR column name (default "hr_").

    Returns:
        A new dataframe containing all columns from `src_df` plus appended HR columns
        prefixed with `prefix`.

    Raises:
        KeyError: If any key column in `key_cols` is missing from either dataframe.
        ValueError: If any target prefixed HR column already exists in `src_df`.

    """

    key_cols = list(key_cols)

    for c in key_cols:
        if c not in src_df.columns:
            raise KeyError(f"src_df missing key column {c!r}")
        if c not in hr_df.columns:
            raise KeyError(f"hr_df missing key column {c!r}")

    hr_value_cols = [c for c in hr_df.columns if c not in key_cols]
    rename_map = {c: f"{prefix}{c}" for c in hr_value_cols}

    collisions = [v for v in rename_map.values() if v in src_df.columns]
    if collisions:
        raise ValueError(f"HR columns already exist in src_df: {collisions}")

    hr_small = hr_df[key_cols + hr_value_cols].rename(columns=rename_map)

    # Log warnings for HR rows with no match in src_df
    src_keys = set(map(tuple, src_df[key_cols].astype(object).to_numpy()))
    hr_keys = list(map(tuple, hr_df[key_cols].astype(object).to_numpy()))
    missing = [k for k in hr_keys if k not in src_keys]
    if missing:
        logger.warning(
            "No matching src_df row for %d HR rows. First few: %s",
            len(missing),
            missing[:10],
        )

    # Left merge: preserves src_df rows, adds hr_ columns when present, else NaN
    out = src_df.merge(hr_small, on=key_cols, how="left")

    return out

def _get_rel_path(folder_path:Path, full_path:Path) -> str:
    """Get the relative path to the folder from the full path"""
    return str(Path(full_path).relative_to(Path(folder_path)))

def generate_hr_report(folder_path:str) -> pd.DataFrame:
    """Generate and save a hr report, one row per (rel_path, roi_id)

    Runs hr analysis for each roi in each kym image in the list,
    and returns a dataframe with one row per (rel_path, roi_id)
    containing the hr analysis results.

    Args:
        folder_path: path to folder with tif files

    Returns:
        pd.DataFrame: a dataframe with one row per (rel_path, roi_id)
    """

    logger.info(f'loading KymImageList from folder_path:{folder_path}')
    kym_images = KymImageList(path=folder_path)
    logger.info(f'{len(kym_images)} kym images')

    logger.warning('  running run_roi() on all images .. SLOW ..')

    # one hr config for all roi
    cfg = HRAnalysisConfig()

    summary_list = []

    for _idx, kym_image in enumerate(kym_images):
        # print(kym_image.path)
        ka = kym_image.get_kym_analysis()
        csv_path, _ = ka._get_save_paths()

        if not csv_path.exists():
            logger.warning(f'{csv_path} does not exist, skipping {kym_image.path}')
            continue

        analysis = HeartRateAnalysis.from_csv(csv_path)
        for roi_id in kym_image.rois.get_roi_ids():
        
            logger.warning(f'  {_idx+1}:{len(kym_images)} run_roi() on roi_id:{roi_id} file:{kym_image.path.name}')
            _ = analysis.run_roi(roi_id, cfg=cfg)
            
            mini_summary = analysis.get_roi_summary(roi_id, minimal="mini")

            # could use csv_path instead but would
            # not match eventual src df rel_path (which is tif based)
            mini_summary['rel_path'] = _get_rel_path(folder_path, kym_image.path)
            
            summary_list.append(mini_summary)

    df = pd.DataFrame(summary_list)
    
    _savePath = 'hr_summary_v2_db.csv'
    logger.info(f'saving {len(df)} to {_savePath}')
    df.to_csv(_savePath, index=False)

    # print(df[['file', 'roi_id', 'lomb_bpm']].head())
    # print(df.columns)

    return df

# def test_hr_save():
#     oneCsv = '/Users/cudmore/Downloads/kymflow_app/declan-stall-v1/28d AngII/20250708/flow-analysis/20250708_A85_0002_kymanalysis.csv'
#     analysis = HeartRateAnalysis.from_csv(oneCsv)
#     roi_id = 1
#     analysis.run_roi(roi_id, cfg=HRAnalysisConfig())
#     json_path = analysis.save_results_json()

#     analysis2 = HeartRateAnalysis.from_csv(oneCsv)
#     analysis2.load_results_json(json_path)

#     from pprint import pprint
    
#     summary = analysis.get_roi_summary(roi_id, minimal="mini")
#     pprint(summary)
#     summary2 = analysis2.get_roi_summary(roi_id, minimal="mini")
#     pprint(summary2)

def _make_unique_file(row):
    parts = str(row['rel_path']).split('/')
    treatment_val = str(row['treatment'])
    parts_no_treatment = [p for p in parts if p != treatment_val]
    parts_clean = [p for p in parts_no_treatment if p]
    return '/'.join(parts_clean)

def _merge_declan_summary_cols():
    """
    TODO: read declan xls and merge hand entered columns:
    Genotype	Sex	Age	Order	Direction	Depth

    merge into existing hr_ csv
    """
    # this is old
    # declanSummaryPath = '/Users/cudmore/Downloads/kymflow_app/declan-stall-v1/declan-orig-summary/Baseline_Bloodflow_Master.csv'
    # this is new jan 2026 (from email)
    # /Users/cudmore/Downloads/kymflow_app/declan-stall-v1/declan-orig-summary/from-email-new/Baseline_Bloodflow_Master.xlsx
    declanSummaryPath = '/Users/cudmore/Downloads/kymflow_app/declan-stall-v1/declan-orig-summary/from-email-new/Baseline_Bloodflow_Master.csv'

    df_declan = pd.read_csv(declanSummaryPath)
    _cols = ['Genotype', 'Sex', 'Age', 'Order', 'Direction', 'Depth']
    logger.info('loaded declan xls/csv is like:')
    print(df_declan[_cols+['uniqueFile']].head())
    # uniqueFile is like: '20221102/Capillary1_0001.tif' 

    # current working hr summary
    hr_summary_path = '/Users/cudmore/Downloads/kymflow_app/declan-stall-v1/hr_report_db.csv'
    df_hr = pd.read_csv(hr_summary_path)
    # print(f'columns of {hr_summary_path} are:')
    # print(df_hr.columns)
    _hr_cols = ['treatment', 'rel_path']
    # rel_path is like '14d Saline/20251014/20251014_A98_0002.tif'
    # print(df_hr[_hr_cols].head())
    df_hr['_tmp_uniqueFile'] = df_hr.apply(_make_unique_file, axis=1)
    logger.info(f'_tmp_uniqueFile is now:')
    _tmp_printCol = ['roi_id', 'rel_path', '_tmp_uniqueFile']
    print(df_hr[_tmp_printCol].head())
    # _tmp_uniqueFile should match df_declan uniqueFile
    

    # first, add all _cols to df_hr, make sure they do not exist:
    for col in _cols:
        if col in df_hr.columns:
            raise ValueError(f'column {col} already exists in df_hr')
        df_hr[col] = None

    # step through each row of df_declan:
    #  - grab uniqueFile
    #  - find corresponding row in df_hr (if it exists)
    #  - append _cols from df_declan to that row in df_declan
    for index, row in df_declan.iterrows():
        uniqueFile = row['uniqueFile']
        # print(f' search for {uniqueFile} in df_hr')
        # find corresponding row in df_hr (if it exists)

        # we will get a number of matching rows across roi_id
        matching_row = df_hr[df_hr['_tmp_uniqueFile'] == uniqueFile]
        if len(matching_row) == 0:
            # raise ValueError(f'expected 1 row, got {len(matching_row)} for {uniqueFile}')
            # lots of master declanSummaryPath has rows (tif) not in our current working hr database
            logger.error(f'  expected row(s) from df_hr, got {len(matching_row)} for xls uniqueFile:"{uniqueFile}"')
            # print(matching_row)
            continue
        # print(matching_row)
        # append _cols from df_declan to that row in df_declan
        for col in _cols:
            # logger.info(f'  !! assigning df_hr at matching_row.index:{matching_row.index} col:{col} value:{row[col]}')
            # df_hr.at[matching_row.index, col] = row[col]
            df_hr.loc[matching_row.index, col] = row[col]

    # drop _tmp_uniqueFile column
    df_hr = df_hr.drop(columns=['_tmp_uniqueFile'])
    
    # print(df_hr.columns)
    # save df_hr to new csv, use hr_summary_path as base name
    base_name = Path(hr_summary_path).stem
    new_path = Path(hr_summary_path).parent / f'{base_name}_declan_merged.csv'
    df_hr.to_csv(new_path, index=False)
    logger.info(f'saved merged to {new_path}.csv')

if __name__ == "__main__":
    _merge_declan_summary_cols()
    sys.exit(1)
    
    # test_hr_save()
    # sys.exit(1)

    """Purpose:
        Generate all hr analysis for a folder
        - save df with one row per (rel_path, roi_id)
        - merge these new hr_ columns into an existing radon report db
    """
    
    if 0:
        # path = "/Users/cudmore/Downloads/kymflow_app/declan-stall-v1/14d Saline"
        path = "/Users/cudmore/Downloads/kymflow_app/declan-stall-v1"
        
        df_hr = generate_hr_report(path)

        # original radon analysis, each row is (rel_path, roi_id)
        # df_src_path = '/Users/cudmore/Sites/kymflow_outer/nicewidgets/data/radon_report_db.csv'
        df_src_path = os.path.join(path, 'radon_report_db.csv')
        df_src = pd.read_csv(df_src_path)

        df_merged = _append_hr_columns(df_src, df_hr)

        # print(df_merged.head())
        # save merged to new csv
        hr_merged_csv = Path(df_src_path).parent / 'hr_report_db.csv' 
        df_merged.to_csv(hr_merged_csv, index=False)
        logger.info(f'saved merged to {hr_merged_csv}')

