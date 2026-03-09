# todo-expand-kymflow-to-multiple-channels.md

## 1. Goal

Get kymflow ready for multiple channels by:

1. Making (roi, channel) explicit in runtime flows for "Analyze Flow" and "Detect Events".
2. Removing channel from ROI so channel is a runtime/analysis choice, not ROI geometry.
3. Keying analysis storage and serialization by (roi_id, channel).
4. Doing the transition in small steps, starting with a hardcoded `channel_id=1`.

---

## 2. Current State (condensed)

### Analyze Flow

| Step | Component | Passed | Notes |
|------|-----------|--------|-------|
| 1 | AnalysisToolbarView._on_start_click | roi_id, window_size | No channel |
| 2 | AnalysisStart event | roi_id, window_size | No channel |
| 3 | AnalysisController._on_analysis_start | roi_id, window_size | No channel |
| 4 | run_flow_analysis (tasks.py) | roi_id, window_size | No channel |
| 5 | KymAnalysis.analyze_roi(roi_id, window_size) | roi_id only | Gets channel from ROI |
| 6 | KymAnalysis.analyze_roi | channel = roi.channel | Uses ROI.channel to get image slice |
| 7 | mp_analyze_flow | image (already channel-specific) | No channel param |

### Detect Events

| Step | Component | Passed | Notes |
|------|-----------|--------|-------|
| 1 | AnalysisToolbarView._on_detect_events_click | roi_id | No channel |
| 2 | DetectEvents event | roi_id | No channel |
| 3 | EventAnalysisController._on_detect_events | roi_id | No channel |
| 4 | KymAnalysis.run_velocity_event_analysis(roi_id) | roi_id only | Gets velocity from _df by roi_id |
| 5 | detect_events(time_s, velocity) | N/A | Uses precomputed velocity |

### Storage (KymAnalysis)

- `_analysis_metadata`: Dict[roi_id → RoiAnalysisMetadata]
- `_df`: DataFrame with roi_id, channel, time, velocity; filtered by roi_id only
- `_velocity_events`: Dict[roi_id → List[VelocityEvent]]
- CSV/JSON save: per-file, keyed by roi_id

### App State

- AppState: selected_file, selected_roi_id — no selected_channel
- AnalysisToolbarView: _current_file, _current_roi_id — no channel

---

## 3. Phase 1: Introduce channel with hardcoded value

Use `channel_id=1` everywhere, no UI changes. Goal: make channel explicit end-to-end.

### 3.1 Events

- **AnalysisStart**: add `channel_id: int = 1`
- **DetectEvents**: add `channel_id: int | None = None` (interpret as 1 when None)

### 3.2 Controllers / tasks

- **AnalysisController._on_analysis_start**: pass `e.channel_id` (or 1) to run_flow_analysis
- **run_flow_analysis**: add param `channel_id: int = 1`
- **EventAnalysisController._on_detect_events**: pass channel to run_velocity_event_analysis
- **KymAnalysis.run_velocity_event_analysis**: add param `channel_id: int = 1`, use for lookups

### 3.3 Core analysis

- **KymAnalysis.analyze_roi**: add param `channel_id: int`, use it instead of `roi.channel`
- **KymAnalysis.get_analysis_value / has_analysis / get_velocity_events**: accept `(roi_id, channel_id)`
- Change internal storage to key by `(roi_id, channel_id)` instead of roi_id alone

### 3.4 Call sites

- AnalysisToolbarView: emit AnalysisStart and DetectEvents with `channel_id=1`
- All `analyze_roi(roi_id, window_size)` → add `channel_id=1`
- All `run_velocity_event_analysis(roi_id)` → add `channel_id=1`

### 3.5 Backward compatibility

- Legacy saved analyses (roi_id-only) → treat as channel 1 on load
- Migration: map roi_id-only rows to (roi_id, 1)

---

## 4. Phase 2: Storage and serialization

### 4.1 KymAnalysis CSV/JSON

- CSV: keep/add `channel` column; rows are unique by (roi_id, channel)
- JSON: RoiAnalysisMetadata includes channel_id; `_analysis_metadata` keys by (roi_id, channel_id)

