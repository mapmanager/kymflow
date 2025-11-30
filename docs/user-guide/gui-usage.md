# GUI Usage Guide

## Main Page

The main page provides a complete workflow for analyzing individual kymograph files.

### File Table

- **Single Selection**: Click a row to select a file
- **Columns**: File name, folder info, analysis status, metadata preview
- **Status Indicators**: ✓ marks show if file is analyzed and saved

### Image & Line Viewer

- **Kymograph Display**: Shows the 2D kymograph image
- **Line Plot**: Shows velocity over time from analysis
- **Zoom/Pan**: Use mouse to zoom and pan the image
- **Contrast Controls**: Adjust intensity scaling

### Metadata Forms

- **Experimental Metadata**: Edit species, region, cell type, depth, branch order, direction, sex, genotype, condition, and notes
- **Olympus Header**: View acquisition parameters (read-only)
- **Analysis Parameters**: View analysis settings and results (read-only)

### Analysis Toolbar

- **Window Size**: Select analysis window size (16, 32, 64, 128, 256)
- **Analyze Flow**: Run Radon-based flow analysis
- **Cancel**: Stop running analysis
- **Save**: Save analysis results to disk

## Batch Page

The batch page allows processing multiple files sequentially.

### Multi-Selection

- **Select Multiple Files**: Click multiple rows to select them
- **Selection Counter**: Shows number of selected files
- **Analyze Selected**: Process only selected files
- **Progress Tracking**: See progress for both individual files and overall batch

### Batch Controls

- **Window Size**: Set analysis window size for all files
- **Analyze Flow**: Start batch processing
- **Cancel**: Stop batch processing at any time

## Tips

- Use the folder selector to switch between different data directories
- Analysis results are saved in a `-analysis` subfolder alongside your TIFF files
- The GUI preserves your file selections when navigating between pages
- Use the contrast controls to better visualize flow patterns in the image
