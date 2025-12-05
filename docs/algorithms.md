# Algorithms

KymFlow uses a Radon transform-based algorithm to detect flow direction and velocity in kymograph images. This page provides an overview of the algorithm and its implementation.

## Overview

The Radon transform algorithm analyzes kymograph images to detect the direction and speed of blood flow. A kymograph is a 2D image where one axis represents time (line scans) and the other represents space (pixels along a line). Flow appears as diagonal streaks in the image, and the angle of these streaks indicates the flow direction and velocity.

The algorithm uses a sliding window approach along the time axis, applying Radon transforms to detect the optimal flow angle for each window. This allows tracking flow changes over time.

## Technical Details

### Sliding Window Approach

The algorithm processes the kymograph using overlapping sliding windows:

- **Window Size**: The number of time lines (rows) per analysis window. Must be a multiple of 4.
- **Step Size**: Windows are advanced by 25% of the window size (e.g., for window_size=16, step_size=4), creating 75% overlap between consecutive windows.
- **Spatial Range**: Optionally, analysis can be limited to a specific range of pixels using `start_pixel` and `stop_pixel` parameters.

### Two-Stage Radon Transform

For each window, the algorithm performs a two-stage angle search:

1. **Coarse Search**: 
   - Performs Radon transforms over angles from 0 to 179 degrees (1 degree steps).
   - Finds the angle that maximizes the variance in Radon space.
   - This variance peak indicates the dominant flow direction.

2. **Fine Search**:
   - Refines the search around the best coarse angle.
   - Searches ±2 degrees from the coarse angle in 0.25 degree steps.
   - Returns the angle with maximum variance in this fine grid.

### Angle Detection and Velocity Calculation

The Radon transform projects the image along lines at different angles. When a line aligns with the flow direction (diagonal streaks), the projection has high variance. The algorithm finds the angle that maximizes this variance.

The detected angle (θ) is converted to velocity using:

```
velocity = (um_per_pixel / seconds_per_line) * tan(θ) / 1000
```

This converts from radians to mm/s, using the spatial and temporal resolution from the Olympus header metadata.

### Data Preprocessing

Before analysis, each window is preprocessed:

- The mean value is subtracted from the window to remove DC offset.
- This improves the sensitivity of the Radon transform to flow patterns.

### Post-Processing

After angle detection, the velocity values undergo post-processing:

- **Outlier Removal**: Values beyond ±2 standard deviations are set to NaN.
- **Median Filtering**: A 5-point median filter smooths the velocity time series.

## Parameters

Key parameters for the analysis:

- **window_size**: Number of time lines per analysis window. Must be a multiple of 4. Larger windows provide better signal-to-noise ratio but reduce temporal resolution.
- **start_pixel**: Optional start index in the spatial dimension (inclusive). If None, uses 0.
- **stop_pixel**: Optional stop index in the spatial dimension (exclusive). If None, uses full width.
- **use_multiprocessing**: If True, uses parallel processing to speed up computation. Defaults to True.

## Output

The algorithm produces:

- **time**: Array of center time points for each analysis window (in seconds).
- **velocity**: Array of flow velocities (in mm/s) for each window. Positive values indicate flow in one direction, negative values indicate reverse flow.
- **cleanVelocity**: Outlier-removed and median-filtered velocity values.
- **absVelocity**: Absolute value of cleanVelocity.

Additional metadata is saved including:
- **parentFolder**: Name of the parent folder containing the original TIFF file.
- **file**: Name of the original TIFF file.
- **algorithm**: Algorithm identifier ("mpRadon").
- **delx**: Spatial resolution (um_per_pixel).
- **delt**: Temporal resolution (seconds_per_line).
- **numLines**: Total number of time lines in the kymograph.
- **pntsPerLine**: Number of pixels per line (spatial dimension).

## Implementation

The algorithm is implemented in `core.analysis.kym_flow_radon` using:

- **scikit-image**: For Radon transform computation (`skimage.transform.radon`).
- **multiprocessing**: For parallel processing of multiple windows.
- **numpy**: For array operations and numerical computations.

The main entry point is the `mp_analyze_flow()` function, which can be called directly or through the `KymFile.analyze_flow()` method.

## References

- Radon Transform: [Wikipedia](https://en.wikipedia.org/wiki/Radon_transform)
- scikit-image Radon Transform: [Documentation](https://scikit-image.org/docs/stable/api/skimage.transform.html#skimage.transform.radon)

