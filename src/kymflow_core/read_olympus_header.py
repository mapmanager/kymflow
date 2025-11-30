"""Parser for Olympus microscope header files.

This module provides functionality to parse Olympus .txt header files that
accompany kymograph TIFF files. The header files contain acquisition parameters
such as spatial and temporal resolution, image dimensions, and acquisition
date/time.
"""

import logging
import os

logger = logging.getLogger(__name__)


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
        logger.warning(f"did not find Olympus header: {txtPath}")
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
