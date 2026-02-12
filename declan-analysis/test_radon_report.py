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

from kymflow.core.image_loaders.acq_image_list import AcqImageList
from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.image_loaders.radon_report import RadonReport
from kymflow.core.image_loaders.acq_image import AcqImage
from kymflow.core.utils.logging import get_logger, setup_logging

# Setup logging
setup_logging(level=logging.INFO)
logger = get_logger(__name__)


def ensure_roi_img_stats(acq_image: AcqImage) -> None:
    """Ensure ROI image statistics are calculated for all ROIs in an AcqImage.
    
    This function loads image data (if not already loaded) and calculates
    image statistics (img_min, img_max, img_mean, img_std) for all ROIs.
    The function mutates the AcqImage and its ROIs in place.
    
    Args:
        acq_image: AcqImage instance to process. Must have ROIs defined.
        
    Note:
        - Tries to load channel 1 first, then other available channels if needed
        - Logs warnings for ROIs that fail to calculate stats
        - Does nothing if image has no ROIs
        - Idempotent: safe to call multiple times (recalculates stats each time)
    """
    # Get all ROI IDs for this image
    roi_ids = acq_image.rois.get_roi_ids()
    
    if len(roi_ids) == 0:
        # No ROIs in this image, nothing to do
        return
    
    # Load image data if needed
    # Try to load channel 1 first (most common channel for kymographs)
    # If channel 1 doesn't exist, try other available channels
    channel_loaded = False
    channels_to_try = [1]  # Start with channel 1
    
    # Get available channels if we can
    try:
        available_channels = acq_image.getChannelKeys()
        if available_channels:
            # Prefer channel 1, but include all available channels
            channels_to_try = [1] + [ch for ch in available_channels if ch != 1]
    except Exception:
        pass  # Fall back to just channel 1
    
    # Try to load a channel
    for channel in channels_to_try:
        if acq_image.load_channel(channel):
            channel_loaded = True
            break
    
    if not channel_loaded:
        logger.warning(
            f"Could not load image data for {acq_image.path} - "
            f"skipping ROI image stats calculation"
        )
        return
    
    # Calculate image statistics for each ROI
    for roi_id in roi_ids:
        roi = acq_image.rois.get(roi_id)
        if roi is None:
            continue
        
        try:
            # Calculate image stats for this ROI
            # This updates roi.img_min, roi.img_max, roi.img_mean, roi.img_std in place
            roi.calculate_image_stats(acq_image)
        except ValueError as e:
            # Image data not available or channel doesn't exist
            logger.warning(
                f"Could not calculate image stats for ROI {roi_id} in {acq_image.path}: {e}"
            )
        except Exception as e:
            # Other unexpected errors
            logger.warning(
                f"Unexpected error calculating image stats for ROI {roi_id} in {acq_image.path}: {e}"
            )


def main() -> List[RadonReport]:
    """Generate and display radon velocity analysis summary report.
    
    Returns:
        List of RadonReport instances containing the radon report for all ROIs.
    """
    # Specify path to folder containing kymograph files
    # Modify this path to point to your data folder
    _path = "/Users/cudmore/Dropbox/data/declan/2026/compare-condiitons/v1-analysis"
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
    
    # Load AcqImageList with KymImage
    # depth=2 means scan base folder and immediate subfolders
    acq_image_list = AcqImageList(
        path=folder_path,
        image_cls=KymImage,
        file_extension=".tif",
        depth=4,  # Adjust depth as needed (1 = base folder only, 2 = base + subfolders)
    )
    
    logger.info(f"Loaded {len(acq_image_list)} images")
    
    if len(acq_image_list) == 0:
        logger.warning("No images found. Check that:")
        logger.warning("  1. The folder_path is correct")
        logger.warning("  2. Files have .tif extension")
        logger.warning("  3. Files can be loaded as KymImage instances")
        return []
    
    # Load image data and calculate ROI image statistics
    # This ensures that img_min, img_max, img_mean, img_std are populated
    logger.info("Loading image data and calculating ROI image statistics...")
    images_processed = 0
    
    for image in acq_image_list:
        # Only process images that have ROIs (typically KymImage instances)
        try:
            ensure_roi_img_stats(image)
            images_processed += 1
        except Exception as e:
            logger.warning(f"Error processing image {image.path}: {e}")
            continue
    
    logger.info(f"Processed {images_processed} images")
    
    # Generate report using AcqImageList.get_radon_report()
    # This aggregates reports from all KymImage files in the list
    # Returns List[RadonReport] instances
    # Now the ROI image statistics should be populated
    report = acq_image_list.get_radon_report()
    
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
        df = acq_image_list.get_radon_report_df()
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
    # Run the main function
    report = main()
    
    # Exit with appropriate code
    if len(report) == 0:
        exit(1)  # Exit with error if no report generated
    else:
        exit(0)  # Exit successfully
