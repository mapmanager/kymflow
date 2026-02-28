import pandas as pd

from kymflow.core.image_loaders.kym_image_list import KymImageList
from kymflow.core.utils.logging import get_logger, setup_logging

from heart_rate_pipeline import HeartRateAnalysis
from heart_rate_plots import HRPlotConfig
from pprint import pprint

logger = get_logger(__name__)
setup_logging()

def run(path):
    kym_images = KymImageList(path=path)
    print(kym_images)

    cfg = HRPlotConfig()

    summary_list = []

    for _idx, kym_image in enumerate(kym_images):
        # print(kym_image.path)
        ka = kym_image.get_kym_analysis()
        csv_path, json_path = ka._get_save_paths()

        analysis = HeartRateAnalysis.from_csv(csv_path)
        roi_id = 1
        hr_per_roi_result = analysis.run_roi(roi_id, cfg=cfg)
        mini_summary = analysis.get_roi_summary(roi_id, minimal="mini")

        # print(f'{_idx} {kym_image.path.name}')
        summary_list.append(mini_summary)

    df = pd.DataFrame(summary_list)
    logger.info(f'saving {len(df)} to hr_summary_db.csv')
    df.to_csv('hr_summary_db.csv', index=False)
    print(df[['file', 'roi_id', 'lomb_bpm']].head())
    print(df.columns)

if __name__ == "__main__":
    path = "/Users/cudmore/Downloads/kymflow_app/declan-stall-v1/14d Saline"
    run(path)