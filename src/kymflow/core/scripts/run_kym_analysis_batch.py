#!/usr/bin/env python3
"""Headless batch kym-event analysis (edit constants, then run from repo).

Run from the ``kymflow`` project directory with the package on the environment
(``uv run`` / editable install), for example::

    uv run python -m kymflow.core.scripts.run_kym_analysis_batch

There are **no command-line arguments**. Adjust the constants in this file,
save, and re-run. This script is for interactive exploration and reproducibility.

The batch runner is :class:`~kymflow.core.kym_analysis_batch.kym_analysis_batch.KymAnalysisBatch`;
results are stored on each file's :class:`~kymflow.core.image_loaders.kym_analysis.KymAnalysis`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from kymflow.core.analysis.velocity_events.velocity_events import BaselineDropParams
from kymflow.core.kym_analysis_batch import KymAnalysisBatch, KymEventBatchStrategy
from kymflow.core.image_loaders.kym_image import KymImage

# ---------------------------------------------------------------------------
# Edit these for your run (no CLI — manual edits only).
# ---------------------------------------------------------------------------

# Example: single file path, or set FILES to a list of Path.
SAMPLE_TIF: Path | None = None

# If SAMPLE_TIF is None, set FILES to a non-empty list of paths to analyze.
FILES: list[Path] = []

# Batch options
CHANNEL = 1
ROI_MODE: Literal["existing", "new_full_image"] = "existing"
ROI_ID: int | None = 1
MAX_PARALLEL_FILES = 4


def main() -> None:
    """Load images, run batch, print per-file outcomes."""
    paths: list[Path] = []
    if SAMPLE_TIF is not None:
        paths.append(SAMPLE_TIF)
    paths.extend(FILES)
    if not paths:
        print("Set SAMPLE_TIF or FILES in this script, then re-run.")
        return

    kym_files: list[KymImage] = []
    for p in paths:
        p = p.expanduser()
        if not p.exists():
            print(f"Skip missing path: {p}")
            continue
        kym_files.append(KymImage(p, load_image=True))

    if not kym_files:
        print("No valid files to analyze.")
        return

    baseline = BaselineDropParams()
    strategy = KymEventBatchStrategy(
        roi_mode=ROI_MODE,
        roi_id=ROI_ID,
        channel=CHANNEL,
        baseline_drop_params=baseline,
        nan_gap_params=None,
        zero_gap_params=None,
    )
    batch = KymAnalysisBatch(kym_files, strategy, max_parallel_files=MAX_PARALLEL_FILES)
    results = batch.run()

    for r in results:
        p = getattr(r.kym_image, "path", None)
        label = str(p) if p is not None else "?"
        print(f"{label}\t{r.outcome.value}\t{r.message}")


if __name__ == "__main__":
    main()
