"""General purpose acquired image.
"""

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Tuple, Any
import numpy as np
import tifffile

from kymflow.core.utils.logging import get_logger
logger = get_logger(__name__)


@dataclass
class AcqImageHeader:
    """Header for acquired image.
    """
    x_pixels: int = 0
    y_pixels: int = 0
    z_pixels: int = 0

    x_scale: float = 1
    y_scale: float = 1
    z_scale: float = 1

    x_label: str = ""
    y_label: str = ""
    z_label: str = ""

    x_unit: str = ""
    y_unit: str = ""
    z_unit: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary representation of this ROI."""
        return asdict(self)

    @classmethod
    def from_img_data(cls, img_data: np.ndarray) -> "AcqImageHeader":
        """Load AcqImageHeader from image data.
        """
        ret = None
        if img_data.ndim == 2:
            ret = cls(x_pixels=img_data.shape[1], y_pixels=img_data.shape[0], z_pixels=1)
        elif img_data.ndim == 3:
            ret = cls(x_pixels=img_data.shape[1], y_pixels=img_data.shape[2], z_pixels=img_data.shape[0])
        else:
            raise ValueError(f"Image data must be 2D or 3D, got {img_data.ndim}D")
        return ret

class AcqImage:
    """General purpose acquired image.

    If path is specified, allows lazy loading of image data.
    If image is specified, it will be used instead of loading from path.
    """

    def __init__(self, path: str | Path | None,
                 img_data: np.ndarray | None = None,
                 load_image: bool = False,
                 ):
        self.path = Path(path) #  if path is not None else None
        self._img_data: np.ndarray | None = img_data
                
        # default header
        self._header = AcqImageHeader()

        logger.warning('-->> SETTING load_image = True')
        load_image = True

        if path is not None and load_image:
            logger.warning('1 xxx')
            self._img_data = tifffile.imread(self.path)
            logger.warning('2 xxx')
        
        # convert to 3d
        if self._img_data is not None:
            if self._img_data.ndim == 2:
                self._img_data = self._img_data[np.newaxis, :, :]
            elif self._img_data.ndim == 3:
                pass
            else:
                raise ValueError(f"Image data must be 2D or 3D, got {self._img_data.ndim}D")

            # header from img data
            self._header = AcqImageHeader.from_img_data(self._img_data)
        
        # try and load header from TIFF file or image data if it exists
        # if self.path is not None:
        #     self._header = AcqImageHeader.from_tif(self.path)
        # elif self._img_data is not None:
        #     self._header = AcqImageHeader.from_img_data(self._img_data)
        # else:
        #     logger.warning("No path or image data provided, header will be default values")

    def __str__(self):
        return f"path={self.path}, shape={self.shape}, header={self.header}"

    @property
    def shape(self) -> Tuple[int, int, int]:
        if self.img_data is None:
            return None
        return self.img_data.shape

    @property
    def img_data(self) -> np.ndarray:
        return self._img_data

    def get_img_data(self, channel: int = 1) -> np.ndarray:
        """Get image data.

        Placeholder, for now (developing KymImage) 
        """
        return self.img_data[0, :, :]

    @property
    def x_pixels(self) -> int:
        return self.img_data.shape[1]
    
    @property
    def y_pixels(self) -> int:
        return self.img_data.shape[2]
    
    @property
    def z_pixels(self) -> int:
        return self.img_data.shape[0]
    
    @property
    def x_scale(self) -> float:
        return self._x_scale

    @property
    def y_scale(self) -> float:
        return self._y_scale

    @property
    def z_scale(self) -> float:
        return self._z_scale

    @property
    def x_label(self) -> str:
        return self._x_label

    @property
    def y_label(self) -> str:
        return self._y_label

    @property
    def z_label(self) -> str:
        return self._z_label

    @property
    def x_unit(self) -> str:
        return self._x_unit

    @property
    def y_unit(self) -> str:
        return self._y_unit

    @property
    def z_unit(self) -> str:
        return self._z_unit

    @property
    def header(self) -> AcqImageHeader:
        return self._header