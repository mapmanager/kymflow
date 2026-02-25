from __future__ import annotations

from typing import Dict


def get_build_info() -> Dict[str, str]:
    """
    Return build metadata generated at packaging time.

    - Works in frozen PyInstaller app
    - Works in dev mode (returns empty dict if module missing)
    - Automatically returns ALL uppercase module-level variables
      from kymflow._build_info without manual mapping.
    """

    try:
        from kymflow import _build_info  # generated at build time

        # Collect all public uppercase attributes
        return {
            name: value
            for name, value in vars(_build_info).items()
            if name.isupper() and not name.startswith("_")
        }

    except Exception:
        # Dev mode or file missing
        return {}


if __name__ == "__main__":
    print("Build info dict:")
    from pprint import pprint
    pprint(get_build_info(), sort_dicts=False, indent=4)