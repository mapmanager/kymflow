from pathlib import Path


def get_data_folder() -> Path:
    """Return the tests/data directory relative to the project root.

    Walks up from this file's location until it finds a directory that
    contains both ``tests`` and ``src`` subdirectories (or a ``pyproject.toml``),
    then returns ``tests/data`` under that root. Raises if the path cannot be
    resolved.
    """
    start = Path(__file__).resolve()

    for parent in start.parents:
        if (parent / "tests").exists() and (parent / "src").exists():
            candidate = parent / "tests" / "data"
            if candidate.exists():
                return candidate
            # Fall through to raise below if tests/data missing
            break
        if (parent / "pyproject.toml").exists():
            candidate = parent / "tests" / "data"
            if candidate.exists():
                return candidate
            break

    raise FileNotFoundError(
        f"Could not find tests/data starting from {start}. "
        "Ensure project root has tests/data."
    )

