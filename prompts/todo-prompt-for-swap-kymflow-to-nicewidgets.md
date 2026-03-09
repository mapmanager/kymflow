switch kymflow/ to use nicewidgets image_line_widget

make a plan and put it in kymflow/ prompts/ todo-switch-kymflow-to-nicewidgets-image-line-widget.md

# current code in kymflow/

in kymflow/ gui_v2/ we have one main home page '/'. in this homepage we have a number of interacting nicegui widget. we have a left toolbar, then we have a vertical stacked layout of nicegui ui elements like (all these are in kymflow/ views/ folder):

 - folder selector, includes @kymflow/src/kymflow/gui_v2/views/folder_selector_view.py and @kymflow/src/kymflow/gui_v2/views/folder_selector_bindings.py 
 - file table view, includes @kymflow/src/kymflow/gui_v2/views/file_table_view.py and @kymflow/src/kymflow/gui_v2/views/file_table_bindings.py 
 - image line view, includes @kymflow/src/kymflow/gui_v2/views/image_line_viewer_view.py and @kymflow/src/kymflow/gui_v2/views/image_line_viewer_bindings.py 
 - kym event view, includes @kymflow/src/kymflow/gui_v2/views/kym_event_view.py and @kymflow/src/kymflow/gui_v2/views/kym_event_bindings.py 

we also have complementary controllers in kymflow/ gui_v2/ controllers/. please use the above list to explore controllers/ to find relationships.

we want to replace the contents of image line viewer (it is a merged image and line viewer) with two widgets from nicewidgets: image roi widget and line plot widget.

currently in kymflow/ gui_v2/ the image line view is one widget that contains both an image view and a line view. it is composed of the following files to implement the full model-view-controller (MVC) architecture:

 - @kymflow/src/kymflow/gui_v2/views/image_line_viewer_view.py 
 - @kymflow/src/kymflow/gui_v2/views/image_line_viewer_bindings.py 

other widgets in the current kymlfow/ gui_v2/ interact with the image line viewer including:

 - @kymflow/src/kymflow/gui_v2/views/kym_event_view.py 
 - @kymflow/src/kymflow/gui_v2/views/kym_event_bindings.py 

to swap the current image line view with the new nicewidgets/ image line widget (actuall two widgets, image roi widget and image plot widget) we need to examine the current status of all kymflow/ runtime events that come in and out of the current image line viewer (both for the kym image and the line plot).

examine the api(S) for both nicewidgets/ @nicewidgets/src/nicewidgets/image_line_widget/image_roi_widget.py and @nicewidgets/src/nicewidgets/image_line_widget/line_plot_widget.py , it is well defined and well documented. we should have sufficient api in the new nicewidgets/ to fully swap them in to kymflow/

one place where we can add a 'todo' is the @nicewidgets/src/nicewidgets/image_line_widget/line_plot_widget.py does not have an api to 'add user' event. we will add that once the swap is done.

# conclude

examine the above and devise a plan to swap out current @kymflow/src/kymflow/gui_v2/views/image_line_viewer_view.py (and associated aux file) for the new nicewidgets/ @nicewidgets/src/nicewidgets/image_line_widget/image_roi_widget.py and @nicewidgets/src/nicewidgets/image_line_widget/line_plot_widget.py 

no code edits, just make a plan in specified todo-switch-kymflow-to-nicewidgets-image-line-widget.md file.

plan should contain an overview of current MVC architecture of kymflow/ gui_v2/ and how widgets interact with existing @kymflow/src/kymflow/gui_v2/views/image_line_viewer_view.py and its aux files.

plan then needs to contain a step by step migration strategy for removing @kymflow/src/kymflow/gui_v2/views/image_line_viewer_view.py and replacing it with (@nicewidgets/src/nicewidgets/image_line_widget/image_roi_widget.py, @nicewidgets/src/nicewidgets/image_line_widget/line_plot_widget.py).

plan also needs to identify sticking points in making this transition, e.g. red flags that need to be addressed. propose extensio/reductions in kymflow/ gui_v2/ and the same for the two widgets in nicewidgets/ image_line_widget/

again, no code edits, just make a detailed plan. ask, do not guess. it is important to ask clarifying questions as you make the plan.