### 4.2 Velocity events

- Store by (roi_id, channel_id)
- VelocityEventDb schema: add channel_id; unique row id includes channel_id

### 4.3 Radon report cache

- Key by (roi_id, channel_id) if report references analysis

---

## 5. Phase 3: ROI refactor (remove channel from ROI)

### 5.1 ROI class

- Remove `channel` from BaseROI/RectROI/MaskROI
- Bump schema version for ROI serialization
- Migration: saved ROIs drop channel; channel is analysis-time only

### 5.2 AcqImage metadata

- If ROI metadata is in acq_image header, update schema
- Ensure migration for old ROI JSON with channel

### 5.3 RoiSet

- `create_roi`, `edit_roi`: remove channel param
- `calculate_image_stats`: needs channel passed in (e.g. for display) or handle separately

---

## 6. Phase 4: UI and channel selection

### 6.1 AppState

- Add `selected_channel_id: Optional[int]`
- Initialize from first available channel or 1

### 6.2 Analysis toolbar

- Add channel selector (dropdown)
- Bind to _current_channel_id
- Emit events with `channel_id` from selection

### 6.3 Image display

- Use selected_channel_id for display when appropriate
- ROI bounds remain channel-agnostic

---

## 7. Transition checklist (Phase 1)

- [ ] Add `channel_id` to AnalysisStart (default 1)
- [ ] Add `channel_id` to DetectEvents (default 1)
- [ ] Update run_flow_analysis to accept and pass channel_id
- [ ] Update KymAnalysis.analyze_roi to accept channel_id, use it instead of roi.channel
- [ ] Update KymAnalysis.run_velocity_event_analysis to accept channel_id for lookups
- [ ] Update KymAnalysis._analysis_metadata and _df to key by (roi_id, channel_id)
- [ ] Update get_analysis_value, has_analysis, get_velocity_events to accept channel_id (default 1)
- [ ] Update CSV/JSON save/load to include channel_id
- [ ] Add migration for legacy analyses (roi_id-only → (roi_id, 1))
- [ ] Update VelocityEventDb schema and cache to include channel_id
- [ ] Update AnalysisToolbarView to emit channel_id=1 explicitly
- [ ] Update all call sites (tests, batch scripts, etc.) to pass channel_id=1

---

## 8. Edge cases and open questions

1. **Single-channel files**: Treat as channel 1; no UI change needed until Phase 4
2. **ROIs created before refactor**: Keep; migrate to channel 1
3. **Analysis on ROI with channel ≠ selected channel**: Phase 4 – analysis uses selected channel, not ROI.channel
4. **Same ROI, multiple channels**: Analysis storage must key by (roi_id, channel_id)
5. **Display channel vs analysis channel**: Decide if they can differ; initially both driven by selected_channel_id
6. **Velocity events per (roi_id, channel_id)**: Event table must show events per channel

---

## 9. Files to touch (Phase 1)

- `gui_v2/events.py` (AnalysisStart, DetectEvents)
- `gui_v2/controllers/analysis_controller.py`
- `gui_v2/controllers/event_analysis_controller.py`
- `gui_v2/tasks.py` (run_flow_analysis)
- `gui_v2/views/analysis_toolbar_view.py`
- `core/image_loaders/kym_analysis.py` (analyze_roi, run_velocity_event_analysis, storage, getters)
- `core/image_loaders/velocity_event_report.py` (if it persists events)
- `core/image_loaders/velocity_event_db.py` (schema)
- `core/image_loaders/radon_report.py` (if it keys by roi)
- Tests that call analyze_roi or run_velocity_event_analysis
- Batch/declan-analysis scripts if they invoke these APIs

---

## 10. Testing strategy (Phase 1)

1. Regression: existing single-channel flow behaves identically with channel_id=1
2. Round-trip: save analysis with channel_id=1, reload, verify (roi_id, 1) data preserved
3. Migration: load old analysis file (roi_id-only), verify maps to (roi_id, 1)
4. Integration: Analyze Flow → Detect Events → save → reload; events remain associated with (roi_id, 1)
