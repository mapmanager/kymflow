from kymflow.core.kym_file import KymFile
from kymflow.core.plotting import (
    plot_image_line_plotly,
    update_colorscale,
    update_contrast,
    update_xaxis_range,
)

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)


def run(path: str):
    """Test script to verify uirevision preserves axis ranges when updating colorscale.

    Test flow:
    1. Load KymFile and create initial figure
    2. Programmatically set x-axis ranges to simulate user zoom
    3. Update colorscale using update_traces()
    4. Verify that axis ranges are preserved (uirevision working)
    """
    print("=" * 80)
    print("Testing Plotly uirevision for preserving zoom/pan state")
    print("=" * 80)

    # Step 1: Load KymFile from path
    print("\n1. Loading KymFile...")
    kf = KymFile(path, load_image=True)
    print(f"   Loaded: {path}")

    # Step 2: Create initial figure with default settings
    print("\n2. Creating initial figure with default settings (colorscale='Gray')...")
    fig = plot_image_line_plotly(
        kf,
        y="velocity",
        remove_outliers=True,
        median_filter=5,
        colorscale="Gray",
    )

    fig.show(config={"scrollZoom": True})

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
    fig.show(config={"scrollZoom": True})

    # Step 5: Update the existing figure's colorscale using backend API
    print(
        "\n5. Updating colorscale from 'Gray' to 'Viridis' using update_colorscale()..."
    )
    print("   Expected: x-axis range should be preserved (uirevision working)")
    update_colorscale(fig, "Viridis")

    # Step 6: Show updated figure - verify range is preserved
    print("\n6. Displaying updated figure...")
    print(f"   Check: Is the x-axis range still {x_range}?")
    fig.show(config={"scrollZoom": True})

    # Step 7: Test with zmin/zmax changes using backend API
    print("\n7. Testing with contrast update using update_contrast()...")
    image = kf.ensure_image_loaded()
    image_max = float(image.max())
    zmin = int(image_max * 0.2)
    zmax = int(image_max * 0.8)
    print(f"   Updating zmin={zmin}, zmax={zmax}")
    update_contrast(fig, zmin=zmin, zmax=zmax)
    print(f"   Expected: x-axis range should still be {x_range}")
    fig.show(config={"scrollZoom": True})

    print("\n" + ("=" * 80))
    print("Test complete!")
    print("=" * 80)


if __name__ == "__main__":
    path = "/Users/cudmore/Dropbox/data/declan/data/20221102/Capillary1_0001.tif"
    run(path)
