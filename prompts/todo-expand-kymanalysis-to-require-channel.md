start making a plan to require channel in analysis for kym_analysis.py radon analysis

examine this overview of how to update kymanalysis.py

examine this outline and examine relevant code.

once you have an understanding of the goals, tasks, extent, etc ... give me an overview of the current radon analysis in kymanalysis and a structured plan (multiple phases) to achieve the goals.

we will go back and forth revising this plan.

once you have examined and explained the goals and plan, ask any clarifying questions needed. ask, do not guess.

this is a breaking plan for external callers, most of them are in kymflow/ gui_v2/. we do not want to provide extensive backwards compatibility or fallback code. we want to extend this analysis to include channel:int throughout, once we are done, we can refactor the gui_v2/ callers.

make a plan, no code edits. respond in the chat

# intro

kymanalysis has two different analysis:

 (i) radon flow analysis
 (ii) velocity event (kym event analysis)

we need to update how the first (i) is done in kymanalysis.

we will call this original form of analysis in kymanalysis, 'radon analysis'

the attributes that are involved are:

        self._analysis_metadata: Dict[int, RoiAnalysisMetadata] = {}
        self._df: Optional[pd.DataFrame] = None

in general, we also will be refactoring acqimage rois roilist class ROI, it currently has channel:int, we will be removing channel:int from class ROI. The channel will be imposed on an ROI when data is radon analyzed, radon analysis saved and loaded, radon analysis queried.

once we refactor all code to use channel:int we will refactor kymanalysis to move and seperate concerns, making radon anlysis a self contained class that is owned by kymanalysis.

## what we are not modifying. the second (ii) analysis in kymanalysis, uses attributes

        self._velocity_events: Dict[int, List[VelocityEvent]] = {}

is often reffered to interchangibly as kym event, velocity event, etc. we are leaving this code alone.

we are focused on the other (i) analysis and are calling it radon analysis.

# goal

the primary goal of this plan is to extend class kymanalysis radon analysis to do one simple thing, 'add channel:int' throughout the codebase for radon analysis in kymanalysis.

please examine, repeat back to me, and explain this goal

# update helper classes

## this needs to have channel:int

@dataclass
class RoiAnalysisMetadata:
    """Analysis metadata for a specific ROI.

    ROI geometry (dim0_start/dim0_stop/dim1_start/dim1_stop, channel, z) lives in AcqImage.rois.
    This stores only analysis state/results metadata.
    """

    roi_id: int
    algorithm: str = "mpRadon"
    window_size: int | None = None
    analyzed_at: str | None = None  # ISO-8601 UTC string
    roi_revision_at_analysis: int = 0

## this needs channel:int

class VelocityReportRow(TypedDict):


# radon analysis api in kymnalysis:

the api to get/set the radon flow analysis is here (there might be other api i missed)

## metadata

these are api functions for radon analysis metadata:

    def has_analysis(self, roi_id: int | None = None) -> bool:
    def get_analysis_metadata(self, roi_id: int) -> RoiAnalysisMetadata | None:
    def has_v0_flow_analysis(self, roi_id:int) -> bool:
    def is_stale(self, roi_id: int) -> bool:
    def invalidate(self, roi_id: int) -> None:

## analysis results

these are functions that access the radon analysis results stored as a pandas df (saved/loaded to csv)

    def _remove_roi_data_from_df(self, roi_id: int) -> None:
 
## main radon analysis entry point

this is the main analysis function that generates radon analysis, it needs a channel:int param. this is simple as, we can just replace the channel param here: channel = roi.channel. once we pass as a param, the remaining analysis like `image = self.acq_image.get_img_slice(channel=channel)` procedes pretty much unchanged.


    def analyze_roi(
        self,
        roi_id: int,
        window_size: int,
        *,
        progress_queue: Optional[queue.Queue] = None,
        is_cancelled: Optional[CancelCallback] = None,
        use_multiprocessing: bool = True,
    ) -> None:

1. expand analyze_roi to require a channel:int

```
    def analyze_roi(
        self,
        roi_id: int,
        window_size: int,
        *,
        progress_queue: Optional[queue.Queue] = None,
        is_cancelled: Optional[CancelCallback] = None,
        use_multiprocessing: bool = True,
    ) -> None:

```

## radon analysis helpers:

note, v0 analysis is an older version of radon analysis that we still provide loading functions for

    def _make_velocity_df(self, velocity: np.ndarray, time_values: np.ndarray, roi: ROI) -> pd.DataFrame:
    # needs channel:int
    def _create_empty_velocity_df(self) -> pd.DataFrame:
    def _try_load_v0_into_existing_roi(self) -> bool:
    def import_v0_analysis(self) -> Optional[bool]:
    def save_analysis(self) -> bool:

    def get_analysis(self, roi_id: Optional[int] = None) -> Optional[pd.DataFrame]:

# primary api (there are others)

this is primary externally used function, most callers will have access to the required channel:int

in this plan, we might want to leave this or at least a version of this so we do not break our caller api. it is critical that we eventually get channel:int into this function).

    def get_analysis_value(
        self,
        roi_id: int,
        key: str,
        remove_outliers: bool = False,
        median_filter: int = 0,
    ) -> Optional[np.ndarray]:


### save radon analysis, see save_analysis()

save_analysis() needs to be sure it saves/loads json with channel:int (Remember, when radon analysis is performed, it will always be performed on a (roi_id, channel)

for json data, we can bump version str in json and provide code to load version="2.0" which will be lacking channel

in the new radon analysis json dict we need channel:int here:

```
            # Prepare JSON data (analysis metadata only; no ROI geometry)
            json_data = {
                "version": "2.0",
                "accepted": self._accepted,
                "analysis_metadata": {
                    str(rid): {
                        "roi_id": meta.roi_id,
                        "algorithm": meta.algorithm,
                        "window_size": meta.window_size,
                        "analyzed_at": meta.analyzed_at,
                        "roi_revision_at_analysis": meta.roi_revision_at_analysis,
                    }
                    for rid, meta in self._analysis_metadata.items()
                },
                # DEPRECATED: Stall analysis is deprecated
                # "stall_analysis": {
                #     str(rid): sa.to_dict() for rid, sa in self._stall_analysis.items()
                # },
                "velocity_events": {
                    str(rid): [ev.to_dict() for ev in evs]
                    for rid, evs in self._velocity_events.items()
                },
            }
```

### load radon analysis, see load_analysis()


# conclude

examine above and follow instructions. answer in chat. no edits.