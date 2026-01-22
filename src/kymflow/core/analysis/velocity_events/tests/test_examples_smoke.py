# tests/test_examples_smoke.py
"""
Smoke test: run detection on one example CSV/TIF pair and generate plots.

This is intentionally integration-ish:
(i) performs analysis
(ii) produces plots saved to disk (so CI doesn't need an interactive display)

Run (pytest):
    pytest -q

Run (script):
    python tests/test_examples_smoke.py
or:
    python tests/test_examples_smoke.py /path/to/your/data_dir

Outputs:
    <outdir>/<stem>_*.png
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt

from kymflow.core.image_loaders.kym_image import KymImage

from kymflow.core.analysis.velocity_events.velocity_events import detect_events
from kymflow.core.analysis.velocity_events.velocity_plots import (
    contrast_clip,
    plot_velocity_zoom,
    plot_kym_zoom_with_event,
    KymScaling,
)
from kymflow.core.utils.logging import get_logger, setup_logging
from matplotlib.figure import Figure

logger = get_logger(__name__)
setup_logging()

def getKymImage(tifPath:str):
    kymImage = KymImage(path=tifPath, load_image=True)
    return kymImage

def run_example(
    *,
    outdir: Path,
    tifPath: Optional[Path] = None,
    # stem: str = "20251204_A117_0004",
    zoom_sec: float = 1.0,  # 0.5,
    max_events: int = 3,
    save: bool = True,
) -> Figure | None:
    """Run one example analysis+plot generation.

    Parameters
    ----------
    outdir:
        Directory to write PNG outputs.
    data_dir:
        Directory containing <stem>.csv and <stem>.tif.
        If None, uses repo-relative tests/data.
    # stem:
    #     Base filename without extension.
    zoom_sec:
        Time window ±zoom_sec around event center for zoom plots.
    max_events:
        Number of top events to plot.
    save:
        If True, saves PNG files; if False, just constructs figures (useful for debugging).
    """

    # plt.switch_backend("Agg")

    # here = Path(__file__).resolve().parent
    # if data_dir is None:
    #     data_dir = here.parent / "data"

    # csv_path = Path(data_dir) / f"{stem}.csv"
    # tif_path = Path(data_dir) / f"{stem}.tif"

    # assert csv_path.exists(), f"Missing {csv_path}"
    # assert tif_path.exists(), f"Missing {tif_path}"

    # df = pd.read_csv(csv_path)
    # # IMPORTANT: you said for now filter roi_id==1 in real datasets;
    # # this seeded CSV already has one stream. If needed later, filter here.
    # t = df["time"].to_numpy(float)
    # v = df["velocity"].to_numpy(float)

    stem = Path(tifPath).stem

    # get t and v from KymImage
    kymImage = getKymImage(tifPath=tifPath)
    ka = kymImage.get_kym_analysis()
    if ka is None:
        logger.error(f"ka is None for tifPath:{tifPath}")
        return
    logger.info(f'{stem} has {ka.num_rois} rois')
    roi_id = 1
    t = ka.get_analysis_value(roi_id=roi_id, key="time")
    v = ka.get_analysis_value(roi_id=roi_id, key="velocity")

    import numpy as np
    logger.info(f'{stem} t: {type(t)} len:{len(t)} min:{np.min(t)} max:{np.max(t)} v: {type(v)} len:{len(v)} min:{np.min(v)} max:{np.max(v)}')

    logger.info('t:')
    print(t)
    logger.info('v:')
    print(v)

    events, debug = detect_events(t, v)

    logger.info(f"{stem} found {len(events)} events")
    # for ev in events[: max(10, max_events)]:
    #     logger.info(f"event: start={ev.t_start:.4f} end={ev.t_end} type={ev.machine_type.value} strength={ev.strength}")
    #     from pprint import pprint
    #     pprint(ev)

    # Not every file must produce events, but this seeded example should in our current suite
    # assert len(events) >= 1

    # scaling = read_scaling_from_csv_first_row(csv_path)
    scaling = KymScaling(delx_um_per_px=kymImage.um_per_pixel, delt_s_per_line=kymImage.seconds_per_line)
    # img = load_kym_tif(tif_path)
    img = kymImage.get_img_slice(channel=1)
    dispImg = contrast_clip(img, 1.0, 99.5)

    outdir.mkdir(parents=True, exist_ok=True)

    figList = []
    
    max_events = 10
    for i, ev in enumerate(events[:max_events], start=1):
        title_v = f"{stem} — {ev.machine_type.value} onset={ev.t_start:.3f}s strength={ev.strength}"
        title_k = f"{stem} — kym zoom — {ev.machine_type.value} onset={ev.t_start:.3f}s strength={ev.strength}"

        fig, (ax_v, ax_k) = plt.subplots(2, 1, sharex=True, figsize=(10, 6))

        # 1) velocity zoom
        plot_velocity_zoom(
            t,
            v,
            ev,
            zoom_sec=zoom_sec,
            title=title_v,
            ax=ax_v,
        )

        # 2) kym zoom
        plot_kym_zoom_with_event(
            dispImg,  # use contrast-clipped for display
            scaling,
            ev,
            zoom_sec=zoom_sec,
            title=title_k,
            alpha=0.4,
            span_sec_if_no_end=0.20,
            disp_time_space=dispImg,  # avoids re-clipping
            ax=ax_k,
        )

        fig.tight_layout()

        if save:
            out = outdir / f"{stem}_event{i:02d}_summary.png"
            fig.savefig(out, dpi=150)

            # Always close in tests/scripts to avoid memory growth when batch-running
            plt.close(fig)

        figList.append(fig)

    return figList

def test_example_produces_events_and_plots(tmp_path: Path) -> None:
    outdir = tmp_path / "velocity_test_outputs"
    run_example(outdir=outdir, save=True)


if __name__ == "__main__":
    # import sys

    # Allow: python tests/test_examples_smoke.py /path/to/data_dir
    # data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else None

    outdir = Path("tmp") / "velocity_test_outputs"
    # run_example(outdir=outdir, data_dir=data_dir, save=True)
    save = False

    # tifPath = '/Users/cudmore/Dropbox/data/declan/2026/data/20251204/20251204_A117_0002.tif'
    # tifPath = '/Users/cudmore/Dropbox/data/declan/2026/data/20251204/20251204_A117_0003.tif'
    tifPath = '/Users/cudmore/Dropbox/data/declan/2026/data/20251204/20251204_A117_0004.tif'
    # tifPath = '/Users/cudmore/Dropbox/data/declan/2026/data/20251204/20251204_A117_0005.tif'
    # tifPath = '/Users/cudmore/Dropbox/data/declan/2026/data/20251204/20251204_A117_0006.tif'

    figList = run_example(outdir=outdir, tifPath=tifPath, save=save)
    if figList is not None and save:
        logger.info(f"Wrote plots to: {outdir.resolve()}")
    else:
        # after figList created
        for fig in figList:
            fig.show()

        plt.show(block=False)
        plt.pause(0.1)  # give GUI a moment

        # keep the GUI responsive until user closes all
        while plt.get_fignums():
            plt.pause(0.1)