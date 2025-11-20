# KymFlow

KymFlow is a NiceGUI-based application for browsing kymograph TIFF files,
editing metadata, and running Radon-based flow analysis.

The backend lives in `src/kymflow_core` and is completely GUI-agnostic, so scripts and notebooks can
reuse the same API for analysis, metadata editing, or batch processing.

---

# Requirements

- Python 3.9+
- [uv](https://github.com/astral-sh/uv) for dependency management (recommended)

---

# Getting the Source

Clone the repository (or download the ZIP) from GitHub:

```bash
git clone https://github.com/mapmanager/kymflow.git
cd kymflow
```

All commands below assume you are in the project root.

---

# Installation (uv)

KymFlow uses a **src/** layout and should be installed in editable mode. With
uv this is a single command:

```bash
uv pip install -e ".[gui,test]"
```

This creates (or updates) `.venv/`, installs the package in editable mode, and
pulls in the GUI + dev extras. If you add/remove dependencies in
`pyproject.toml`, rerun the same command. Regular source edits do **not**
require reinstalling.

> Not using uv?
> Any standard tool can install the same extras via: `pip install -e ".[gui,test]"`
> or the equivalent in your environment.

---

# Running the GUI

Launch the NiceGUI app with:

```bash
uv run python -m kymflow_gui.main
```

This automatically uses the uv-managed environment and keeps editable imports
intact. The GUI defaults to port **8080**; tweak defaults in
`src/kymflow_gui/config.py` if needed.

---

# Running Tests

```bash
uv run pytest
```

Tests that require proprietary TIFF data auto-skip when the sample data is
unavailable.


---

# Working with Jupyter Notebooks

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

# Project Layout

```
kymflow/
├─ src/
│  ├─ kymflow_core/       # backend (KymFile, metadata, analysis, repository)
│  └─ kymflow_gui/        # NiceGUI frontend (layout, components)
├─ tests/                 # unit/integration tests
├─ pyproject.toml
├─ README.md
└─ .venv/                 # uv-managed virtualenv
```

---

# Contributing

Issues and pull requests are welcome. Please include clear steps to reproduce
bugs and run `uv run pytest` before submitting changes. More detailed
guidelines will be added later.

