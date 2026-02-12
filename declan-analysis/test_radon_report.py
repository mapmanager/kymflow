"""Test script for radon velocity analysis summary report.

This script demonstrates how to use the new get_radon_report() methods
to generate a summary of velocity analysis across multiple kymograph files.

Usage:
    python test_radon_report.py
    
    Or modify the folder_path variable below to point to your kymograph data folder.
"""

from pathlib import Path
import logging
from typing import List

from kymflow.core.image_loaders.kym_image_list import KymImageList
from kymflow.core.image_loaders.radon_report import RadonReport
from kymflow.core.image_loaders.acq_image import AcqImage
from kymflow.core.utils.logging import get_logger, setup_logging

# Setup logging
setup_logging(level=logging.INFO)
logger = get_logger(__name__)


# ROI image stats keys to check for undefined defaults (None)
_ROI_IMG_STAT_KEYS = ("img_min", "img_max", "img_mean", "img_std")


def _roi_has_undefined_img_stats(roi) -> bool:
    """Return True if ROI has any undefined (None) image stats."""
    return any(getattr(roi, key) is None for key in _ROI_IMG_STAT_KEYS)


def ensure_roi_img_stats(acq_image: AcqImage, *, _preflight: bool = True) -> bool:
    """Ensure ROI image statistics are calculated for all ROIs in an AcqImage.
    
    When _preflight=True (default): Only checks if any ROI has undefined image stats
    (img_min, img_max, img_mean, img_std are None). Returns True if at least one ROI
    needs updating, False otherwise. Does not load image data.
    
    When _preflight=False: Loads image data, calculates stats for each ROI via
    roi.calculate_image_stats(), marks the acq_image as dirty (needs saving).
    Does NOT save; caller is responsible for calling acq_image.save_metadata().
    
    Args:
        acq_image: AcqImage instance to process.
        _preflight: If True, only check and return needs_update flag. If False,
            load image, calculate stats, mark dirty (no save).
        
    Returns:
        True if at least one ROI has undefined stats (needs updating), False otherwise.
        When _preflight=False, also returns True if stats were calculated and image
        was marked dirty.
        
    Note:
        - Tries to load channel 1 first, then other available channels if needed
        - Logs warnings for ROIs that fail to calculate stats
        - Returns False if image has no ROIs (nothing to update)
    """
    roi_ids = acq_image.rois.get_roi_ids()
    
    if len(roi_ids) == 0:
        return False
    
    if _preflight:
        # Check only: any ROI with undefined img stats?
        for roi_id in roi_ids:
            roi = acq_image.rois.get(roi_id)
            if roi is not None and _roi_has_undefined_img_stats(roi):
                return True
        return False
    
    # _preflight=False: if any ROI has undefined stats, load image, calculate, mark dirty (no save)
    has_undefined = any(
        _roi_has_undefined_img_stats(roi)
        for roi_id in roi_ids
        if (roi := acq_image.rois.get(roi_id)) is not None
    )
    if not has_undefined:
        return False

    channel_loaded = False
    channels_to_try = [1]
    try:
        available_channels = acq_image.getChannelKeys()
        if available_channels:
            channels_to_try = [1] + [ch for ch in available_channels if ch != 1]
    except Exception:
        pass
    
    for channel in channels_to_try:
        if acq_image.load_channel(channel):
            channel_loaded = True
            break
    
    if not channel_loaded:
        logger.warning(
            f"Could not load image data for {acq_image.path} - "
            f"skipping ROI image stats calculation"
        )
        return False
    
    needs_saving = False
    for roi_id in roi_ids:
        roi = acq_image.rois.get(roi_id)
        if roi is None:
            continue
        try:
            roi.calculate_image_stats(acq_image)
            needs_saving = True
        except ValueError as e:
            logger.warning(
                f"Could not calculate image stats for ROI {roi_id} in {acq_image.path}: {e}"
            )
        except Exception as e:
            logger.warning(
                f"Unexpected error calculating image stats for ROI {roi_id} in {acq_image.path}: {e}"
            )
    
    if needs_saving:
        acq_image.mark_metadata_dirty()
    return needs_saving


def get_acq_images_needing_roi_stats_update(
    folder_path: Path,
    *,
    file_extension: str = ".tif",
    depth: int = 4,
    ignore_file_stub: str | None = None,
    _preflight: bool = True,
) -> List[Path]:
    """Load a KymImageList and return paths of acq images that need ROI img stats updated.
    
    For each KymImage, checks if any ROI has undefined img stats (img_min, img_max,
    img_mean, img_std are None). Returns a list of acq image paths where at least
    one ROI needs stats calculated.
    
    Uses _preflight=True: loads metadata only (ROIs from JSON), no image pixel loading.
    Does NOT calculate stats or save - this is a check-only pass.
    
    Args:
        folder_path: Directory to scan for kymograph files.
        file_extension: File extension to match. Defaults to ".tif".
        depth: Recursive scan depth. Defaults to 4.
        ignore_file_stub: Optional stub string to ignore in filenames.
        
    Returns:
        List of Path to acq images (e.g. .tif files) that need ROI img stats updating.
    """
    kym_image_list = KymImageList(
        path=folder_path,
        file_extension=file_extension,
        depth=depth,
        ignore_file_stub=ignore_file_stub,
    )
    needs_update: List[Path] = []
    for image in kym_image_list:
        if ensure_roi_img_stats(image, _preflight=_preflight):
            path = image.path
            if path is not None:
                needs_update.append(path)
            
            # do the save here if _preflight=False
            if not _preflight:
                # image.save_metadata()
                logger.info(f"Saving analysis for")
                print(f"  {image.path}")
                image.get_kym_analysis().save_analysis()

    return needs_update


