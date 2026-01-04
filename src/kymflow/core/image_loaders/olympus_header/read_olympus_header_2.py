# path: olympus_header_parser.py
from __future__ import annotations

from dataclasses import dataclass
import csv
import io
import json
import re
from pathlib import Path
from typing import Any, Iterable

from kymflow.core.utils.logging import get_logger
logger = get_logger(__name__)

_SECTION_RE = re.compile(r"^\[(?P<name>.+?)\]$")  # [General], [Channel 1], ...
_VALUE_UNIT_RE = re.compile(
    r"^\s*(?P<value>[-+]?\d+(?:\.\d+)?)\s*\[(?P<unit>.+?)\]\s*$"
)


@dataclass(frozen=True)
class ParsedHeader:
    """
    sections maps:
      section_name -> { key -> value_string }

    Examples:
      sections["General"]["Name"] == "cell01.oir"
      sections["Channel 2"]["Dye Name"] == "rhod-2"
    """
    sections: dict[str, dict[str, str]]

    # ---- convenience accessors ----

    @property
    def section_names(self) -> list[str]:
        return list(self.sections.keys())

    def get_section(self, name: str) -> dict[str, str]:
        return self.sections.get(name, {})

    @property
    def general(self) -> dict[str, str]:
        return self.get_section("General")

    @property
    def dimensions(self) -> dict[str, str]:
        return self.get_section("Dimensions")

    @property
    def image(self) -> dict[str, str]:
        return self.get_section("Image")

    @property
    def reference_image(self) -> dict[str, str]:
        return self.get_section("Reference Image")

    @property
    def acquisition(self) -> dict[str, str]:
        return self.get_section("Acquisition")

    @property
    def channels(self) -> list[dict[str, str]]:
        def channel_index(name: str) -> int:
            m = re.search(r"\bChannel\s+(\d+)\b", name)
            return int(m.group(1)) if m else 10**9

        names = [n for n in self.sections.keys() if n.startswith("Channel ")]
        names.sort(key=channel_index)
        return [self.sections[n] for n in names]

    @property
    def channel_sections(self) -> list[tuple[str, dict[str, str]]]:
        """Like channels(), but includes section names: [("Channel 1", {...}), ...]."""
        def channel_index(name: str) -> int:
            m = re.search(r"\bChannel\s+(\d+)\b", name)
            return int(m.group(1)) if m else 10**9

        names = [n for n in self.sections.keys() if n.startswith("Channel ")]
        names.sort(key=channel_index)
        return [(n, self.sections[n]) for n in names]


def parse_value_with_unit(s: str) -> dict[str, Any]:
    """
    Parse values like:
      "503 [V]" -> {"raw": "503 [V]", "value": 503.0, "unit": "V"}
    If not matched, returns {"raw": s}.
    """
    m = _VALUE_UNIT_RE.match(s)
    if not m:
        return {"raw": s}
    return {"raw": s, "value": float(m.group("value")), "unit": m.group("unit")}


def parse_olympus_header_text(text: str) -> ParsedHeader:
    """
    Parse Olympus TSV-ish text where each row is tab-delimited and values are quoted.

    Section row example:
        "[General]"    ""
    KV row example:
        "Name"         "cell01.oir"
    """
    sections: dict[str, dict[str, str]] = {}
    current_section = "ROOT"
    sections[current_section] = {}

    reader = csv.reader(io.StringIO(text), delimiter="\t", quotechar='"')

    for row in reader:
        if not row:
            continue

        row = [cell.strip() for cell in row]

        # drop trailing empty columns
        while row and row[-1] == "":
            row.pop()

        if not row:
            continue

        first = row[0]
        m = _SECTION_RE.match(first)
        if m:
            current_section = m.group("name")
            sections.setdefault(current_section, {})
            continue

        if len(row) >= 2:
            key = row[0]
            value = row[1]
            if key:
                sections.setdefault(current_section, {})[key] = value
            continue

        # ignore anything else
        continue

    return ParsedHeader(sections=sections)


