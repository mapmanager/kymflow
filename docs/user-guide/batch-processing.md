# Batch Processing

Batch processing allows you to analyze multiple kymograph files sequentially with progress tracking.

## Workflow

1. **Navigate to Batch Page**: Click "Batch" in the header navigation
2. **Select Files**:
   - Click multiple rows to select files (multi-select mode)
   - Selection counter shows number of selected files
3. **Set Parameters**: Choose window size for analysis
4. **Start Analysis**: Click "Analyze Flow" button
5. **Monitor Progress**:
   - Overall progress shows files completed
   - Per-file progress shows windows completed for current file
6. **Save Results**: Files are marked as analyzed; use Save button to persist

## Features

- **Progress Tracking**: Two progress bars - one for overall batch, one for current file
- **Cancellation**: Cancel button stops processing at any time
- **Auto-Refresh**: File table updates as each file completes
- **Error Handling**: If one file fails, processing continues with remaining files

## Tips

- Start with a small selection to test parameters
- Window size applies to all files in the batch
- Results are not auto-saved - use Save button after batch completes
- Large batches may take significant time depending on file sizes