def main() -> List[RadonReport]:
    """Generate and display radon velocity analysis summary report.
    
    Returns:
        List of RadonReport instances containing the radon report for all ROIs.
    """
    # Specify path to folder containing kymograph files
    # Modify this path to point to your data folder
    _path = "/Users/cudmore/Dropbox/data/declan/2026/compare-condiitons/v2-analysis"
    
    folder_path = Path(_path)
    
    # Example paths (uncomment and modify as needed):
    # folder_path = Path("/Users/cudmore/Sites/kymflow_outer/data/20221102")
    # folder_path = Path.home() / "data" / "kymographs"
    
    logger.info(f"Loading KymImage files from: {folder_path}")
    
    # Validate that the path exists
    if not folder_path.exists():
        logger.error(f"Path does not exist: {folder_path}")
        logger.info("Please modify the folder_path variable in this script to point to a valid folder.")
        return []
    
    # Load KymImageList
    # depth=2 means scan base folder and immediate subfolders
    kym_image_list = KymImageList(
        path=folder_path,
        file_extension=".tif",
        depth=4,  # Adjust depth as needed (1 = base folder only, 2 = base + subfolders)
    )
    
    logger.info(f"Loaded {len(kym_image_list)} images")
    
    if len(kym_image_list) == 0:
        logger.warning("No images found. Check that:")
        logger.warning("  1. The folder_path is correct")
        logger.warning("  2. Files have .tif extension")
        logger.warning("  3. Files can be loaded as KymImage instances")
        return []
    
    # Load image data and calculate ROI image statistics
    # This ensures that img_min, img_max, img_mean, img_std are populated
    logger.info("Loading image data and calculating ROI image statistics...")
    images_processed = 0
    
    for image in kym_image_list:
        # Only process images that have ROIs (typically KymImage instances)
        try:
            ensure_roi_img_stats(image, _preflight=False)
            images_processed += 1
        except Exception as e:
            logger.warning(f"Error processing image {image.path}: {e}")
            continue
    
    logger.info(f"Processed {images_processed} images")
    
    # Generate report using KymImageList.get_radon_report()
    # This aggregates reports from all KymImage files in the list
    # Returns List[RadonReport] instances
    # Now the ROI image statistics should be populated
    report = kym_image_list.get_radon_report()
    
    logger.info(f"Generated report with {len(report)} ROI entries")
    
    # Print report summary
    print("\n" + "="*80)
    print("RADON VELOCITY ANALYSIS SUMMARY REPORT")
    print("="*80)
    print(f"Total ROIs: {len(report)}")
    
    # Count unique files
    unique_files = set(r.file_name for r in report if r.file_name is not None)
    print(f"Total files: {len(unique_files)}")
    
    # Count ROIs with missing image stats (should be rare after calculation above)
    missing_img_stats = sum(
        1 for r in report 
        if any(getattr(r, key) is None for key in ['img_min', 'img_max', 'img_mean', 'img_std'])
    )
    if missing_img_stats > 0:
        print(f"ROIs with missing image stats: {missing_img_stats}")
        print("  (These may have failed to calculate due to missing image data or invalid channels)")
    
    print("\n" + "-"*80)
    
    # Print first few entries as example
    # print("\nFirst 5 ROI entries (example):")
    # for i, roi_report in enumerate(report[:5], 1):
    #     print(f"\nROI Entry {i}:")
    #     # Use to_dict() to get a dictionary representation
    #     roi_dict = roi_report.to_dict()
    #     for key, value in sorted(roi_dict.items()):
    #         # Format floats to 3 decimal places for readability
    #         if isinstance(value, float):
    #             print(f"  {key}: {value:.3f}")
    #         else:
    #             print(f"  {key}: {value}")
    
    if len(report) > 5:
        print(f"\n... and {len(report) - 5} more ROIs")
    
    # Optionally save to CSV for further analysis
    # Use the convenient get_radon_report_df() method
    try:
        # Get report as DataFrame (convenience method)
        # This requires pandas, which is imported inside the try block
        df = kym_image_list.get_radon_report_df()
        csv_path = folder_path / "radon_report.csv"
        df.to_csv(csv_path, index=False)
        logger.info(f"Saved report to: {csv_path}")
        
        # Print summary statistics
        print("\n" + "-"*80)
        print("Summary Statistics (for ROIs with valid velocity data):")
        print("-"*80)
        
        # Filter out None values for statistics
        valid_velocities = df[df['vel_mean'].notna()]
        if len(valid_velocities) > 0:
            print(f"ROIs with valid velocity data: {len(valid_velocities)}")
            print(f"  Mean velocity (mean of all ROI means): {valid_velocities['vel_mean'].mean():.3f} mm/s")
            print(f"  Std of ROI means: {valid_velocities['vel_mean'].std():.3f} mm/s")
            print(f"  Min velocity across all ROIs: {valid_velocities['vel_min'].min():.3f} mm/s")
            print(f"  Max velocity across all ROIs: {valid_velocities['vel_max'].max():.3f} mm/s")
        else:
            print("No ROIs with valid velocity data found.")
            
    except ImportError:
        logger.info("pandas not available - skipping CSV export and summary statistics")
    
    return report


if __name__ == "__main__":

    if 0:

        # Run the main function
        report = main()
        
        # Exit with appropriate code
        if len(report) == 0:
            exit(1)  # Exit with error if no report generated
        else:
            exit(0)  # Exit successfully


    path = '/Users/cudmore/Dropbox/data/declan/2026/compare-condiitons/v2-analysis/radon_report.csv'
    _preflight = False
    paths = get_acq_images_needing_roi_stats_update(Path(path).parent,_preflight=False)
    # print(f"Images needing ROI stats update: {len(paths)}")
    # for p in paths:
    #     print(f"  {p}")