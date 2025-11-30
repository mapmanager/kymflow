Make a contrast widget to adjust the image display.

We have a plotly image that is created in @line_plots.py with plot_image_line_plotly(). Like this:

"""
        fig.add_trace(
            go.Heatmap(
                z=image.T,
                x=image_time,
                colorscale="Gray",
                showscale=False,
            ),
            row=1,
            col=1,
        )
"""

- we are displaying an image, call it img. It is a 2d numpy array.
- I want a color LUT popup menu that contains color lookup tables like: red, green, glue, grays, grays inverted, plasma, etc. Make sure it is easy to add additional color LUT in the future.
- when user selects a color LUT we should update the image plot with that color.
- I want another plot, a image pixel intensity histogram where the x-axis is pixel intensity and y-axis (histogram) is count.
- I want a checkbox 'Log' that will toggle the y-axis between linear and log. Log should be the default.
- I want two int range sliders, one min and one max. Each will have range from min=0 to max=np.max(img). AS the user adjusts a slider, I want the image to be redisplayed with the min/max range using some simple thing in plotly image plots. I think it is called zmin/zmax or range or something.
- In the image plot, I want two vertical lines (v-line) that show the min and max values. As the sliders are adjusted, these v-lines should be updated.

Now, I am not sure how to incorporate this into our plot_image_line_plotly()? plot_image_line_plotly() is using subplots like:
"""
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.025,
        row_heights=[0.5, 0.5],  # Image gets 60%, line plot gets 40%
        # subplot_titles=("Kymograph", "Velocity vs Time"),
    )
"""

Maybe the proposed color LUT popup and the min/max sliders could be in theor own widget. Somehow signalling the img plot to (i) set range with zmin/zmax and adjust the v-lines.

Could be an event like update_image_display(minInt: int = None, maxInt: int = None, colorLUT:str = None). On color LUT fill in colorLUT, on either min/max slider, fill in BOTH minInt, and maxInt (not just one).

Please examine code, make a plan for these additions. Let me know what you think. Do not guess, ask. I want this new feature/code to be relatively independent and easy to manage in the future.

One big consideration is for now, our plot_image_line_plotly() is pure plotly. What we are proposing here is actually nicegui widgets (popup, min/max slider).Thus, all this new code must be in kym_gui/ I guess as a new component/ that somehow gets wired up to signal that the color LUT, image min/max has changed.

To do this, seems logical to me to use our event system in @state.py? But that makes me question, "are we ever using @state.py in the kym_core/ code"? Could it be useful in the kym_core/ code or should it be in kym_gui/? For example, I see run_flow_analysis() in @tasks.py but it, as an example, is only called from the gui?

This is getting a bit long winded.

At least implement (i) color LUT popup, (ii) min/max range sliders, (iii) v-lines in the plotly image plot, and wire up some sort of signal to adjust the display of the image when color LUT, or min/max is changed by the user.
