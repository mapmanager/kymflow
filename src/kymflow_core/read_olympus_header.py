import logging
import os

logger = logging.getLogger(__name__)

def _readOlympusHeader(tifPath):
    """Read the Olympus header from exported txt file.

        Return:
            dx:
            dt:

        The important Olympus txt header lines are:
            "Date"	"11/02/2022 12:54:17.359 PM"
            "File Version"	"2.1.2.3"
            "System Version"	"2.3.2.169"

            "X Dimension"	"38, 0.0 - 10.796 [um], 0.284 [um/pixel]"
            "T Dimension"	"1, 0.000 - 35.099 [s], Interval FreeRun"
            "Image Size"	"38 * 30000 [pixel]"

            "Bits/Pixel"	"12 [bits]"

        20230404

        "[General]"	""
        "Name"	"Live"
        "Scan Mode"	"XT"
        "Date"	"04/04/2023 02:01:15.183 PM"
        "System Name"	"FVMPE-RS"
        "System Version"	"2.3.2.169"
        "[Image]"	""
        "Primary Dimensions"	"X * T"
        "Image Size"	"37 * 512 [pixel]"
        "Image Size(Unit Converted)"	"8.140 [um] * 599.040 [ms]"
        "[Reference Image]"	""
        "Image Size"	"512 * 512 [pixel]"
        "Image Size(Unit Converted)"	"112.636 [um] * 112.636 [um]"
        "[Acquisition]"	""
        "Objective Lens"	"XLUMPLFLN20XW"
        "Objective Lens Mag."	"20.0X"
        "Objective Lens NA"	"1.0"
        "Scan Device"	"Galvano"
        "Scan Direction"	"Oneway"
        "Sampling Speed"	"2.0 [us/pixel]"
        "Sequential Mode"	"None"
        "Integration Type"	"None"
        "Integration Count"	"0"
        "Region Mode"	"Line"
        "Find Mode"	"x1"
        "Rotation"	"0.0 [deg]"
        "Pan X"	"0.0 [um]"
        "Pan Y"	"0.0 [um]"
        "Zoom"	"x5.65"
        "ADM"	"ADM800"
        "MirrorTurret 1"	"DMVBOIR"
        "[Channel 1]"	""
        "Channel Name"	"RNDD2"
        "Dye Name"	"Alexa Fluor 488"
        "Emission WaveLength"	"520 [nm]"
        "PMT Voltage"	"550 [V]"
        "BF Name"	"BA495-540"
        "Emission DM Name"	"SDM570"
        "Bits/Pixel"	"12 [bits]"
        "Laser Wavelength"	"920 [nm]"
        "Laser Transmissivity"	"5.0 [%]"
        "Laser ND Filter"	"None"

    """

    txtPath = os.path.splitext(tifPath)[0] + '.txt'
    if not os.path.isfile(txtPath):
        logger.error(f'error: did not find Olympus header: {txtPath}')
        return
    
    retDict = {
        'dateStr': None,
        'timeStr': None,
        'umPerPixel': None,
        'secondsPerLine': None,  # derived from retDict['durImage_sec'] / retDict['numLines']
        'durImage_sec': None,
        'pixelsPerLine': None,
        'numLines': None,
        'bitsPerPixel': None,
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
                retDict['umPerPixel'] = float(umPerPixel)

            # "T Dimension"	"1, 0.000 - 35.099 [s], Interval FreeRun"
            if line.startswith('"T Dimension"'):
                oneLine = line.split()
                durImage_sec = oneLine[5]  # imaging duration
                # print('durImage_sec:', durImage_sec)
                retDict['durImage_sec'] = float(durImage_sec)

            # "Image Size"	"38 * 30000 [pixel]"
            if line.startswith('"Image Size"'):
                if pixelsPerLine is None:
                    oneLine = line.split()
                    pixelsPerLine = oneLine[2].replace('"', '')
                    numLines = oneLine[4].replace('"', '')
                    # print('pixelsPerLine:', pixelsPerLine)
                    # print('numLines:', numLines)
                    retDict['pixelsPerLine'] = int(pixelsPerLine)
                    retDict['numLines'] = int(numLines)

            # "Date"	"11/02/2022 12:54:17.359 PM"
            if line.startswith('"Date"'):
                oneLine = line.split()
                dateStr = oneLine[1].replace('"', '')
                timeStr = oneLine[2]
                dotIndex = timeStr.find('.')
                if dotIndex != -1:
                    timeStr = timeStr[0:dotIndex]
                # print('dateStr:', dateStr)
                # print('timeStr:', timeStr)
                retDict['dateStr'] = dateStr
                retDict['timeStr'] = timeStr

            # "Bits/Pixel"	"12 [bits]"
            if line.startswith('"Bits/Pixel"'):
                oneLine = line.split()
                bitsPerPixel = oneLine[1].replace('"', '')
                # print('bitsPerPixel:', bitsPerPixel)
                retDict['bitsPerPixel'] = int(bitsPerPixel)

    # april 5, 2023
    if retDict['durImage_sec'] is None:
        logger.error(f'did not get durImage_sec')
    else:
        retDict['secondsPerLine'] = retDict['durImage_sec'] / retDict['numLines']

    if retDict['umPerPixel'] is None:
        logger.error(f'did not get umPerPixel')

    return retDict
