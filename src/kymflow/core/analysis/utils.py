"""General purpose analysis utils.
"""

from __future__ import annotations

import numpy as np
import scipy.signal

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)

def _removeOutliers_analyzeflow(y: np.ndarray) -> np.ndarray:
    """
    old v0 analyze flow -> analyzeflow with radon was doing this

    remove inf and 0 tan()
      np.tan(90 deg) is returning 1e16 rather than inf
      tan90or0 = (drewVelocity > 1e6) | (drewVelocity == 0)
      drewVelocity[tan90or0] = float('nan')

    this new version removes values +/- 1e6 but does not remove 0
    """
    
    # old v0 was removing 0, we do not want to do that
    # tan90or0 = (y > 1e6) | (y == 0)
    # tan90or0 = (y > 1e6)  # seems old v0 flowanalysis was doing this ???
    tan90or0 = ( (y > 1e6) | (y < -1e6) )  # in the new version, i do not want to remove 0 (it can be real)

    y[tan90or0] = float('nan')
    return y

def _removeOutliers_sd(y: np.ndarray) -> np.ndarray:
    """Nan out values +/- 2*std.
    
    This is different from old flow analysis in that it does not remove 0 values."""

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
