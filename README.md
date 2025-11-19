# KymFlow

KymFlow is a NiceGUI-based application for browsing kymograph TIFF files,
editing metadata, and running Radon-based flow analysis. The backend lives in
`src/kymflow_core` and is completely GUI-agnostic, so scripts and notebooks can
reuse the same API for analysis, metadata editing, or batch processing.

This README is also a personal cheat sheet for installing, running, and
developing the project using **uv**.

---

# Requirements

- Python 3.9+
- [uv](https://github.com/astral-sh/uv) for dependency management (recommended)

---

# Installation (uv)

KymFlow uses a **src/** layout and should be installed in **editable mode**.

### Install backend + dev tools:

```bash
uv pip install -e ".[dev]"
```

### Install GUI extras (NiceGUI + Plotly):

```bash
uv pip install -e ".[gui]"
```

These two commands:

- create or update the `.venv/` environment  
- install the project in true editable mode (PEP 660)  
- install optional extras for GUI development  

> **Tip:**  
> Re-run these commands only if you change `pyproject.toml`.  
> Source edits under `src/` do **not** require reinstalling.

---

# Running the GUI

The only reliably correct way to launch the GUI (because of NiceGUI’s
multiprocessing design) is:

```bash
uv run python -m kymflow_gui.main
```

This:

- uses uv’s environment (no manual activation)
- respects editable installs
- correctly initializes NiceGUI with `ui.run(...)`

The GUI defaults to port **8080**.  
You can adjust defaults (data folder, port, etc.) in:

```
src/kymflow_gui/config.py
```

> **Note:**  
> The console script defined in `pyproject.toml` (`kymflow-gui`) currently
> cannot be used with NiceGUI’s multiprocessing unless the module changes its
> `__main__` guard to support the `"__mp_main__"` name used by worker processes.
> For now, always run:
>
> ```bash
> uv run python -m kymflow_gui.main
> ```

---

# Running Tests

Install dev dependencies first:

```bash
uv pip install -e ".[dev]"
```

Run tests:

```bash
uv run pytest
```

Tests that require proprietary TIFF data auto-skip when the sample data is
unavailable.

---

# Development Workflow (Cheat Sheet)

**Editable install:**

```bash
uv pip install -e ".[dev]"
uv pip install -e ".[gui]"
```

**Run GUI while developing:**

```bash
uv run python -m kymflow_gui.main
```

**Run tests:**

```bash
uv run pytest
```

**When do I need to reinstall?**

- ✔ When `pyproject.toml` changes  
  (new dependencies, extras, or metadata)
- ✖ *Not needed* for normal source edits under `src/`  
  (editable mode picks them up automatically)
- ✔ If environment feels stale (rare)  
  reinstalling is safe and fast:

```bash
uv pip uninstall kymflow -y
uv pip install -e ".[dev]"
uv pip install -e ".[gui]"
```

**How to verify editable mode is active:**

```bash
uv run python - << 'EOF'
import inspect, kymflow_core
print(inspect.getfile(kymflow_core))
EOF
```

Output should show:

```
.../kymflow/src/kymflow_core/...
```

If it shows a `.venv/site-packages` path, the install is not editable.

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

1. Install dependencies:

   ```bash
   uv pip install -e ".[dev]"
   uv pip install -e ".[gui]"
   ```

2. Create a feature branch.

3. Run:

   ```bash
   uv run pytest
   ```

4. Submit a pull request with a clear description.


5. dev troubleshooting

uv sync --group dev --group gui
uv run python -m kymflow_gui.main
