# src/kymflow/gui_v2/__init__.py
"""NiceGUI v2 package for KymFlow.

This package provides a thin NiceGUI UI layer that:
- relies on the existing kymflow.core backend
- uses an explicit EventBus for clean signal flow logging
- keeps views dumb and controllers responsible for coordination
"""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("kymflow")
except PackageNotFoundError:  # running from source without install
    __version__ = "0.0.0+local"