def parse_olympus_header_file(path: str | Path, encoding: str = "utf-8") -> ParsedHeader | None:
    """Load and parse from a .txt file on disk.
    
    Returns None if the file does not exist.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Header file not found: {p}")
        return None
    text = p.read_text(encoding=encoding)
    return parse_olympus_header_text(text)


def get_channel_info(
    parsed: ParsedHeader,
    fields: list[str],
    *,
    parse_units_for: Iterable[str] = (),
) -> list[dict[str, Any]]:
    """
    Convenience table: per-channel dict with selected fields.
      - Missing -> None
      - If field in parse_units_for -> dict from parse_value_with_unit()
    """
    parse_units_set = set(parse_units_for)

    out: list[dict[str, Any]] = []
    for idx, ch in enumerate(parsed.channels, start=1):
        row: dict[str, Any] = {"channel_index": idx}
        for f in fields:
            raw = ch.get(f)
            if raw is None:
                row[f] = None
            elif f in parse_units_set:
                row[f] = parse_value_with_unit(raw)
            else:
                row[f] = raw
        out.append(row)
    return out


# ---------------------------
# Native save/load suggestion:
# ---------------------------

@dataclass(frozen=True)
class OlympusHeaderNative:
    """
    A "native" structure that is easy to serialize.

    - vendor: helps future-proof (if you later parse other vendors)
    - version: your schema version
    - sections: raw strings exactly as seen (lossless)
    """
    vendor: str
    version: int
    sections: dict[str, dict[str, str]]

    @staticmethod
    def from_parsed(parsed: ParsedHeader, *, version: int = 1) -> "OlympusHeaderNative":
        return OlympusHeaderNative(vendor="olympus", version=version, sections=parsed.sections)

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(
            {"vendor": self.vendor, "version": self.version, "sections": self.sections},
            indent=indent,
            ensure_ascii=False,
        )

    @staticmethod
    def from_json(text: str) -> "OlympusHeaderNative":
        obj = json.loads(text)
        return OlympusHeaderNative(
            vendor=obj.get("vendor", "unknown"),
            version=int(obj.get("version", 1)),
            sections=obj["sections"],
        )

    def save_json(self, path: str | Path, *, indent: int = 2, encoding: str = "utf-8") -> None:
        logger.info(f"saving OlympusHeaderNative to {path}")
        p = Path(path)
        p.write_text(self.to_json(indent=indent), encoding=encoding)

    @staticmethod
    def load_json(path: str | Path, *, encoding: str = "utf-8") -> "OlympusHeaderNative":
        logger.info(f"loading OlympusHeaderNative from {path}")
        p = Path(path)
        return OlympusHeaderNative.from_json(p.read_text(encoding=encoding))


def pretty_print_all(parsed: ParsedHeader) -> None:
    """Print every section + all key/values, including channels."""
    for section_name in parsed.section_names:
        print(f"\n[{section_name}]")
        sec = parsed.get_section(section_name)
        for k in sorted(sec.keys()):
            print(f'  {k}: {sec[k]}')


def read_olympus_header_2(olympusTxtPath: str | Path) -> dict[str, Any]:
    """Read and parse an olympus header txtx file.
    """
    from extractors import (
        extract_int,
        extract_image_size_pixels,
        extract_um_per_pixel_from_x_dimension,
        extract_duration_sec_from_t_dimension,
    )

    parsed = parse_olympus_header_file(olympusTxtPath)
    if parsed is None:
        return None

    retDict = {
        "dateStr": None,
        "timeStr": None,
        "umPerPixel": None,
        "secondsPerLine": None,
        "durImage_sec": None,
        "pixelsPerLine": None,
        "numLines": None,
        "bitsPerPixel": None,
        "numChannels": None,
        "olympusTxtPath": str(olympusTxtPath),
    }

    # Channel Dimension: "2 [Ch]" or "1[Ch]"
    retDict["numChannels"] = extract_int(parsed.dimensions.get("Channel Dimension"))

    # X Dimension: "... 0.414 [um/pixel]"
    retDict["umPerPixel"] = extract_um_per_pixel_from_x_dimension(parsed.dimensions.get("X Dimension"))

    # T Dimension: "... 0.000 - 35.099 [s] ..."
    retDict["durImage_sec"] = extract_duration_sec_from_t_dimension(parsed.dimensions.get("T Dimension"))

    # Image Size: "38 * 30000 [pixel]"
    img_size = extract_image_size_pixels(parsed.image.get("Image Size"))
    if img_size is not None:
        retDict["pixelsPerLine"], retDict["numLines"] = img_size

    # Date: "09/08/2022 11:36:50.978 AM"
    date_raw = parsed.general.get("Date")
    if date_raw:
        # keep it simple: split on space -> date + time + AM/PM (time may include .ms)
        parts = date_raw.split()
        if len(parts) >= 2:
            retDict["dateStr"] = parts[0]
            time_part = parts[1].split(".")[0]  # drop milliseconds if present
            retDict["timeStr"] = time_part

    # Bits/Pixel: "12 [bits]"
    # (this works whether or not you used parse_units_for in a channel-summary call)
    retDict["bitsPerPixel"] = extract_int(parsed.acquisition.get("Bits/Pixel")) or extract_int(
        # some files may put Bits/Pixel in the channel section instead
        (parsed.channels[0].get("Bits/Pixel") if parsed.channels else None)
    )

    # Derived:
    if retDict["durImage_sec"] is not None and retDict["numLines"]:
        retDict["secondsPerLine"] = retDict["durImage_sec"] / retDict["numLines"]

    return retDict

if __name__ == "__main__":
    from kymflow.core.utils.logging import setup_logging
    setup_logging()
    from pprint import pprint
    import sys
    
    path = '/Users/cudmore/Sites/kymflow_outer/kymflow/data/2-channel kymographs/cell 03/cell 03.txt'
    
    retDict = read_olympus_header_2(path)
    pprint(retDict, sort_dicts=False, width=300)

    sys.exit(1)

    # Example usage (edit the path)
    header = parse_olympus_header_file(path)
    # pretty_print_all(header)

    # Example: channel summary table
    fields = ["Channel Name", "Dye Name", "Laser Wavelength", "PMT Voltage", "Detection Wavelength"]
    rows = get_channel_info(header, fields, parse_units_for=["Laser Wavelength", "PMT Voltage"])
    pprint(rows)

    # Example: save to native JSON
    native = OlympusHeaderNative.from_parsed(header, version=1)
    native.save_json("example_header.native.json")

    # Example: load it back
    native2 = OlympusHeaderNative.load_json("example_header.native.json")
    header2 = ParsedHeader(sections=native2.sections)
    pretty_print_all(header2)
    pass
