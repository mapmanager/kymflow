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



#
# comments on the plan and potential steering for phase 9.

please examine the points below (be sure to finish with `conclusion (important)` section at end)

we can continue with your planned phase 9 (when we agree and I say to implement).

i want you to consider the followingas potential updates to phase 9. many of these points might be best if we even add a `phase 10` to the plan. examine and give me feedback.


# refactor radon analysis into its own file/class RadonAnalysis (radon_analysis.py)

1. KymAnalysis will own any number of relatively independent `analysis`:

 - RadonAnalysis, what we are working on in the current plan
 - VelocityAnalysis, what we will work on next
 - DiameterAnalysis, near future addition to KymAnalysis
 - HeartRateAnalysis, near future addition to KymAnalysis

For KymAnalysis to manage these different `analysis` (current plan is four different `analysis`), we need to decide on a public and internal API such that KymAnalysis can manage them with get, set, save, load

KymAnalysis can determine the folder to save to. It currently has _get_analysis_folder_path() and can continue to use this. KymAnalysis will determine the full folder path to save all its children `analysis` to.

Each analysis owned by KymAnalysis will determine the analysis file or files it will save to. For example RadonAnalysis will have fns to determine the name of its json (sidecar) and csv. Likewise, the new VelocityAnalysis will do the same, know the name of its json and csv files to save/load. The analysis children of KymAnalysis (currently, RadonAnalysis and VelocityAnalysis but in the future will include DiameterAnalysis and HeartBeatAnalysis) will know the names of files and will be given a folder path (from parent KymAnalysis) to save/load their respective files to/from.

KymAnalysis will still have _get_primary_path() -> the path of the tif file it was init() with.

In making children analysis for KymAnalysis (Eventually four different analysis), KymAnalysis will use each childs api to ask 'save your files' with a common api in all children like `save_analysis(folder_path: str | Path)`, likewise, KymAnalysis will rely on a common api in children analysis to load like `load_analysis(folder_path: str | Path)`

Currenlty, KymAnalysis has _get_save_paths() which hard coded one json/csv pair:

```
    def _get_save_paths(self) -> tuple[Path, Path]:
        """Get the save paths for analysis files.
        
        Returns:
            Tuple of (csv_path, json_path) for this acq_image's analysis.
        """
        analysis_folder = self._get_analysis_folder_path()
        primary_path = self._get_primary_path()
        if primary_path is None:
            raise ValueError("No file path available for save paths")
        base_name = primary_path.stem
        csv_path = analysis_folder / f"{base_name}_kymanalysis.csv"
        json_path = analysis_folder / f"{base_name}_kymanalysis.json"
        return csv_path, json_path
```

in your "Paths for radon artifacts", RadonAnalysis will determine its own analysis file names to save, these include names of the saved/load json and csv. KymAnalysis does not have to know about or determine these, it only provides a folder path to save/load.

