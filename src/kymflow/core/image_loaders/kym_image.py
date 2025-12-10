"""KymImage is a subclass of AcqImage that represents a kymograph image.
"""

from pathlib import Path
import numpy as np

from kymflow.core.image_loaders.acq_image import AcqImage
from kymflow.core.image_loaders.read_olympus_header import OlympusHeader

from kymflow.core.utils.logging import get_logger
logger = get_logger(__name__)

class KymImage(AcqImage):
    """KymImage is a subclass of AcqImage that represents a kymograph image.
    """

    def __init__(self, path: str | Path | None,
                 img_data: np.ndarray | None = None,
                 load_image: bool = False,
                 ):
        super().__init__(path=path, img_data=img_data, load_image=load_image)

        # self._olympus_header: OlympusHeader = OlympusHeader()  # header is default values

        # try and load Olympus header from txt file if it exists
        _olympus_header = OlympusHeader.from_tif(self.path)

        # from pprint import pprint
        # pprint(_olympus_header)

        # assign AcqImage properties from olympus header
        self.header.x_pixels = _olympus_header.num_lines
        self.header.y_pixels = _olympus_header.pixels_per_line
        self.header.seconds_per_line = _olympus_header.seconds_per_line
        self.header.um_per_pixel = _olympus_header.um_per_pixel


    @property
    def num_lines(self) -> int:
        """Number of lines scanned.
        """
        if self.img_data is None:
            return None
        return self.x_pixels
    
    @property
    def pixels_per_line(self) -> int:
        """Number of pixels per line.
        """
        if self.img_data is None:
            return None
        return self.y_pixels

    @property
    def image_dur(self) -> float:
        """Image duration (s).
        """
        return self.num_lines * self.header.seconds_per_line

    @property
    def seconds_per_line(self) -> float:
        return self.header.seconds_per_line

    @property
    def um_per_pixel(self) -> float:
        return self.header.um_per_pixel