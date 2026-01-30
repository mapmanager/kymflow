"""
compare old v0.0 velocity to new v1.0 velocity  
compare old v0 velocity to new v1.0 velocity
"""

import pandas as pd
import numpy as np
from kymflow.core.image_loaders.kym_image import KymImage
import matplotlib.pyplot as plt

from kymflow.core.analysis.utils import _removeOutliers_sd, _removeOutliers_analyzeflow

def _printStats(y: np.ndarray, name: str) -> None:
    """print stats of y"""
    
    # print(f'{name} stats: n:{len(y)}, nan:{np.sum(np.isnan(y))}, min:{np.round(np.nanmin(y), 3)}, max:{np.round(np.nanmax(y), 3)} mean:{np.round(np.nanmean(y), 3)}')

    print(
        f"{name} stats: "
        f"n:{len(y)}, "
        f"nan:{np.sum(np.isnan(y))}, "
        f'zeros:{np.sum(y == 0)}, '
        f"min:{np.round(np.nanmin(y), 3)}, "
        f"max:{np.round(np.nanmax(y), 3)}, "
        f"mean:{np.round(np.nanmean(y), 3)}"
    )

def plot_compare(path: str) -> None:
    """plot old v0.0 velocity to new v1.0 velocity
    """
    kymImage = KymImage(path)
    ka = kymImage.get_kym_analysis()

    # old velocity is in folder <parent folder>-analysis,like "20251014-analysis"
    old_analysis_folder_path = kymImage.path.parent / f"{kymImage.path.parent.name}-analysis"
    # check if old analysis folder exists
    if not old_analysis_folder_path.exists():
        raise FileNotFoundError(f"Old analysis folder not found: {old_analysis_folder_path}")
    # old velocity csv is like "20251014_A98_0002.csv"
    old_vel_csv = old_analysis_folder_path / f"{kymImage.path.stem}.csv"
    # check that old csv exists
    if not old_vel_csv.exists():
        raise FileNotFoundError(f"Old velocity CSV not found: {old_vel_csv}")
    old_vel_df = pd.read_csv(old_vel_csv)
    old_vel = old_vel_df["velocity"].values
    # n_old_velocity = len(old_vel_df)
    # print(f"n_old_velocity: {n_old_velocity}")
    # print(old_vel_df.head())
    
    roi_ids = kymImage.rois.get_roi_ids()
    # 20260130, we only have one roi in our new analysis
    # roi_id = roi_ids[0]
    for roi_id in roi_ids:
        # old_vel = ka.get_analysis_value(roi_id=roi_id, key="velocity_v0")
        new_time = ka.get_analysis_value(roi_id=roi_id, key="time")
        new_vel = ka.get_analysis_value(roi_id=roi_id, key="velocity")
    
        # our new vel might not have removed large values
        #new_vel = _removeOutliers(new_vel)
        # manually remove new vel < 100000
        # new_vel[new_vel < -100000] = np.nan

        # analyze flow -> analyzeflowwith radon was doing this
        """
        # remove inf and 0 tan()
        # np.tan(90 deg) is returning 1e16 rather than inf
        tan90or0 = (drewVelocity > 1e6) | (drewVelocity == 0)
        drewVelocity[tan90or0] = float('nan')
        """

        # remove inf and 0 tan()
        # np.tan(90 deg) is returning 1e16 rather than inf
        # tan90or0 = (new_vel > 1e6) | (new_vel == 0)
        # tan90or0 = ( (new_vel > 1e6) | (new_vel < -1e6) )  # in the new version, i do not want to remove 0 (it can be real)
        # new_vel[tan90or0] = np.nan
        
        print('removing new v1 vel outliers like old v0 analyzeflow')
        new_vel = _removeOutliers_analyzeflow(new_vel)

        # to compare exactly what flowanalysis was doing
        # new_vel_no_zeros is new_vel with 0s set to nan
        new_vel_no_zeros = new_vel.copy()
        new_vel_no_zeros[new_vel_no_zeros == 0] = np.nan

        # compare stats of old and new velocity
        _printStats(old_vel, 'old         ')
        _printStats(new_vel_no_zeros, 'new no zeros')
        _printStats(new_vel, 'new         ')

        # make a second figure with old/new on same plot
        fig, ax = plt.subplots()
        ax.plot(old_vel_df["time"], old_vel_df["velocity"], label="old")
        ax.plot(new_time, new_vel, label="new")
        ax.legend()
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Velocity")
        # ax.set_title(f"ROI {roi_id}")

        plt.show()
        break

if __name__ == "__main__":
    path = '/Users/cudmore/Dropbox/data/declan/2026/compare-condiitons/box-download/14d Saline/20251014/20251014_A98_0002.tif'
    plot_compare(path)