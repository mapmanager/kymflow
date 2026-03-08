# ticket_017_kymflow_facade_adapter.md

## Goal
Introduce a **single adapter layer** in `diameter-analysis/` for interacting with real kymographs via **kymflow’s external facade API** (`kymflow.core.api.kym_external`). This adapter becomes the **only allowed** entry point for:

- listing kymographs from a folder
- locating a kymograph by path
- reading geometry / physical size
- loading channel data
- reading ROI ids / ROI bounds

This ticket does **not** change any files under `kymflow/`.

## Context / Constraints (must follow)
- **Scope:** only edit files under `kymflow/sandbox/diameter-analysis/`.
- **Do not modify anything under `kymflow/`** (treat it like an external dependency).
- When dealing with **real kymographs**, use **only** `kymflow.core.api.kym_external` facade functions.
  - Do **not** access `KymImage` convenience properties like `.seconds_per_line`, `.um_per_pixel`, `.num_lines`, `.pixels_per_line`, etc.
- **Assumptions for real data:** `roi_id=1`, `channel=1` (hard-coded for now, explicitly documented).
- **Synthetic data:** ignores ROI/channel concepts (continues to run on a raw ndarray).

## Deliverables
### 1) New adapter module
Create a new module (name is important for later tickets):
- `kymflow/sandbox/diameter-analysis/diameter_kymflow_adapter.py`

It should provide small, typed functions that wrap kymflow facade calls and centralize defaults:

Required functions (minimum):
- `load_kym_list_for_folder(folder: str | Path) -> Any`
- `get_kym_by_path(klist: Any, path: str | Path) -> Any | None`
- `get_kym_geometry_for(kimg: Any) -> tuple[tuple[int, int], float, float]`  # (shape, dt, dx)
- `get_kym_physical_size_for(kimg: Any) -> tuple[float, float]`  # (duration_s, length_um)
- `get_channel_ids_for(acq: Any) -> list[int]`
- `load_channel_for(acq: Any, channel: int = 1) -> "np.ndarray"`
- `get_roi_ids_for(acq: Any) -> list[int]`
- `get_roi_pixel_bounds_for(acq: Any, roi_id: int = 1) -> Any`  # RoiPixelBounds
- `require_channel_and_roi(acq: Any, *, channel: int = 1, roi_id: int = 1) -> None`
  - Must raise a clear `ValueError` with message suitable for UI display if missing channel/roi.

Implementation rules:
- Import facade functions ONLY from:
  - `from kymflow.core.api.kym_external import ...`
- Keep all hard-coded defaults in one place (module constants):
  - `DEFAULT_CHANNEL_ID = 1`
  - `DEFAULT_ROI_ID = 1`
- Include google-style docstrings on the module and each public function.

### 2) Update diameter-analysis code to use adapter for real data path
Update only the *diameter-analysis* integration points that currently touch kymflow objects directly.

At minimum:
- Update `gui/file_table_integration.py` (or whichever module is wiring FileTableView selection) so it:
  - does not iterate `KymImageList` manually
  - does not call `KymImageList.find_by_path(...)` directly (if present)
  - uses the adapter functions to:
    - resolve selection path -> kym object
    - check channel/roi existence (roi_id=1, channel=1)
    - load channel array (channel=1)
    - obtain dt/dx and pass into DiameterAnalyzer

NOTE: Do not remove existing fallback “Open TIFF…” button behavior in this ticket unless it is already unused and safely removable.
But: any real-data load path should go through the adapter.

### 3) Tests
Add tests under `kymflow/sandbox/diameter-analysis/tests/`:

- Create `tests/test_kymflow_adapter.py`:
  - Unit test that `require_channel_and_roi(...)` raises when roi/channel missing.
  - Unit test that adapter uses the facade functions (mock/monkeypatch).
  - Unit test that defaults channel=1 roi=1 are applied.

Testing constraints:
- Tests must NOT import internal kymflow implementation modules directly (no `kym_image_list`, etc).
- Use `monkeypatch` to stub facade functions imported by the adapter module.

### 4) Guardrails in CODEX rules
Add a short rule to `tickets/CODEX_RULES.md` (and/or the ticket template if you prefer) stating:

- “When dealing with real kymographs, use only `kymflow.core.api.kym_external` facade functions; do not access `KymImage` convenience properties.”

Keep it short and explicit.

## Acceptance criteria
- GUI can still load/preview a kymograph selected from FileTableView, and the data load path uses the adapter.
- If ROI 1 or channel 1 is missing, user gets a clear UI-visible error (exception message is acceptable for now).
- New tests pass with `uv run pytest`.
- No edits under `kymflow/` outside `kymflow/sandbox/diameter-analysis/`.

## Commands
From `kymflow/sandbox/diameter-analysis/`:
- Run tests: `uv run pytest`
- Run GUI: `uv run python run_gui.py`
