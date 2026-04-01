import pandas as pd
import plotly.io as pio

from kymflow.core.analysis.heart_rate.heart_rate_plots_plotly import (
    HRPlotlyConfig,
    plot_velocity_hr_overview_plotly,
    plot_hr_psd_welch_plotly,
    plot_hr_periodogram_lombscargle_plotly,
)

# load one of your CSVs
one_csv = '/Users/cudmore/Downloads/kymflow_app/declan-stall-v1/14d Saline/20251014/flow-analysis/20251014_A98_0002_kymanalysis.csv'

df = pd.read_csv(one_csv)
# if your CSV has multiple roi_id rows, filter before passing:
df1 = df[df["roi_id"] == 1]

t = df1["time"].to_numpy()
v = df1["velocity"].to_numpy()

cfg = HRPlotlyConfig()

fig_overview = plot_velocity_hr_overview_plotly(t, v, cfg=cfg)
fig_welch   = plot_hr_psd_welch_plotly(t, v, cfg=cfg)
fig_lomb    = plot_hr_periodogram_lombscargle_plotly(t, v, cfg=cfg)

pio.show(fig_overview)   # works with dict
pio.show(fig_welch)
pio.show(fig_lomb)