in the refactored version, KymAnalysis will not know the csv/json names (like f"{base_name}_kymanalysis.csv" and f"{base_name}_kymanalysis.json) and will rely just on each childs save_analysis() and load_analysis() api.

for new RadonAnalysis to load old import_v0_analysis(), it just needs the folder path from kymanalysis and it will determine where v0 files are (they are in a different subfolder). the loading of old analysis with import_v0_analysis() is an edge case in that it will create an roi, this requires the RadonAnalysis to go up the chain -> parent kym analysis -> acqimage -> add roi. this is a one off import edge case and should be fine.

for, "Radon persistence (JSON + CSV) – currently combined with velocity events", it will not own, save, or load `accepted`, that is a kymanalysis property

One important detail, with this refactor kymanalysis will not be saving/loading any analysis files. it is ok it does not save/load its accepted attribute. the accepted attribute (outside scope of this plan) is actually owned by AcqImage (outside scope) that saves/loads its own json and will handle `accepted` at a file level. KymAnalysis will not need `accepted` in the future.

when saving/loading derived RadonAnalysis, it will not have to manager `"velocity_events": per-roi_id list of VelocityEvent.to_dict() plus a "channel" field`, this will be part of save/load defined in the new VelocityAnalysis.


2. to make KymAnalysis a container for any number of analysis (we will have 4 or more), we want to devise an architecture so we do not contaminate KymAnalysis with cluttered attributes (one for each child analysis) and member function.

To do this, I propose to define a new common class that all children analysis can derive from the common class, call it KymAnalysisBase will define a small api that KymAnalysis can use during runtime to manage its children analysis. Something like (I am open to suggestions):

    class KymAnalysisBase:
        # static name that each derived class must define
        analysis_name:str = 'Undefined'

        def __init__(self, kym_analysis_parent:KymAnalysis):
            self._parent_kymanalysis = kym_analysis_parent

    
        def save_analysis(self, path: str | Path):
            """save anything the derived class needs to save.
            Can be json, and or csv. Determined by derived class.
            """
    
        def load_analysis(self, path: str | PAth):
            ""Load all needed analysis files.
            Can be json, and or csv. Determined by derived class
            """
    
        def is_dirty(self) -> bool:
            """Return dirtly status during runtime.
            Derived classes will decide this.
            """

With this, kymanalysis can init(), load, and save a given child analysis. We still have to define the types of child analysis that KymAnalysis will own and how many. I vote to just hard code this (open to suggestions) in KymANalysis. So today, KymAnalysis will know how to import RadonAnalysis and Velocity analysis, in future it will import DiameterAnalysis and HeartRateAnalysis.

Kym analysis can init a general purpose (internal list or dict) of KymAnalysisBase objects. Then can iterate over these to load, save, get, set, etc.

In revising the plan, we can expand the api of KymAnalysisBase such that KymAnalysis can use it to do its runtime work, book-keeping, load, save, etc.

We can add a public api to KymAnalysis such that callers (e.g. in gui_v2/ and standalone scripts) can get known named analysis which internally uses KymAnalysisBase.analysis_name, for example an api for KymAnalysis like a member fn like get_analysis_object(self, name:str) where name is the known name of a given analysis defined in KymAnalysis.analysis_name (in RadonAnalysis this could be defined as just "RadonAnalysis', in VelocityAnalysis it could simple be "VelocityAnalysis"). 

in the future, if we put all KymAnalysisBase derived analysis classes we can actually do discovery during runtime by inspecting the files -> classes -> analysis_name of each type of child KymAnalysis we have. this is beyond scope of current plan.


3. concept of kymanalysis `dirty`, kymanalysis should retain its own _dirty:bool flag but to determine dirty states during runtime, needs to iterate over its kymanalysisbase objects to query each with kymanalysisbase.is_dirty().

kymanalysis will own one _accept:bool that can flag the entire kymanalysis (e.g. one src img file, tif for now) as accepted or not. Children analysis do not need the concept of _accept.


4. comments on your "2. Updated Phase 9 Implementation Plan (concrete)"

4.1 we want to sooner rather than later make each analysis (RadonAnalysis in this plan, next if VelocityAnalysis) define, load, save its own json file as well as its own csv file (if  it wants, radonanalysis has one, Velocity analysis does not but these are relagated to the class for each type of analysis).

we will need one more 'import' from version 2.0 json because they are combinded and shared between RadonAnalysis and VelocityAnalysis. currently, the version 2.0 json we have (it is a mixture of radonanalysis and velocityanalysis) looks like this (see below). in this, radonanalysis is in "analysis_metadata". in this each (3 events for this file) event in VelocityAnalysis is in "velocity_events".

to load this mixed json, kymanalysis just needs a clear version 2.0 import that will load the mixed json and delegate the contents to its new children via their api defined in KymAnalysisBase. ocnclude, we need a clear kymanalysis load version 2.0 as a migration path to load (the very few) json files we currently have saved.

```
{
  "version": "2.0",
  "accepted": true,
  "analysis_metadata": {
    "1": {
      "roi_id": 1,
      "algorithm": "mpRadon_v0",
      "window_size": 16,
      "analyzed_at": "2026-02-05T12:19:32.025289+00:00",
      "roi_revision_at_analysis": 0
    },
    "2": {
      "roi_id": 2,
      "algorithm": "mpRadon",
      "window_size": 16,
      "analyzed_at": "2026-02-05T12:23:01.116454+00:00",
      "roi_revision_at_analysis": 0
    }
  },
  "velocity_events": {
    "1": [
      {
        "event_type": "baseline_drop",
        "i_start": 1004,
        "i_peak": 1004,
        "i_end": null,
        "t_start": 4.564215833333333,
        "t_peak": 4.564215833333333,
        "t_end": null,
        "score_peak": -0.1168513631320029,
        "baseline_before": 0.4404327438709661,
        "baseline_after": 0.3235813807389632,
        "strength": 0.4674054525280116,
        "nan_fraction_in_event": null,
        "n_valid_in_event": null,
        "duration_sec": null,
        "machine_type": "stall_candidate",
        "user_type": "unreviewed",
        "note": ""
      },
      {
        "event_type": "baseline_drop",
        "i_start": 4742,
        "i_peak": 4742,
        "i_end": null,
        "t_start": 21.519285433333337,
        "t_peak": 21.519285433333337,
        "t_end": null,
        "score_peak": -0.11255708278706827,
        "baseline_before": 0.4846341574381712,
        "baseline_after": 0.3720770746511029,
        "strength": 0.4502283311482731,
        "nan_fraction_in_event": null,
        "n_valid_in_event": null,
        "duration_sec": null,
        "machine_type": "stall_candidate",
        "user_type": "unreviewed",
        "note": ""
      },
      {
        "event_type": "nan_gap",
        "i_start": 7016,
        "i_peak": null,
        "i_end": 7071,
        "t_start": 31.833846233333333,
        "t_peak": null,
        "t_end": 32.0833189,
        "score_peak": null,
        "baseline_before": null,
        "baseline_after": null,
        "strength": 0.12473633333333467,
        "nan_fraction_in_event": 0.5,
        "n_valid_in_event": 28,
        "duration_sec": 0.24947266666666934,
        "machine_type": "nan_gap",
        "user_type": "unreviewed",
        "note": ""
      }
    ]
  }
}
```

4.1 for your, "2.1 Step A – Introduce RadonAnalysis and move radon logic", "Methods moved here (radon-only):"

the new RadonAnalysis does not have to manage a folder path, it is given one by parent KymAnalysis on calling its public api for save/load. RadonAnalysis will have hard-coded str for the names of the csv and json it will load/save just to concept of path to save/load to/from (that is relegated to KymAnalysis).

a common external use of the new RadonAnalysis will be calling RadonAnalysis.get_analysis_value(). this does not have to be part of proposed common base class `KymAnalysisBase`, this can remain  a specific api that RadonAnalysis owns and callers (like in gui_v2/) just need to know about. i guess, the same can go for get_radon_report(), get_analysis()

for your, "Persistence helpers (radon side only):". we do not need to use "analysis_metadata" subtree at all. RadonAnalysis will save/load its own independent json with key/values specific to just RadonAnalysis. all derived `KymAnalysisBase` including RadonAnalysis do not need to save/load `accepted`

to rephrase your statements in "That is, RadonAnalysis will know how to:"

yes, "Populate its internal _analysis_metadata and _df from incoming JSON (and v0 path).", it is more simple, this will be populated from the json file that RadonAnalysis owns/manages (once we save it). For version 2.0 import we need a special function to implement this.

you said, "Produce an "analysis_metadata" subtree and possibly an updated _df for JSON/CSV saving." -> much more simple in that RadonAnalysis will just prodics a self contained json/csv that it owns and manages.

sure, the following is fine and should be a clear version 2.0 json load path: "For Phase 9, we can also keep the full save/load implementation inside RadonAnalysis and have KymAnalysis.save_analysis/load_analysis call directly into self._radon.save_analysis() and self._radon.load_analysis(), even though these still include velocity_events. That’s acceptable as a transitional design, and we can change it when we split JSON files."

4.2, for your, "2.2 Step B – Update KymAnalysis to delegate to RadonAnalysis"

can we generalize the children analysis that KymAnalysis will own. Can we put all children in a dict keyed by `KymAnalysisBase.analysis_name`? This would remove our KymAnalysis attributes like `self._radon = RadonAnalysis(acq_image)` and (in the next plan) `self._velocity_ = VelocityAnalysis(acq_image)` which is currently like this `self._velocity_events: Dict[int, List[VelocityEvent]] = {}`.

something like this:

    class KymAnalysis:
        def __init__(self, acq_image: AcqImage) -> None:
            ...
            self._analysis_children: Dict[str, KymAnalysisBase]
            ...

load/save in kymanalysis becomes an iterator over keys in _analysis_children

examine this proposal and give me feedback on its design and if this is possible to implement in the current plan.

we may want to just proceed with your plan and use KymAnalysis `self._radon = RadonAnalysis(acq_image)` for the plan. next plan would generalize it to a more structured datastructure like a dict keyed on KymAnalysisBase.analysis_name with values of derived classes from KymAnalysisBase.


in your, "For this Phase 9, to avoid blowing up JSON layout while we also modularize:". can we switch to having RadonAnalysis load/save its own independent json? can we do the following (you suggested) in the current plan:

```
RadonAnalysis can write *_radon.json.
KymAnalysis (or a VelocityEventAnalysis class) can write a separate *_events.json.
The old combined file can be supported for backward compatibility or via a migration step.
```

# conclusion (important)

This prompt contains many forward looking design propositions.

a. it re-iterates our agreed desire to have each analysis child save/load it own files (for example, not merged json).

b. it also proposes a new idea to have each child analysis derive from a common class, KymAnalysisBase, that provides most (if not all) the api that kymanalysis needs for its children.


examine the above details in this prompt. after you understand the prompt. i am happy to continue with your more conservative approach you defined like this:

```
3. JSON splitting (future, not in Phase 9)
Your suggestion of separate JSON files:
*_radon.json – radon analysis only (analysis_metadata, acceptance).
*_events.json – kym event analysis only (velocity_events, event CSV / DB cache).
This is a good idea and will:
Decouple radon and velocity-event persistence.
Make it much easier to evolve event schemas independently.
However, to minimize risk, we’ll:
Keep the existing combined JSON file for Phase 9 (but move its radon logic into RadonAnalysis).
Plan a separate follow-up change to:
Introduce the new JSON files.
Add migration/compat logic (e.g. read combined file and write out separate ones, or support both layouts).
```


# steering for phase 9

yes, i want to do the split in phase 9, you said, "Recommendation: do the split in Phase 9 if you’re okay with a migration step for old files"

in the split, accepted can just be part of acqimage, accepted does not have to be part of (in current plan) KymAnalysis or RadonAnalysis. no, we do not want an intermediate "accepted could go in a tiny metadata file", it is part of acqimage json.

for your, "1.6 Version 2.0 migration", yes i agree with the plan of "KymAnalysis (or a small migration helper) reads the combined file, pulls "analysis_metadata" and radon CSV into RadonAnalysis, and "velocity_events" into VelocityAnalysis (once it exists)"

for your comment in "1.7 import_v0_analysis edge case". can we just derive radon anaysis from acqimage and have it go 'up' to add an roi. can we design at least radon analysis to not know about parent kymanalysis? afaik, it will work if RadonAnalysis is just init() with acqimage, not kymanalysis? examine and determine if this is true.

for your, "2. Recommendation: Phase 9 vs Phase 10". can we use AcqAnalysisBase rather than KymAnalysisBase? With that rename, `_analysis_children: Dict[str, KymAnalysisBase]` becomes `_analysis_children: Dict[str, AcqAnalysisBase]`. Note, this is for Phase 10 as you are proposing.

phase 9 should implement "Separate *_radon.json / *_events.json", and "v2.0 combined-JSON migration". Velocity analysis is reserved for Phase 10 (need to coninue planning phase 10)

i want to go with your option B - Forward-looking phase 9, like this:

```
Option B – Forward-looking Phase 9
Same RadonAnalysis extraction.
Add KymAnalysisBase and a minimal _analysis_children (e.g. only "RadonAnalysis" for now).
RadonAnalysis writes *_radon.json and its CSV.
Implement v2.0 migration: read combined file once, delegate analysis_metadata and radon CSV to RadonAnalysis; leave velocity_events for VelocityAnalysis (or a stub) in Phase 10.
Velocity events remain on KymAnalysis until Phase 10.
```


# steering for proposed phase 10

instead of class KymAnalysisBase we can (rename it) AcqAnalysisBase in the init() could take acq_image:AcqImage param.

this works for analysis that entirely depend on acqimage such as RadonAnalysis and future DiameterAnalysis. Other analysis including our current work on VelocityAnalysis but also future HeartRateAnalysis will depend on results from RadonAnalysis, in particular the RadonAnalysis ocncept of get_analysis_value() which is currentl part of KymAnalysis.

We could make a class hiearchy of analysis inheritance like:

 - RadonAnalysis(AcqAnalysisBase)
 - VelocityAnalysis(RadonAnalysis)
 - DiameterAnalysis(AcqAnalysisBase)
 - HeartRateAnalysis(RadonAnalysis)

 here, both VelocityAnalysis and HeartRateAnalysis would know how to get (time, velocity) from its inherited RadonAnalysis, e.g. the current KymAnalysis function  get_analysis_value() which (some version of it) will be part of our new RadonAnalysis

# conclusion for steering phase 9

to answer your question, "If you prefer the split to happen in Phase 9, that’s feasible but increases scope. Which path do you want for Phase 9: (A) conservative, or (B) split files + migration?"

I want (b) split files + migration.

# final conclusion ofr this prompt

examine and understand the above suggestions/requirements

incorporate and update phase 9 and phase 10 as needed.

then, give me the status of phase 9 (brief) and we can decide if i accept and then i will ask to implement.

---

## Phase 9 Implementation Plan (Updated)

### Steering incorporated (1.a, 1.b)

- **No delegation on KymAnalysis**: `analyze_roi`, `get_analysis_value`, `has_analysis`, `get_analysis`, `get_analysis_metadata`, `get_radon_report` live **only** on RadonAnalysis. KymAnalysis does **not** expose these.
- **Callers go through getter**: Callers use `kym_analysis.get_analysis_object("RadonAnalysis")` to obtain the RadonAnalysis instance, then call its API directly (e.g. `.analyze_roi(...)`, `.get_analysis_value(...)`, `.has_analysis(...)`, `.get_radon_report()`).
- **1.a and 1.b in Phase 9**: Both are done in Phase 9. KymAnalysis API is reduced; all call sites are migrated to the new pattern.
- **Internal use**: KymAnalysis keeps velocity logic (including `run_velocity_event_analysis`). It will call `self._radon.get_analysis_value()` internally for (time, velocity) when needed. That is internal use, not part of the public API.

### API naming

- **KymAnalysis** exposes `get_analysis_object(name: str)` → returns the analysis object (e.g. `RadonAnalysis | None`). For Phase 9, only `"RadonAnalysis"` is supported.
- **RadonAnalysis** exposes `analysis_name: str = "RadonAnalysis"` (class attribute).
- **Naming**: Current `KymAnalysis.get_analysis(roi_id, channel)` (returns DataFrame) moves to RadonAnalysis. KymAnalysis uses `get_analysis_object(name)` for the analysis-object getter.

### Suggested implementation order

1. Create `radon_analysis.py` and move radon logic.
2. Add RadonAnalysis save/load for `*_radon.json` and `*_radon.csv`.
3. Add `*_events.json` for velocity_events.
4. Implement v2.0 migration in KymAnalysis.load_analysis.
5. Update KymAnalysis: add `get_analysis_object(name)`, remove radon-specific public methods, wire save/load.
6. **Update all call sites** to use `kym_analysis.get_analysis_object("RadonAnalysis").xxx()` instead of `kym_analysis.xxx()`.
7. Run tests and manual checks on existing data.

### How to begin implementation

Say: **"Implement Phase 9"** or **"Begin Phase 9 implementation"** to start. I will follow the suggested order above and the steering in this document.

### Call sites to update (summary)

- `tasks.py`: analyze_roi
- `analysis_toolbar_view.py`: has_analysis
- `kym_image.py`: has_analysis
- `kym_image_list.py`: get_radon_report (via `kym_image.get_kym_analysis()`)
- `_analyze_radon_roi_1.py`: analyze_roi, get_analysis_metadata
- `declan_analysis_2026.py`: analyze_roi
- `line_plots.py`, `stall_plots.py`, `image_line_viewer_v2_view.py`: has_analysis, get_analysis_value
- `core/analysis/velocity_events/tests/test_examples_smoke.py`: get_analysis_value
- `test_kym_analysis.py`, `test_tasks.py`, `test_analysis_toolbar_view.py`, `test_app_state_analysis.py`, `test_velocity_events.py`, `test_generate_velocity_events.py`, `test_velocity_event_uuid_lifecycle.py`, `test_velocity_event_db.py`, `test_kym_image_list.py`, `test_generate_rois.py`

---

## Phase 10 Plan (Summary)

- Introduce `AcqAnalysisBase(acq_image)` with `analysis_name`, `save_analysis(folder_path)`, `load_analysis(folder_path)`, `is_dirty()`.
- Retrofits `RadonAnalysis(AcqAnalysisBase)`.
- Introduce `VelocityAnalysis(RadonAnalysis)`; move velocity logic out of KymAnalysis.
- KymAnalysis uses `_analysis_children: Dict[str, AcqAnalysisBase]`; `get_analysis_object(name)` returns `_analysis_children.get(name)`.
- Future: `DiameterAnalysis(AcqAnalysisBase)`, `HeartRateAnalysis(RadonAnalysis)`.


# comments on "(a) Red Flags from Phase 9"

1. accepted location – Phase 9 stores accepted in *_events.json. The doc said it should be in AcqImage. Current behavior works, but Phase 10 may need to move accepted into AcqImage if that’s the target design.

this is not acceptable. the plan was specifically that `accepted` would be part of acqimage. `accepted` can not be part of any json saved by analysis, neither radon or event ... no analysis in the phase saves accepted. accepted is saved by acq image.

2. radonanalysis init is correct, it should be created with acq image. The idea is that most analysis (like radon analysis), while instantiated and owned by kymanalysis, does not itself depend in kym analysis. no action requested, i am just confirming, 'radon analysis is init with acqimage'.

4. general question. why does unit test, `test_generate_rois` need this `_radon(ka)._get_radon_paths(ka._get_analysis_folder_path())`?

5. yes, fix this ... "FutureWarning in RadonAnalysis – pd.concat([self._df, roi_df], ...) with empty/NA entries triggers a pandas FutureWarning in some tests. Should be handled before pandas changes behavior."

in your, "Existing red flags still relevant"

fix any of these that you can. in fixing, ask and do not guess:

a. RadonReport (from how-to-add-to-radon-report.md): from_dict() uses hardcoded type lists; new fields need to be added in the right branches.

b. RadonReport (frozen): Use dataclasses.replace or a new instance to change values.

c. Cache keyed by str(kym_image.path): If path is None, updates are skipped.


# in your "(b) Phase 10 Plan and Decisions"

when planning/implementing this, "Introduce AcqAnalysisBase(acq_image) with analysis_name, save_analysis(folder_path), load_analysis(folder_path), is_dirty()", examine current kymanalysis, radonanalysis, and planned velocityanalysis to determine the full api needed by base class AcqAnalysisBase. Include any common api needs/pattern used by our derived classes, keeping it KISS and DRY.

# for your "Decisions to make"

I agree with all your "suggested route". Please follow these suggestions and tell me if you decide to do otherwise.

# steering for phase 10

1. general question. If "VelocityAnalysis needs RadonAnalysis get_analysis_value() – inheritance from RadonAnalysis is preferred.", I agree with strategy. question is, how will KymAnalysis init() Valocity analysis when it is part of a more abstract dict with key name and value AcqAnalysisBase? Do not modify plan if not neccessary, just tell me how you will implement this.