# KymFlow

[![PyPI version](https://img.shields.io/pypi/v/kymflow.svg)](https://pypi.org/project/kymflow/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/kymflow.svg)](https://pypi.org/project/kymflow/)
[![License: GPL v3+](https://img.shields.io/badge/License-GPLv3%2B-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Tests](https://github.com/mapmanager/kymflow/actions/workflows/test.yml/badge.svg)](https://github.com/mapmanager/kymflow/actions/workflows/test.yml)

| Component | Coverage |
|----------|----------|
| **core/** | [![core coverage](https://codecov.io/gh/mapmanager/kymflow/branch/main/graph/badge.svg?flag=core)](https://codecov.io/gh/mapmanager/kymflow) |
| **gui_v2/** | [![gui_v2 coverage](https://codecov.io/gh/mapmanager/kymflow/branch/main/graph/badge.svg?flag=gui_v2)](https://codecov.io/gh/mapmanager/kymflow) |

KymFlow is a NiceGUI-based application for browsing kymograph TIFF files,
editing metadata, and running Radon-based flow analysis.

The backend lives in `src/kymflow/core` and is completely GUI-agnostic, so scripts and notebooks can
reuse the same API for analysis, metadata editing, or batch processing.

---

## Requirements

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) for dependency management (recommended)

---

## Quick Start

### Install and Run GUI

1. **Create a virtual environment:**

   python -m venv kymflow-venv

2. **Activate the virtual environment:**

    ```bash
    # On macOS/Linux:
    source kymflow-venv/bin/activate

    # On Windows:
    kymflow-venv\Scripts\activate
    ```

3. **Install KymFlow with GUI dependencies:**

    ```bash
    pip install 'kymflow[gui]'
    ```

4. **Run the GUI:**

   ```bash
   python -m kymflow.gui.main
   ```
      The GUI will open in your default web browser at `http://localhost:8080` (or the next available port).


## Getting the Source

Clone the repository (or download the ZIP) from GitHub:

```bash
git clone https://github.com/mapmanager/kymflow.git
cd kymflow
```

All commands below assume you are in the project root.

---

## Installation (uv)

KymFlow uses a **src/** layout and should be installed in editable mode. With uv this is a single command:

```bash
uv pip install -e ".[gui]"
```

This creates (or updates) `.venv/`, installs the package in editable mode, and
pulls in the GUI + dev extras. If you add/remove dependencies in
`pyproject.toml`, rerun the same command. Regular source edits do **not**
require reinstalling.

> Not using uv?
> Any standard tool can install the same extras via: `pip install -e ".[gui]"`
> or the equivalent in your environment.

---

### Running the GUI

Launch the NiceGUI app with:

```bash
uv run python -m kymflow.gui.main
```

This automatically uses the uv-managed environment and keeps editable imports
intact. The GUI defaults to port **8080**; tweak defaults in
`src/kymflow/gui/config.py` if needed.

---

## Running Tests

```bash
uv pip install -e ".[test]"
```

```bash
uv run pytest tests/                    # Run all tests
uv run pytest tests/core/               # Run only core tests
uv run pytest tests/gui/                # Run only GUI tests (when you add them)
```

Run tests without data using

```bash
uv run pytest -m "not requires_data"
```

---

## Working with Jupyter Notebooks

Install the optional notebook extras (once):

```bash
uv pip install -e ".[notebook]"
```

Launch Jupyter Lab inside the repo (it will open in the `notebooks/` folder by
default):

```bash
uv run jupyter lab --notebook-dir notebooks
```

You can also use `jupyter notebook` if you prefer the classic interface. All
dependencies run inside the same uv-managed environment.

---

## Project Layout

```
kymflow/
├─ src/
│  └─ kymflow/
│     ├─ core/              # backend (KymFile, metadata, analysis, repository)
│     ├─ gui/               # NiceGUI frontend (layout, components)
│     └─ v2/                # v2 API (experimental)
├─ tests/                   # unit/integration tests
│  ├─ core/                 # core tests
│  └─ gui/                  # GUI tests
├─ pyproject.toml
├─ README.md
└─ .venv/                   # uv-managed virtualenv
```

---

## Contributing

Issues and pull requests are welcome. Please include clear steps to reproduce
bugs and run `uv run pytest` before submitting changes. More detailed
guidelines will be added later.


## Troubleshooting

To kill a stale nicegui. By default it should be running on port 8080.

```bash
sudo lsof -iTCP:8080 -sTCP:LISTEN
```

Then look for `pid` and `kill <pid>`


## Development

### To push a new version from local dev machine

edit version in pyproject.toml

```
version = "0.1.1"
```

Then

```bash
git commit -am "Bump version to 0.1.1"

git tag -a v0.1.1 -m "KymFlow 0.1.1"
git push origin main
git push origin v0.1.1
```

### To append info to macOS app

Build your macOS app bundle and go to:

 - GitHub → Releases → “Draft a new release”
 - Select tag v0.1.1
 - In the description, paste the 0.1.1 section from CHANGELOG.md.
 - Attach the macOS .dmg / .zip / .app as an asset.
 - Publish release.
