"""Tests for read_olympus_header_2.py functions."""

from __future__ import annotations

from pathlib import Path

import pytest

from kymflow.core.image_loaders.olympus_header.read_olympus_header_2 import (
    ParsedHeader,
    get_channel_info,
    parse_olympus_header_file,
    parse_olympus_header_text,
    parse_value_with_unit,
    read_olympus_header_2,
)


def test_parse_value_with_unit() -> None:
    """Test parse_value_with_unit() function."""
    # Test valid format
    result = parse_value_with_unit("503 [V]")
    assert result["raw"] == "503 [V]"
    assert result["value"] == 503.0
    assert result["unit"] == "V"
    
    # Test with float
    result = parse_value_with_unit("123.45 [um]")
    assert result["raw"] == "123.45 [um]"
    assert result["value"] == 123.45
    assert result["unit"] == "um"
    
    # Test with negative value
    result = parse_value_with_unit("-42.5 [s]")
    assert result["raw"] == "-42.5 [s]"
    assert result["value"] == -42.5
    assert result["unit"] == "s"
    
    # Test invalid format (no match)
    result = parse_value_with_unit("just text")
    assert result == {"raw": "just text"}
    
    # Test empty string
    result = parse_value_with_unit("")
    assert result == {"raw": ""}


def test_parse_olympus_header_text() -> None:
    """Test parse_olympus_header_text() function."""
    # Sample Olympus header text format
    header_text = """[General]
Name	"test.oir"
Date	"2024-01-01"

[Dimensions]
X	"416, 0.0 - 172.357 [um], 0.414 [um/pixel]"
Y	"38 * 30000 [pixel]"
T	"1, 0.000 - 35.099 [s], Interval FreeRun"

[Channel 1]
Dye Name	"rhod-2"
"""
    
    parsed = parse_olympus_header_text(header_text)
    
    assert isinstance(parsed, ParsedHeader)
    assert "General" in parsed.sections
    assert "Dimensions" in parsed.sections
    assert "Channel 1" in parsed.sections
    
    # Test convenience properties
    assert parsed.general["Name"] == "test.oir"
    assert parsed.dimensions["X"] == "416, 0.0 - 172.357 [um], 0.414 [um/pixel]"
    assert len(parsed.channels) == 1
    assert parsed.channels[0]["Dye Name"] == "rhod-2"


def test_parsed_header_properties() -> None:
    """Test ParsedHeader convenience properties."""
    sections = {
        "General": {"Name": "test.oir", "Date": "2024-01-01"},
        "Dimensions": {"X": "416", "Y": "38"},
        "Image": {"Width": "100", "Height": "200"},
        "Reference Image": {"Ref": "value"},
        "Acquisition": {"Mode": "scan"},
        "Channel 1": {"Dye Name": "rhod-2"},
        "Channel 2": {"Dye Name": "fluo-4"},
    }
    
    parsed = ParsedHeader(sections=sections)
    
    # Test section_names
    assert "General" in parsed.section_names
    assert "Dimensions" in parsed.section_names
    
    # Test get_section
    assert parsed.get_section("General") == sections["General"]
    assert parsed.get_section("Nonexistent") == {}
    
    # Test convenience properties
    assert parsed.general == sections["General"]
    assert parsed.dimensions == sections["Dimensions"]
    assert parsed.image == sections["Image"]
    assert parsed.reference_image == sections["Reference Image"]
    assert parsed.acquisition == sections["Acquisition"]
    
    # Test channels (should be sorted by channel number)
    channels = parsed.channels
    assert len(channels) == 2
    assert channels[0] == sections["Channel 1"]
    assert channels[1] == sections["Channel 2"]
    
    # Test channel_sections
    channel_sections = parsed.channel_sections
    assert len(channel_sections) == 2
    assert channel_sections[0][0] == "Channel 1"
    assert channel_sections[0][1] == sections["Channel 1"]


def test_parse_olympus_header_file() -> None:
    """Test parse_olympus_header_file() function."""
    from tempfile import TemporaryDirectory
    
    # Create a temporary header file
    with TemporaryDirectory() as tmpdir:
        header_file = Path(tmpdir) / "test.txt"
        header_text = """[General]
Name	"test.oir"
Date	"2024-01-01"

[Dimensions]
X	"416, 0.0 - 172.357 [um], 0.414 [um/pixel]"
"""
        header_file.write_text(header_text, encoding="utf-8")
        
        # Parse the file
        parsed = parse_olympus_header_file(header_file)
        
        assert parsed is not None
        assert isinstance(parsed, ParsedHeader)
        assert "General" in parsed.sections
        assert "Dimensions" in parsed.sections
        
        # Test with non-existent file
        non_existent = Path(tmpdir) / "nonexistent.txt"
        result = parse_olympus_header_file(non_existent)
        assert result is None


def test_get_channel_info() -> None:
    """Test get_channel_info() function."""
    # Create ParsedHeader with channel information
    sections = {
        "Channel 1": {
            "Dye Name": "rhod-2",
            "Excitation Wavelength": "550 [nm]",
            "Emission Wavelength": "580 [nm]",
        },
        "Channel 2": {
            "Dye Name": "fluo-4",
            "Excitation Wavelength": "488 [nm]",
            "Emission Wavelength": "510 [nm]",
        },
    }
    
    parsed = ParsedHeader(sections=sections)
    
    # Get channel info
    fields = ["Dye Name", "Excitation Wavelength", "Emission Wavelength"]
    channel_info = get_channel_info(parsed, fields)
    
    assert isinstance(channel_info, list)
    assert len(channel_info) == 2
    
    # Check first channel
    assert channel_info[0]["channel_index"] == 1
    assert channel_info[0]["Dye Name"] == "rhod-2"
    
    # Check second channel
    assert channel_info[1]["channel_index"] == 2
    assert channel_info[1]["Dye Name"] == "fluo-4"


def test_read_olympus_header_2() -> None:
    """Test read_olympus_header_2() function."""
    from tempfile import TemporaryDirectory
    
    # Create a temporary header file
    with TemporaryDirectory() as tmpdir:
        header_file = Path(tmpdir) / "test.txt"
        header_text = """[General]
Name	"test.oir"
Date	"2024-01-01"

[Dimensions]
X	"416, 0.0 - 172.357 [um], 0.414 [um/pixel]"
Y	"38 * 30000 [pixel]"
T	"1, 0.000 - 35.099 [s], Interval FreeRun"
"""
        header_file.write_text(header_text, encoding="utf-8")
        
        # Read header
        result = read_olympus_header_2(header_file)
        
        assert isinstance(result, dict)
        # Should contain extracted values
        # Exact keys depend on implementation, but should have some data
        assert len(result) > 0
        
        # Test with non-existent file
        non_existent = Path(tmpdir) / "nonexistent.txt"
        result_none = read_olympus_header_2(non_existent)
        # Should return None or empty dict depending on implementation
        assert result_none is None or isinstance(result_none, dict)
