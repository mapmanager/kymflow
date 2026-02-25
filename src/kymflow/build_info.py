from __future__ import annotations

from typing import Dict


def get_build_info() -> Dict[str, str]:
    """
    Return build metadata generated at packaging time.

    Works in:
      - frozen PyInstaller app
      - dev mode (returns fallback values if module missing)
    """

    _build_dict = {
        "build_timestamp": "dev",
        "build_git_status": "dev",
    }

    try:
        from kymflow import _build_info  # generated at build time

        _build_dict["build_timestamp"] = getattr(_build_info, "BUILD_TIMESTAMP", "unknown")
        _build_dict["build_git_status"] = getattr(_build_info, "BUILD_GIT_STATUS", "unknown")

    except Exception:
        # Dev mode or file missing
        pass
        # _build_dict = {
        #     "build_timestamp": "dev",
        #     "build_git_status": "dev",
        # }

    return _build_dict


def get_build_string() -> str:
    info = get_build_info()
    return f"{info['build_timestamp']} | {info['build_git_status']}"


if __name__ == "__main__":
    # Useful for quick CLI testing
    print("Build info dict:", get_build_info())
    print("Build info string:", get_build_string())