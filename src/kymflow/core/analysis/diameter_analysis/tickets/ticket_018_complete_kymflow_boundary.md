# Ticket 018 — Complete kymflow boundary: add list_file_table_kym_images + guardrails test

## Goal
Finish the “controller-only kymflow” boundary by completing the adapter API surface and adding a small test to prevent drift.

This ticket is intentionally small and surgical.

---

## Hard rules (must follow)
1. **Do not modify anything under `kymflow/`.** Only edit files under `sandbox/diameter-analysis/`.
2. **No imports from `kymflow.core.api.kym_external` outside `gui/diameter_kymflow_adapter.py`.**
3. Views must not touch kym list internals (no `state.kym_image_list.images`, no `getattr` hacks). Views call controller methods only.
4. Real data assumptions remain: **roi_id=1** and **channel=1** (adapter enforces/validates). Synthetic ignores ROI/channel.

---

## Scope

### A) Adapter: implement `list_file_table_kym_images`
**File:** `sandbox/diameter-analysis/gui/diameter_kymflow_adapter.py`

Add:

```py
def list_file_table_kym_images(klist: Any) -> list[Any]:
    """Return images for FileTableView.

    Trust the kymflow API: klist is expected to be a kym list object returned by
    `load_kym_list_for_folder()` / facade `load_kym_list()`, and is assumed to
    already represent valid kymograph images.

    Returns:
        A plain list of image objects suitable for passing into FileTableView.set_files().
    """
    if klist is None:
        return []
    try:
        return list(klist.images)
    except AttributeError:
        return list(klist)
```

**Important:** do **not** filter by file suffix here. We trust the list provider.

---

### B) Controller: use the adapter function
**File:** `sandbox/diameter-analysis/gui/controllers.py`

1. Ensure the controller imports `list_file_table_kym_images` from the adapter.
2. Ensure `get_file_table_files()` returns `list_file_table_kym_images(self.state.kym_image_list)`.

This fixes the current mismatch where controller imports a symbol that doesn’t exist.

---

### C) Views: ensure it uses controller only (no internals)
**File:** `sandbox/diameter-analysis/gui/views.py`

Confirm the file table population uses:

```py
file_table_view.set_files(controller.get_file_table_files())
```

and does not reference `state.kym_image_list.images` directly.

If the current `views.py` already does this, keep it as-is.

---

### D) Add a small “boundary” unit test
**File:** `sandbox/diameter-analysis/tests/test_kymflow_boundary.py` (new)

Add a lightweight test that fails if any GUI module (except the adapter) imports the facade.

Implementation approach:
- Read the source text for `sandbox/diameter-analysis/gui/*.py`
- Assert that `"kymflow.core.api.kym_external"` appears **only** in `diameter_kymflow_adapter.py`.

Example:

```py
from pathlib import Path

GUI_DIR = Path(__file__).resolve().parents[1] / "gui"

def test_only_adapter_imports_kym_external():
    hits = []
    for p in GUI_DIR.glob("*.py"):
        text = p.read_text(encoding="utf-8")
        if "kymflow.core.api.kym_external" in text:
            hits.append(p.name)
    hits = sorted(hits)
    assert hits == ["diameter_kymflow_adapter.py"]
```

---

## Acceptance criteria
- App runs and FileTableView populates as before.
- Selecting a file still loads and “Detect” still works.
- No `ImportError` for `list_file_table_kym_images`.
- Boundary test passes: only the adapter imports `kymflow.core.api.kym_external`.

---

## Out of scope
- Any ROI/channel UI changes
- Any changes to kymflow code
- Any changes to analysis algorithm behavior
