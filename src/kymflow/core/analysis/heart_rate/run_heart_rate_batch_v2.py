from pathlib import Path

from kymflow.core.image_loaders.kym_image_list import KymImageList
from kymflow.core.utils.logging import get_logger, setup_logging
setup_logging()
logger = get_logger(__name__)

from kymflow.core.analysis.heart_rate.heart_rate_batch import batch_run_and_save
from kymflow.core.analysis.heart_rate.heart_rate_pipeline import HRAnalysisConfig
from kymflow.core.analysis.heart_rate.heart_rate_pipeline import HeartRateAnalysis

def _get_csv_paths_from_kymimagelist(path:str) -> list[Path]:
    csv_paths = []
    logger.info(f'loading kymimagelist from {path}')
    kymImageList = KymImageList(path)
    for kymImage in kymImageList.images:
        ka = kymImage.get_kym_analysis()
        csv_path, _ = ka._get_save_paths()
        csv_paths.append(csv_path)
    return csv_paths

def batch_run_all_hr_analysis(path: str) -> None:
    """Batch run all heart rate analysis for all kymimage in kymimagelist.
    """
    csv_paths = _get_csv_paths_from_kymimagelist(path)

    logger.info(f'kymimagelist retrieved {len(csv_paths)} csv paths')

    # Optional: use defaults by passing cfg=None
    cfg = HRAnalysisConfig()

    # If roi_ids=None: compute ALL roi_id in each CSV
    logger.info('calling batch_run_and_save()')

    results = batch_run_and_save(
        csv_paths,
        roi_ids=None,
        cfg=cfg,
        overwrite=True,
        backend="process",   # "thread" (GUI-ish) or "serial" also supported
        n_workers=0,         # auto
    )

    logger.info(f'  done ...')

    # Minimal reporting
    n_ok = sum(1 for r in results if r.ok)
    n_fail = len(results) - n_ok
    print(f"batch_run_and_save: ok={n_ok} fail={n_fail}")

    for r in results:
        if not r.ok:
            print(f"FAIL: {r.csv_path} -> {r.error}")

def load_saved_hr_analysis(path: str) -> None:
    # after batch_run_all_hr_analysis,
    # we saved json for each hr analysis, reload all hr analysis from json

    # slow ...
    csv_paths = _get_csv_paths_from_kymimagelist(path)

    hr_analysis_list = []
    for csv_path in csv_paths:
        hr_analysis = HeartRateAnalysis.from_csv(csv_path)
        hr_analysis.load_results_json()
        hr_analysis_list.append(hr_analysis)
    
    logger.info(f'  loaded {len(hr_analysis_list)} hr analyses')
    
    summary = hr_analysis_list[0].getSummaryDict( compact=True )
    logger.info(f'  summary of first is:')
    from pprint import pprint
    pprint(summary)

    # plot first, need csv velocity and time
    import matplotlib.pyplot as plt
    from heart_rate_plots import plot_summary
    roi_id = 1
    time_s, velocity = hr_analysis_list[0].get_time_velocity(roi_id)
    fig, axs = plot_summary(time_s, velocity)
    plt.show()

if __name__ == "__main__":
    path = '/Users/cudmore/Downloads/kymflow_app/declan-stall-v1'

    # just one treatment
    path = '/Users/cudmore/Downloads/kymflow_app/declan-stall-v1/14d Saline'
    
    # batch_run_all_hr_analysis(path)

    load_saved_hr_analysis(path)