# Getting Started

## First Steps

1. **Launch KymFlow**: Run `kymflow-gui` from your terminal
2. **Select a Folder**: Use the folder selector to choose a directory containing kymograph TIFF files
3. **Browse Files**: The file table shows all TIFF files found in the selected folder
4. **Select a File**: Click on a file in the table to view its metadata and image

## Basic Workflow

### Viewing Files

- The file table displays key metadata for each file
- Select a file to see detailed metadata, image, and analysis results
- Use the image viewer to explore the kymograph data

### Editing Metadata

1. Select a file from the table
2. Edit fields in the Metadata section (species, region, notes, etc.)
3. Changes are saved automatically when you save the analysis

### Running Analysis

1. Select a file
2. Set the window size (typically 16, 32, 64, 128, or 256)
3. Click "Analyze Flow" in the toolbar
4. Wait for analysis to complete
5. Click "Save" to persist results

### Batch Processing

1. Navigate to the Batch page
2. Select multiple files (hold Ctrl/Cmd to multi-select)
3. Set window size
4. Click "Analyze Flow" to process all selected files sequentially

## Next Steps

- See [GUI Usage](gui-usage.md) for detailed interface documentation
- See [Batch Processing](batch-processing.md) for batch analysis workflows
- See [API Reference](../api/kym_file.md) for programmatic access
