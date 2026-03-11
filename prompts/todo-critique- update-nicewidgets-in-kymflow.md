1. intro to logic:

in @kymflow/src/kymflow/gui_v2/views/image_line_viewer_v2_view.py is see this runtime flow:

 -> set_selected_file()
 -> _set_selected_file_impl()
 -> _refresh_from_state()

then we call functions for

a. image roi widget:
 -> _update_image_for_file_change()
b. line plot widget:
 -> _update_line_for_current_roi()
 -> _update_events_for_current_roi()

in general the gui file selection, originates in file table view (user click row0 -> bus -> bus emit state event FileSelection.

FileSelection is defined in @kymflow/src/kymflow/gui_v2/events.py here: @events.py (53-54) 

2. focus on @kymflow/src/kymflow/gui_v2/views/image_line_viewer_v2_view.py _update_image_for_file_change()

2.1. the main work is done here: self._image_roi_widget.set_file(manager, rois)

in @nicewidgets/src/nicewidgets/image_line_widget/image_roi_widget.py set_file() i have some concerns and questions.

we do a full rebuild with `ViewGenerator.full_build()`, my main question is, is this full build neccessary? is it slow compared to other less intrusive builds? in @nicewidgets/src/nicewidgets/image_line_widget/image_roi_config.py ViewGenerator.full_build(...) we basically build 'data' and 'layout' keys for the plotly dict that is used by nicegui ui.plotly(), this dict will be updated in nicegui when we call update() on it.

i see this: @image_roi_config.py (89-91) which might be expensive and not neccessary (or best to due) at this level of the code. it is basically creating the correct x/y axis scale/units for the heatmap. can this be pre-calculated somewhere else? why do we do that level of detail and computation/work in our plotly dict building. suggest where this could be moved to and how it could be more efficient

```
                'x': (np.arange(nx) * mgr.row_scale).tolist(),
                'y': (np.arange(ny) * mgr.col_scale).tolist(),

```

2.2 in set_file() we have:

self.plot_dict['layout']['shapes'] = self._get_shapes_for_layout()

after the call to 

@image_roi_widget.py (286-288) 
        new_build = ViewGenerator.full_build(
            self.manager, self.config, list(self.rois.values()), theme=self._theme
        )

but in ViewGenerator.full_build() we also have `'shapes': ViewGenerator.generate_shapes(rois, mgr, cfg),` when constructing the 'layout' key for the plotly dict.

this seems redundant and should, afaik, be done once and in one place? examine and let me know if this is actually redundant and how to make this more efficient, more DRY, more KISS.

to conclude, I want to make ViewGenerator.full_build() and @nicewidgets/src/nicewidgets/image_line_widget/image_roi_widget.py set_file() as focused, efficient, dry, and kiss as possible.

please examine and report your findings in the chat.

this item is of critical importance, e.g. 2, 2.1, 2.2. please examine and suggest improvements in chat with pros/cons, etc.


2.3. do we need to set theme in FileSelection event? we have self._theme already? do we need to set again?

 - theme_str = _to_nicewidgets_theme(self._theme)
 - self._image_roi_widget.set_theme(theme_str)

2.4. similar question on self._display_params. do we need to set colorscale and set_contrast() on FileSelection event consumption?

we set like this, here @image_line_viewer_v2_view.py (264-271) 

```
        if self._display_params:
            self._image_roi_widget.set_colorscale(self._display_params.colorscale)
            if self._display_params.zmin is not None or self._display_params.zmax is not None:
                self._image_roi_widget.set_contrast(
                    zmin=self._display_params.zmin,
                    zmax=self._display_params.zmax,
                )

```

2.5 we then set the selected roi by name with select_roi_by_name()

my question, we use self._current_roi_id but I do not see where it is assigned? I do see that the kymflow event FileSelection has an attribute for `roi_id: int | None = None`. DO we use that in the call chain leading to _update_image_for_file_change(), see "(1) ... a. image roi widget" above.

do we use  provided FileSelection state event roi_id?


3. can we add image roi widget and plot line widget as consumers of ThemeChanged? DO we take a theme when we are first init() by the home page or similar? if we init with theme, it basically does not change until we recieve and consume a ThemeChanged event.

theme change event in kymflow @kymflow/src/kymflow/gui_v2/events_state.py is:

```
@dataclass(frozen=True, slots=True)
class ThemeChanged:
    """AppState theme change notification.

    Emitted by AppStateBridgeController when AppState.set_theme() is called
    and the theme mode changes. Views subscribe to this to update their
    UI when the theme changes.

    Attributes:
        theme: New theme mode (DARK or LIGHT).
    """

    theme: ThemeMode

```

4. i have very similar questions for the code in @kymflow/src/kymflow/gui_v2/views/image_line_viewer_v2_view.py _refresh_from_state() that calls similar functions for line plot widget, e.g.

            self._update_line_for_current_roi()
            self._update_events_for_current_roi()


in _update_line_for_current_roi(), we do not need to specify (And shold not specify) remove_outliers and median_filter in calling get_analysis_value(). I comment them out and now code is:

@image_line_viewer_v2_view.py (292-298) 
```
        vel_arr = kym_analysis.get_analysis_value(
            roi_id,
            "velocity",
            # remove_outliers=False,
            # median_filter=0,
        )

```

in _update_line_for_current_roi(), we should not do this work (See @image_line_viewer_v2_view.py (301-302) ):

        x_line = np.asarray(time_arr, dtype=float)
        y_line = np.asarray(vel_arr, dtype=float)

kym_analysis.get_analysis_value() already returns a np array? why would we even cast to `float`, we do not know this detail (and should not do this kind of work) at the view level. this cast to float makes me nervous that other code in our image roi and line plot view is doing too much and make too many assumptions.

once we do this assignment of x_line and y_line, the runtime flow eventually gets to @nicewidgets/src/nicewidgets/image_line_widget/_relayout_helpers.py trace_dict() which has signature:

    x: Union[np.ndarray, List[float]],
    y: Union[np.ndarray, List[float]],


so from earlier in the call chain, we hard code a (probably not needed) cast form return of kym_analysis.get_analysis_value() to a `np.asarray(..., dtype=float)` but then deeper down and later in call chain, trace_dict() has type hints for union like:

    x: Union[np.ndarray, List[float]],
    y: Union[np.ndarray, List[float]],

then, trace_dict() is doing this:

    x_list = x.tolist() if isinstance(x, np.ndarray) else list(x)
    y_list = y.tolist() if isinstance(y, np.ndarray) else list(y)

to conclude on point (4), this seems very disorganized and there may be 2-3 too many conversions and construction happening. 

examine this analysis (e.g. (4)) and propose how to make this more efficient.


# conclude

please examine above. give a summary of actionable items to address these topics (in the chat)

we want ot make sure the consumption of app level events by image line widgets (image roi widget and line plot widget) are streamlined, efficient, dry, and kiss.


