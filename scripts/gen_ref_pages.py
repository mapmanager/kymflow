#!/usr/bin/env python3
"""Generate documentation tables for dataclasses.

This script generates markdown tables from dataclass field definitions
for use in documentation. Run with --class to generate docs for a specific
dataclass, or without arguments to generate all.
"""

from __future__ import annotations

import argparse

from kymflow.core.image_loaders.metadata import (
    _generateDocs,
    AcqImgHeader,
    ExperimentMetadata,
)


def main() -> None:
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Generate documentation tables for dataclasses"
    )
    parser.add_argument(
        "--class",
        dest="class_name",
        choices=["OlympusHeader", "ExperimentMetadata", "AcqImgHeader", "all"],
        default="all",
        help="Dataclass to generate docs for (default: all)",
    )
    
    args = parser.parse_args()
    
    classes_to_generate = []
    if args.class_name == "all":
        classes_to_generate = [
            ("ExperimentMetadata", ExperimentMetadata),
            ("AcqImgHeader", AcqImgHeader),
            # ("AnalysisParameters", AnalysisParameters),
            # ("OlympusHeader", OlympusHeader),
        ]
    else:
        class_map = {
            "ExperimentMetadata": ExperimentMetadata,
            "AcqImgHeader": AcqImgHeader,
            # "AnalysisParameters": AnalysisParameters,
            # "OlympusHeader": OlympusHeader,
        }
        classes_to_generate = [(args.class_name, class_map[args.class_name])]
    
    for name, dc_class in classes_to_generate:
        _generateDocs(dc_class, print_markdown=True)


if __name__ == "__main__":
    main()

