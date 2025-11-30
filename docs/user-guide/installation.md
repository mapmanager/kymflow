# Installation

## Quick Start

### Create Virtual Environment

```bash
python -m venv venv
```

### Activate Virtual Environment

**On macOS/Linux:**
```bash
source venv/bin/activate
```

**On Windows:**
```bash
venv\Scripts\activate
```

### Install KymFlow with GUI

```bash
pip install kymflow[gui]
```

### Run the GUI

```bash
kymflow-gui
```

The GUI will open in your default web browser at `http://localhost:8080` (or the next available port).

## Installation Options

### GUI Application Only

```bash
pip install kymflow[gui]
```

### Python API Only (No GUI)

```bash
pip install kymflow
```

### Development Installation

For development, install in editable mode with all extras:

```bash
git clone https://github.com/mapmanager/kymflow.git
cd kymflow
pip install -e ".[gui,test,notebook]"
```

## Requirements

- Python 3.11 or higher
- See `pyproject.toml` for full dependency list
