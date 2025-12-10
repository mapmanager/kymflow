"""Parser for Olympus microscope header files.

This module provides functionality to parse Olympus .txt header files that
accompany kymograph TIFF files. The header files contain acquisition parameters
such as spatial and temporal resolution, image dimensions, and acquisition
date/time.
"""

import os

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from pathlib import Path
from dataclasses import asdict, fields

from kymflow.core.metadata import field_metadata

from kymflow.core.utils.logging import get_logger
logger = get_logger(__name__)

@dataclass
class OlympusHeader:
    """Structured representation of Olympus microscope header metadata.

    Contains acquisition parameters extracted from the Olympus .txt header file
    that accompanies kymograph TIFF files. All fields have default values to
    handle cases where the header file is missing.

    Attributes:
        um_per_pixel: Spatial resolution in micrometers per pixel.
        seconds_per_line: Temporal resolution in seconds per line scan.
        duration_seconds: Total recording duration in seconds.
        pixels_per_line: Number of pixels in the spatial dimension.
        num_lines: Number of line scans in the temporal dimension.
        bits_per_pixel: Bit depth of the image data.
        date_str: Acquisition date string from header.
        time_str: Acquisition time string from header.
        raw: Raw dictionary of all parsed header values.
    """

    # OlympusHeader needs defaults in case corresponding Olympus txt file is not found
    um_per_pixel: Optional[float] = field(
        default=1.0,
        metadata=field_metadata(
            editable=False,
            label="um/pixel",
            widget_type="text",
            grid_span=1,
        ),
    )
    seconds_per_line: Optional[float] = field(
        default=0.001,  # 1 ms
        metadata=field_metadata(
            editable=False,
            label="seconds/line",
            widget_type="text",
            grid_span=1,
        ),
    )
    duration_seconds: Optional[float] = field(
        default=None,
        metadata=field_metadata(
            editable=False,
            label="Duration (s)",
            widget_type="text",
            grid_span=1,
        ),
    )
    pixels_per_line: Optional[int] = field(
        default=None,
        metadata=field_metadata(
            editable=False,
            label="Pixels/Line",
            widget_type="text",
            grid_span=1,
        ),
    )
    num_lines: Optional[int] = field(
        default=None,
        metadata=field_metadata(
            editable=False,
            label="Lines",
            widget_type="text",
            grid_span=1,
        ),
    )
    bits_per_pixel: Optional[int] = field(
        default=None,
        metadata=field_metadata(
            editable=False,
            label="Bits/Pixel",
            widget_type="text",
            grid_span=1,
        ),
    )
    date_str: Optional[str] = field(
        default=None,
        metadata=field_metadata(
            editable=False,
            label="Date",
            widget_type="text",
            grid_span=1,
        ),
    )
    time_str: Optional[str] = field(
        default=None,
        metadata=field_metadata(
            editable=False,
            label="Time",
            widget_type="text",
            grid_span=1,
        ),
    )
    raw: Dict[str, Any] = field(
        default_factory=dict,
        metadata=field_metadata(
            editable=False,
            label="Raw",
            widget_type="text",
            grid_span=2,  # Full width for raw dict
            visible=False,  # Hide raw dict from form display
        ),
    )

    @classmethod
    def from_tif(cls, tif_path: Path) -> "OlympusHeader":
        """Load Olympus header from accompanying .txt file.

        Attempts to parse the Olympus header file that should be in the same
        directory as the TIFF file with the same base name.
        
        Returns a header
        with default values if the file is not found or cannot be parsed.

        Args:
            tif_path: Path to the TIFF file. The corresponding .txt file will
                be looked up in the same directory.

        Returns:
            OlympusHeader instance with parsed values,
            or default values if the header file is missing.
        """
        parsed = _readOlympusHeader(str(tif_path))
        if not parsed:
            return cls()
        return cls(
            um_per_pixel=parsed.get("umPerPixel"),
            seconds_per_line=parsed.get("secondsPerLine"),
            duration_seconds=parsed.get("durImage_sec"),
            pixels_per_line=parsed.get("pixelsPerLine"),
            num_lines=parsed.get("numLines"),
            bits_per_pixel=parsed.get("bitsPerPixel"),
            date_str=parsed.get("dateStr"),
            time_str=parsed.get("timeStr"),
            raw=parsed,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with renamed keys.

        Returns:
            Dictionary representation with date_str and time_str renamed to
            date and time for compatibility with external APIs.
        """
        d = asdict(self)
        # Rename keys
        d["date"] = d.pop("date_str", None)
        d["time"] = d.pop("time_str", None)
        return d

    @classmethod
    def form_schema(cls) -> List[Dict[str, Any]]:
        """Return field schema for form generation.

        Generates a list of field definitions with metadata extracted from
        the dataclass field definitions. Used by GUI frameworks to dynamically
        generate forms without hardcoding field information.

        Returns:
            List of dictionaries, each containing field name, label, editability,
            widget type, grid span, visibility, and field type information.
            Fields are ordered by their declaration order in the dataclass.
        """
        schema = []
        for field_obj in fields(cls):
            meta = field_obj.metadata
            schema.append(
                {
                    "name": field_obj.name,
                    "label": meta.get(
                        "label", field_obj.name.replace("_", " ").title()
                    ),
                    "editable": meta.get("editable", True),
                    "widget_type": meta.get("widget_type", "text"),
                    "grid_span": meta.get("grid_span", 1),
                    "visible": meta.get("visible", True),
                    "field_type": str(field_obj.type),
                }
            )

        # Order is determined by the order of the fields in the dataclass
        return schema

    def get_editable_values(self) -> Dict[str, str]:
        """Get current values for editable fields only.

        Returns:
            Dictionary mapping field names to string representations of their
            current values. Only includes fields marked as editable in the
            form schema. None values are converted to empty strings.
        """
        schema = self.form_schema()
        values = {}
        for field_def in schema:
            if field_def["editable"]:
                field_name = field_def["name"]
                value = getattr(self, field_name)
                # Convert to string, handling None and dict types
                if value is None:
                    values[field_name] = ""
                elif isinstance(value, dict):
                    values[field_name] = str(value)
                else:
                    values[field_name] = str(value)
        return values

def _readOlympusHeader(tifPath):
    """Read and parse Olympus header from accompanying .txt file.

    Parses the Olympus header file that should be in the same directory as
    the TIFF file with the same base name. Extracts key acquisition parameters
    including spatial resolution (um/pixel), temporal resolution (seconds/line),
    image dimensions, and acquisition date/time.

    The function looks for specific header lines:
    - "X Dimension": Contains spatial resolution (um/pixel)
    - "T Dimension": Contains total duration (seconds)
    - "Image Size": Contains pixels per line and number of lines
    - "Date": Contains acquisition date and time
    - "Bits/Pixel": Contains bit depth

    Args:
        tifPath: Path to the TIFF file. The corresponding .txt file will be
            looked up in the same directory.

    Returns:
        Dictionary containing parsed header values:
        - dateStr: Acquisition date string
        - timeStr: Acquisition time string
        - umPerPixel: Spatial resolution in micrometers per pixel
        - secondsPerLine: Temporal resolution in seconds per line (calculated)
        - durImage_sec: Total image duration in seconds
        - pixelsPerLine: Number of pixels per line (spatial dimension)
        - numLines: Number of lines (temporal dimension)
        - bitsPerPixel: Bit depth of the image

        Returns None if the .txt file is not found.
    """

    txtPath = os.path.splitext(tifPath)[0] + ".txt"
    if not os.path.isfile(txtPath):
        # logger.warning(f"did not find Olympus header: {txtPath}")
        return

    retDict = {
        "dateStr": None,
        "timeStr": None,
        "umPerPixel": None,
        "secondsPerLine": None,  # derived from retDict['durImage_sec'] / retDict['numLines']
        "durImage_sec": None,
        "pixelsPerLine": None,
        "numLines": None,
        "bitsPerPixel": None,
    }

    pixelsPerLine = None

    with open(txtPath) as f:
        for line in f:
            line = line.strip()

            # "X Dimension"	"38, 0.0 - 10.796 [um], 0.284 [um/pixel]"
            if line.startswith('"X Dimension"'):
                oneLine = line.split()
                umPerPixel = oneLine[7]  # um/pixel
                # print('umPerPixel:', umPerPixel)
                retDict["umPerPixel"] = float(umPerPixel)

            # "T Dimension"	"1, 0.000 - 35.099 [s], Interval FreeRun"
            if line.startswith('"T Dimension"'):
                oneLine = line.split()
                durImage_sec = oneLine[5]  # imaging duration
                # print('durImage_sec:', durImage_sec)
                retDict["durImage_sec"] = float(durImage_sec)

            # "Image Size"	"38 * 30000 [pixel]"
            if line.startswith('"Image Size"'):
                if pixelsPerLine is None:
                    oneLine = line.split()
                    pixelsPerLine = oneLine[2].replace('"', "")
                    numLines = oneLine[4].replace('"', "")
                    # print('pixelsPerLine:', pixelsPerLine)
                    # print('numLines:', numLines)
                    retDict["pixelsPerLine"] = int(pixelsPerLine)
                    retDict["numLines"] = int(numLines)

            # "Date"	"11/02/2022 12:54:17.359 PM"
            if line.startswith('"Date"'):
                oneLine = line.split()
                dateStr = oneLine[1].replace('"', "")
                timeStr = oneLine[2]
                dotIndex = timeStr.find(".")
                if dotIndex != -1:
                    timeStr = timeStr[0:dotIndex]
                # print('dateStr:', dateStr)
                # print('timeStr:', timeStr)
                retDict["dateStr"] = dateStr
                retDict["timeStr"] = timeStr

            # "Bits/Pixel"	"12 [bits]"
            if line.startswith('"Bits/Pixel"'):
                oneLine = line.split()
                bitsPerPixel = oneLine[1].replace('"', "")
                # print('bitsPerPixel:', bitsPerPixel)
                retDict["bitsPerPixel"] = int(bitsPerPixel)

    # april 5, 2023
    if retDict["durImage_sec"] is None:
        logger.error("did not get durImage_sec")
    else:
        retDict["secondsPerLine"] = retDict["durImage_sec"] / retDict["numLines"]

    if retDict["umPerPixel"] is None:
        logger.error("did not get umPerPixel")

    return retDict
