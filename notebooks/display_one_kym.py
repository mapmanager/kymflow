from kymflow.core.image_loaders.acq_image_list import AcqImageList
from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.plotting import (
    plot_image_line_plotly,
    update_contrast,
    update_xaxis_range,
)

from kymflow.core.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)


def run(folder_path: str, filename: str):
    """Test script to verify uirevision preserves axis ranges when updating colorscale.

    Test flow:
    1. Load folder with AcqImageList and find specific file
    2. Load image data for the file
    3. Create initial figure
    4. Programmatically set x-axis ranges to simulate user zoom
    5. Update colorscale using update_traces()
    6. Verify that axis ranges are preserved (uirevision working)
    """
    print("=" * 80)
    print("Testing Plotly uirevision for preserving zoom/pan state")
    print("=" * 80)

    # Step 1: Load folder with AcqImageList
    print(f"\n1. Loading folder: {folder_path}")
    image_list = AcqImageList(
        path=folder_path,
        image_cls=KymImage,
        file_extension=".tif",
        depth=1
    )
    print(f"   Found {len(image_list)} files in folder")
    
    # Find specific file
    kymImage = None
    image_index = None
    for i, img in enumerate(image_list):
        if img.path and img.path.name == filename:
            kymImage = img
            image_index = i
            break
    
    if kymImage is None:
        raise ValueError(f"File '{filename}' not found in folder '{folder_path}'")
    
    print(f"   Found file: {kymImage.path}")
    
    # Load all channels for the image
    print("   Loading image data for all channels...")
    load_results = image_list.load_all_channels(image_index)
    for channel, success in load_results.items():
        if success:
            print(f"     Channel {channel}: loaded successfully")
        else:
            print(f"     Channel {channel}: failed to load")

    # Get all ROI IDs (using new API)
    roi_ids = kymImage.rois.get_roi_ids()
    if not roi_ids:
        raise ValueError("No ROIs found. Please create at least one ROI first.")
    
    # Use first ROI
    first_roi_id = roi_ids[0]
    one_roi_id = first_roi_id

    # logger.info(f'one_roi: {one_roi}')
    # logger.info(f'one_roi_id: {one_roi_id}')
    
    # Commented out loop for iterating over all ROIs:
    # for roi in all_rois:
    #     print(f"   ROI: {roi}")
    #     fig = plot_image_line_plotly(
    #         kf,
    #         roi_id=roi.id,
    #         y="velocity",
    #         remove_outliers=True,
    #         median_filter=5,)
    #     fig.show(config={"scrollZoom": True})
    
    # Step 2: Create initial figure with default settings
    print("\n2. Creating initial figure with default settings (colorscale='Gray')...")
    fig = plot_image_line_plotly(
        kymImage,
        # roi_id=one_roi_id,
        yStat="velocity",
        remove_outliers=True,
        median_filter=5,
        colorscale="Gray",
        selected_roi_id=one_roi_id,
        transpose=True,
        plot_rois=True,
    )

    # fig.show(config={"scrollZoom": True})

    if 0:
        # Step 3: Programmatically set x-axis range to simulate user zoom
        x_range = [11.4, 12.4]
        print(f"\n3. Programmatically setting x-axis range to {x_range}...")

        # Use helper function to update x-axis range for both subplots
        # Note: With shared_xaxes=True, row=2 (line plot) is the master axis
        update_xaxis_range(fig, x_range)

        # Verify the figure object has the correct ranges
        print("\n   Verifying figure object has correct ranges...")
        print(f"   xaxis (row=1) range in layout: {fig.layout.xaxis.range}")
        print(f"   xaxis2 (row=2) range in layout: {fig.layout.xaxis2.range}")

        # Step 4: Show figure with programmatically set ranges
        print("\n4. Displaying figure with programmatically set x-axis range...")
        print(f"   Expected range: {x_range}")
        print("   (Close the figure window to continue)")

    # fig.show(config={"scrollZoom": True})

    # Step 5: Update the existing figure's colorscale using backend API
    # print(
    #     "\n5. Updating colorscale from 'Gray' to 'Viridis' using update_colorscale()..."
    # )
    # print("   Expected: x-axis range should be preserved (uirevision working)")
    # update_colorscale(fig, "Viridis")

    # Step 6: Show updated figure - verify range is preserved
    # print("\n6. Displaying updated figure...")
    # print(f"   Check: Is the x-axis range still {x_range}?")
    # fig.show(config={"scrollZoom": True})

    # Step 7: Test with zmin/zmax changes using backend API
    print("\n7. Testing with contrast update using update_contrast()...")
    image = kymImage.get_img_slice(channel=1)
    image_max = float(image.max())
    zmin = int(image_max * 0.2)
    zmax = int(image_max * 0.8)
    print(f"   Updating zmin={zmin}, zmax={zmax}")
    update_contrast(fig, zmin=zmin, zmax=zmax)
    
    # print(f"   Expected: x-axis range should still be {x_range}")
    # fig.show(config={"scrollZoom": True})

    print("\n" + ("=" * 80))
    print("Test complete!")
    print("=" * 80)

    fig.show(config={"scrollZoom": True})


if __name__ == "__main__":
    setup_logging()
    
    # Use folder path and filename
    folder_path = '/Users/cudmore/Sites/kymflow_outer/kymflow/tests/data'
    filename = 'Capillary1_0001.tif'
    
    # Alternative: use full path and extract folder/filename
    # full_path = '/Users/cudmore/Sites/kymflow_outer/kymflow/tests/data/Capillary1_0001.tif'
    # folder_path = str(Path(full_path).parent)
    # filename = Path(full_path).name

    run(folder_path, filename)
