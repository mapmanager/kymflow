# hide_plotly_toolbar_nicegui.py
from nicegui import ui
import numpy as np

x = np.arange(50).tolist()
y = (np.random.randn(50)).tolist()

fig_dict = {
    "data": [{"type": "scatter", "mode": "markers", "x": x, "y": y}],
    "layout": {"title": {"text": "Modebar toggle (NiceGUI workaround)"}},
}

plot = ui.plotly(fig_dict).classes("w-full")

def set_modebar(show: bool) -> None:
    # Plotly config is NOT part of the figure dict; set it via NiceGUI's internal props.
    plot._props.setdefault("options", {})
    plot._props["options"]["config"] = {"displayModeBar": show}
    plot.update()  # re-send props to the client

ui.button("Hide modebar", on_click=lambda: set_modebar(False))
ui.button("Show modebar", on_click=lambda: set_modebar(True))

ui.run()