from kymflow.core.image_loaders.acq_image_list import AcqImageList
from kymflow.core.image_loaders.kym_image import KymImage
from kymflow.core.plotting.line_plots import plot_image_line_plotly_v2
from kymflow.core.analysis.stall_analysis import StallAnalysisParams

from kymflow.core.utils.logging import get_logger, setup_logging
logger = get_logger(__name__)

def plot_analysis(path: str) -> None:
    depth = 2
    kymList = AcqImageList(path, image_cls=KymImage, file_extension=".tif", depth=depth)
    for kymImage in kymList:
        roi_ids = kymImage.rois.get_roi_ids()
        # logger.info(kymImage.path)

        # already analyzed
        # ka = kymImage.get_kym_analysis()

        # analyze stalls
        # sap = StallAnalysisParams(
        #     velocity_key="velocity",
        #     refactory_bins=500,
        #     min_stall_duration=50,
        #     end_stall_non_nan_bins=2,
        # )
        
        # for roi_id in roi_ids:
        #     stall_analysis = ka.run_stall_analysis(roi_id, sap)
        #     logger.info(f'stall_analysis: {roi_id}')
        #     for stall in stall_analysis.stalls:
        #         logger.info(f'stall: {stall}')

        # ensure img data is loaded (for plotting)
        kymImage.load_channel(channel=1)

        # roi_ids = [roi_ids[0]]
        fig = plot_image_line_plotly_v2(kymImage,
                channel=1,
                selected_roi_id=roi_ids,
                transpose=True,
                plot_rois=True,
                yStat="velocity",
                remove_outliers=True,
                colorscale="Gray",
            )
        fig.show()
        
        break

def analyze_stalls(path: str) -> None:
    depth = 2
    kymList = AcqImageList(path, image_cls=KymImage, file_extension=".tif", depth=depth)

    # analyze stalls
    sap = StallAnalysisParams(
        velocity_key="velocity",
        refactory_bins=50,
        min_stall_duration=5,
        end_stall_non_nan_bins=2,
    )

    for kymImage in kymList:
        logger.info(kymImage.path)
        ka = kymImage.get_kym_analysis()
        for roi_id in kymImage.rois.get_roi_ids():
            stall_analysis = ka.run_stall_analysis(roi_id, sap)
            logger.info(f'stall_analysis: {roi_id}')
            for stall in stall_analysis.stalls:
                logger.info(f'stall: {stall}')

        # save analysis
        success = ka.save_analysis()
        logger.info(f'saved analysis: {success}')

def analyze_flow(path: str) -> None:

    depth = 2
    kymList = AcqImageList(path, image_cls=KymImage, file_extension=".tif", depth=depth)
    # print(kymList)

    # analyze stalls
    # sap = StallAnalysisParams(
    #     velocity_key="velocity",
    #     refactory_bins=500,
    #     min_stall_duration=50,
    #     end_stall_non_nan_bins=2,
    # )
    
    for kymImage in kymList:
        logger.info(kymImage.path)

        # Delete any existing ROIs (start fresh)
        deleted_count = kymImage.rois.clear()
        logger.info(f"Deleted {deleted_count} existing ROI(s)")

        # ensure img data is loaded
        kymImage.load_channel(channel=1)

        windows = [16, 32, 64]
        for _idx, window in enumerate(windows):
            # create roi for the window
            roi = kymImage.rois.create_roi()
            logger.info(f'created roi: {roi.id}')

            ka = kymImage.get_kym_analysis()
            
            # analyze flow
            logger.info(f'   analyze flow for roi {roi.id} window:{window}...')
            ka.analyze_roi(roi.id, window)

            # stall_analysis = ka.run_stall_analysis(roi.id, sap)
            # logger.info(f'stall_analysis: {roi.id}')
            # for stall in stall_analysis.stalls:
            #     logger.info(f'stall: {stall}')

        # save analysis
        success = kymImage.get_kym_analysis().save_analysis()

        
if __name__ == "__main__":
    setup_logging(level="INFO")
    path = "/Users/cudmore/Dropbox/data/declan/2026/declan-data-analyzed"
    path = '/Users/cudmore/Dropbox/data/declan/2026/data/20251204'

    # analyze_flow(path)

    # analyze_stalls(path)
    
    plot_analysis(path)
