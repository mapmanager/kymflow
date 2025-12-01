# Example Notebooks

Jupyter notebooks demonstrating how to use the KymFlow Python API.

## Available Notebooks

Notebooks are located in the `notebooks/` directory of the repository:

- `display_one_kym.py` - Example script for displaying a single kymograph
- `quality_control.ipynb` - Quality control workflow

## Running Notebooks

1. Install notebook dependencies:
   ```bash
   pip install kymflow[notebook]
   ```

2. Launch Jupyter Lab:
   ```bash
   jupyter lab --notebook-dir notebooks
   ```

3. Open and run the notebooks to see examples of:
   - Loading kymograph files
   - Accessing metadata
   - Running flow analysis
   - Visualizing results

## Example Code

```python
from kymflow.core.kym_file import KymFile

# Load a kymograph file
kym = KymFile("path/to/file.tif", load_image=False)

# Access metadata
print(f"Duration: {kym.duration_seconds} seconds")
print(f"Pixels per line: {kym.pixels_per_line}")

# Load image when needed
image = kym.ensure_image_loaded()

# Run analysis
kym.analyze_flow(window_size=16)

# Save results
kym.save_analysis()
```
