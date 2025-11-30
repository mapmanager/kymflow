"""General purpose analysis utils.
"""

from __future__ import annotations

import numpy as np
import scipy.signal

from .utils.logging import get_logger

logger = get_logger(__name__)

def _removeOutliers(y: np.ndarray) -> np.ndarray:
    """Nan out values +/- 2*std."""

    # trying to fix plotly refresh bug
    # _y = y.copy()
    _y = y

    _mean = np.nanmean(_y)
    _std = np.nanstd(_y)

    _greater = _y > (_mean + 2 * _std)
    _y[_greater] = np.nan  # float('nan')

    _less = _y < (_mean - 2 * _std)
    _y[_less] = np.nan  # float('nan')

    # _greaterLess = (_y > (_mean + 2*_std)) | (_y < (_mean - 2*_std))
    # _y[_greaterLess] = np.nan #float('nan')

    return _y


def _medianFilter(y: np.ndarray, window_size: int = 5) -> np.ndarray:
    """Apply a median filter to the array."""
    return scipy.signal.medfilt(y, window_size)
