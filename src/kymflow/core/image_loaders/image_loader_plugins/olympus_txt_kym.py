"""Olympus kymograph sidecar ``.txt`` parsing (vendored; no import from ``olympus_header``).

Copied from ``kymflow.core.image_loaders.olympus_header.read_olympus_header`` logic
for use only under ``image_loader_plugins``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from kymflow.core.utils.logging import get_logger

logger = get_logger(__name__)


def _get_channel_from_tif_filename(tif_path: str | Path) -> int | None:
    tif_file_name = os.path.basename(str(tif_path))
    if "_C001T" in tif_file_name:
        return 1
    if "_C002T" in tif_file_name:
        return 2
    if "_C003T" in tif_file_name:
        return 3
    return None


def find_olympus_txt_file(tif_path: str | Path) -> str | None:
    """Return path to companion Olympus ``.txt`` if it exists, else ``None``."""
    tif_filename = os.path.basename(str(tif_path))
    channel = _get_channel_from_tif_filename(tif_path)

    if channel is None:
        olympus_txt_path = os.path.splitext(str(tif_path))[0] + ".txt"
    else:
        ch_stub = f"_C{channel:03d}"
        ch_stub_index = tif_filename.find(ch_stub)
        olympus_txt_file = tif_filename[0:ch_stub_index] + ".txt"
        olympus_txt_path = os.path.join(os.path.split(str(tif_path))[0], olympus_txt_file)

    if not os.path.isfile(olympus_txt_path):
        return None
    return olympus_txt_path


def read_olympus_txt_dict(tif_path: str | Path) -> dict[str, Any] | None:
    """Parse Olympus header text next to ``tif_path``; return dict or ``None`` if no file."""
    olympus_txt_path = find_olympus_txt_file(tif_path)
    if olympus_txt_path is None:
        return None

    ret_dict: dict[str, Any] = {
        "dateStr": None,
        "timeStr": None,
        "umPerPixel": None,
        "secondsPerLine": None,
        "durImage_sec": None,
        "pixelsPerLine": None,
        "numLines": None,
        "bitsPerPixel": None,
        "olympusTxtPath": olympus_txt_path,
    }

    pixels_per_line: int | None = None

    with open(olympus_txt_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()

            if line.startswith('"Channel Dimension"'):
                one_line = line.replace('"', "")
                parts = one_line.split()
                if len(parts) >= 3:
                    ret_dict["numChannels"] = int(parts[2])

            if line.startswith('"X Dimension"'):
                parts = line.split()
                if len(parts) > 7:
                    ret_dict["umPerPixel"] = float(parts[7])

            if line.startswith('"T Dimension"'):
                parts = line.split()
                if len(parts) > 5:
                    ret_dict["durImage_sec"] = float(parts[5])

            if line.startswith('"Image Size"'):
                if pixels_per_line is None:
                    parts = line.split()
                    if len(parts) > 4:
                        pixels_per_line = int(parts[2].replace('"', ""))
                        num_lines = int(parts[4].replace('"', ""))
                        ret_dict["pixelsPerLine"] = pixels_per_line
                        ret_dict["numLines"] = num_lines

            if line.startswith('"Date"'):
                # Prefer tab-separated quoted blob: "Date"\t"10/30/2025 02:54:36.454 PM"
                if "\t" in line:
                    after_tab = line.split("\t", 1)[1].strip()
                    if after_tab.startswith('"') and after_tab.endswith('"'):
                        combined = after_tab[1:-1]
                        ret_dict["olympusDateTimeCombined"] = combined
                parts = line.split()
                if len(parts) > 2:
                    date_str = parts[1].replace('"', "")
                    time_str = parts[2]
                    dot_index = time_str.find(".")
                    if dot_index != -1:
                        time_str = time_str[0:dot_index]
                    ret_dict["dateStr"] = date_str
                    ret_dict["timeStr"] = time_str

            if line.startswith('"Bits/Pixel"'):
                parts = line.split()
                if len(parts) > 1:
                    bits = parts[1].replace('"', "")
                    ret_dict["bitsPerPixel"] = int(bits)

    if ret_dict["durImage_sec"] is None:
        logger.error("Olympus txt: did not get durImage_sec from %s", olympus_txt_path)
    else:
        nl = ret_dict["numLines"]
        if nl is not None and nl > 0:
            ret_dict["secondsPerLine"] = ret_dict["durImage_sec"] / nl

    if ret_dict["umPerPixel"] is None:
        logger.error("Olympus txt: did not get umPerPixel from %s", olympus_txt_path)

    given_channel_number = _get_channel_from_tif_filename(tif_path)
    channel_dict: dict[int, str | Path | None] = {}
    if given_channel_number is None:
        channel_dict = {1: tif_path}
    else:
        channel_dict = {given_channel_number: tif_path}
        ch_stub = f"C{given_channel_number:03d}"
        tif_file_name = os.path.basename(str(tif_path))
        n_ch = int(ret_dict.get("numChannels", 1))
        for channel_idx in range(n_ch):
            channel_number = channel_idx + 1
            if channel_number == given_channel_number:
                continue
            other = os.path.join(
                os.path.split(str(tif_path))[0],
                tif_file_name.replace(ch_stub, f"C{channel_number:03d}"),
            )
            if not os.path.isfile(other):
                logger.warning("Olympus: missing other channel tif: %s", other)
                channel_dict[channel_number] = None
            else:
                channel_dict[channel_number] = other

    ret_dict["tifChannelPaths"] = channel_dict
    return ret_dict
