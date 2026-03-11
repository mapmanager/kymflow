# Plan: ImageRoiWidget ROI Edit Callbacks → App State & File Table

## Summary

Examination of the codebase shows:
1. **Add ROI** – correctly wired: `on_request_add_roi` → `create_full_roi_for_widget` → `_on_add_roi` → `AddRoi(state)` + `FileChanged`
2. **Edit ROI** – correctly wired: `on_roi_event(UPDATE)` → `_on_edit_roi(EditRoi)` → `bus.emit` → EditRoiController → `EditRoi(state)` + `FileChanged`
3. **Delete ROI** – **not wired**: `on_roi_event(DELETE)` is not handled; no `on_delete_roi` callback in the v2 view
4. **File table** – already reacts to `FileChanged` via `FileTableBindings._on_file_changed` → `update_row_for_file` (updates ROIS column, Saved, etc.)
5. **KymAnalysis dirty** – already handled by `RoiSet._mark_metadata_dirty()` in create/delete/edit, so `KymAnalysis.is_dirty` reflects ROI changes
6. **Recursion** – no recursion risk: ImageRoiWidget is driven by `set_selected_file` / `set_selected_roi`; ROI CRUD events flow controller → state → other consumers. The v2 view does not subscribe to AddRoi/EditRoi/DeleteRoi state for rebuilding the widget.

---

## Current Wiring

### ImageRoiWidget callbacks (nicewidgets)

- `on_roi_event(ROIEvent)` – ADD, DELETE, UPDATE, SELECT
- `on_request_add_roi()` – returns `RegionOfInterest | None` for Add

### ImageLineViewerV2View `on_roi_event` handler

```python
# image_line_viewer_v2_view.py (lines 131–149)
def on_roi_event(e: ROIEvent) -> None:
    if e.type is ROIEventType.SELECT and self._on_roi_select and not self._suppress_roi_select_emit:
        roi_id = _parse_roi_id_from_name(e.roi.name) if e.roi else None
        self._on_roi_select(roi_id)
    elif e.type is ROIEventType.UPDATE and e.roi and self._on_edit_roi:
        roi_id = _parse_roi_id_from_name(e.roi.name)
        if roi_id is not None:
            bounds = _region_of_interest_to_roi_bounds(e.roi)
            path = str(self._current_file.path) if self._current_file else None
            self._on_edit_roi(EditRoi(...))
    # MISSING: elif e.type is ROIEventType.DELETE
```

### HomePage callbacks

- `on_add_roi` – wired to `_on_add_roi` (emits `AddRoi(state)` + `FileChanged`)
- `on_edit_roi` – wired to `bus.emit` (EditRoiController receives intent)
- `on_delete_roi` – not passed to the view; view has no `on_delete_roi`

---

## Gaps

1. **Delete ROI** – The v2 view never handles `ROIEventType.DELETE`. When the user deletes in ImageRoiWidget:
   - The widget removes the ROI locally and emits `ROIEvent(DELETE, deleted_roi)`
   - The view ignores it; kymflow `KymImage` still has the ROI
   - File table and KymAnalysis do not update

2. **Add ROI state event** – `_on_add_roi` emits `AddRoi(phase="state")`. `AddRoiController` listens for `AddRoi` intent. That’s fine: the adapter already creates the ROI; we only need `FileChanged` to refresh the file table. No change needed.

---

## Proposed Changes

### 1. Add `on_delete_roi` to ImageLineViewerV2View

- Add optional `on_delete_roi: OnDeleteRoi | None = None` (same style as `on_add_roi`, `on_edit_roi`).
- In `on_roi_event`, add handling for `ROIEventType.DELETE`:
  - Parse `roi_id` from `e.roi.name` (`_parse_roi_id_from_name`)
  - If `on_delete_roi` is set, call `on_delete_roi(DeleteRoi(roi_id=..., path=..., origin=IMAGE_VIEWER, phase="intent"))`

### 2. Wire `on_delete_roi` in HomePage

- Implement `_on_delete_roi(DeleteRoi)` that emits `DeleteRoi` with `phase="intent"`.
- Pass it to the view: `on_delete_roi=bus.emit` (or a small wrapper that sets `phase="intent"`).

`DeleteRoi` is intent when emitted from the view, and `DeleteRoiController` subscribes to intent. So `on_delete_roi=bus.emit` is correct if the view emits `phase="intent"`.

### 3. `_on_roi_deleted` in ImageLineViewerV2Bindings

- Keep `_on_roi_deleted` as today: it receives `DeleteRoi(state)` and calls `set_selected_roi(None)` (or similar).
- Selection is later corrected by `ROISelection` from the bridge when `DeleteRoiController` calls `app_state.select_roi(remaining)`.
- Alternatively, call `_view._refresh_from_state()` to resync the widget with KymImage after delete. Since the widget already removed the ROI locally and the controller updates KymImage, both should match; refresh is optional but harmless.

---

## File table and KymAnalysis

- **File table** – `FileTableBindings._on_file_changed` already calls `update_row_for_file(kym_file)`, which uses `file.getRowDict()` with:
  - `"Num ROIS"` from `self.rois.numRois()`
  - `"Saved"` from `not self.get_kym_analysis().is_dirty`
- **KymAnalysis dirty** – `RoiSet.delete()` (and create/edit) calls `_mark_metadata_dirty()` on `acq_image`; `KymAnalysis.is_dirty` includes `acq_image.is_metadata_dirty`, so ROI changes are reflected.

No changes needed for the file table or KymAnalysis.

---

## Recursion

- ImageRoiWidget does not subscribe to bus events.
- It is driven by `set_selected_file` / `set_selected_roi` and by the initial ROI list passed from `kymimage_to_channel_manager`.
- On add/edit/delete, events go: view callback → bus (intent) → controller → KymImage → bus (state) → `FileTableBindings`, `ImageLineViewerV2Bindings`, etc.
- `ImageLineViewerV2Bindings` reacts to `EditRoi`/`DeleteRoi` state with `set_selected_roi` and optional refresh. There is no loop back into ImageRoiWidget that would cause recursion.

---

## Implementation Checklist

- [ ] Add `OnDeleteRoi` type and `on_delete_roi` to `ImageLineViewerV2View`
- [ ] In `on_roi_event`, handle `ROIEventType.DELETE` and call `on_delete_roi` with `DeleteRoi(phase="intent")`
- [ ] In `HomePage`, pass `on_delete_roi=bus.emit` to `ImageLineViewerV2View`
- [ ] Confirm `DeleteRoiController` is created in `HomePage` (already present)
- [ ] (Optional) Adjust `_on_roi_deleted` to use `_refresh_from_state` if a full sync after delete is desired
