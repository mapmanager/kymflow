#!/usr/bin/env bash
set -euo pipefail

# Always run from this script's directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "[min] CWD: $(pwd)"

# -----------------------------------------------------------------------------
# Local venv (kept inside min_example/.venv_min)
# -----------------------------------------------------------------------------
VENV_DIR=".venv_min"

# Choose python (prefers python3)
PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "[min] ERROR: '$PYTHON_BIN' not found on PATH" >&2
  exit 1
fi

echo "[min] Using python: $("$PYTHON_BIN" -c 'import sys; print(sys.executable)')"

# Create venv if missing
if [ ! -d "$VENV_DIR" ]; then
  echo "[min] Creating venv: $VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# Activate venv
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "[min] Venv python: $(python -c 'import sys; print(sys.executable)')"

# -----------------------------------------------------------------------------
# Install minimal deps (pin NiceGUI to match your main build if desired)
# -----------------------------------------------------------------------------
echo "[min] Upgrading pip..."
python -m pip install --upgrade pip

# Pin NiceGUI if you want reproducibility
NICEGUI_VER="${NICEGUI_VER:-3.7.1}"

echo "[min] Installing: nicegui==$NICEGUI_VER, pyinstaller"
python -m pip install "nicegui==${NICEGUI_VER}" pyinstaller

# Confirm nicegui-pack entry point exists
if ! command -v nicegui-pack >/dev/null 2>&1; then
  echo "[min] ERROR: nicegui-pack not found after installing nicegui. Check NiceGUI install." >&2
  python -c "import nicegui; print('nicegui', getattr(nicegui, '__version__', 'unknown'))"
  exit 1
fi

echo "[min] nicegui-pack: $(command -v nicegui-pack)"

# -----------------------------------------------------------------------------
# Clean build artifacts (only within this folder)
# -----------------------------------------------------------------------------
rm -rf dist build

# -----------------------------------------------------------------------------
# Build minimal app
# -----------------------------------------------------------------------------
nicegui-pack \
  --windowed \
  --clean \
  --name "NiceGUIMin" \
  --osx-bundle-identifier "com.robertcudmore.niceguimin" \
  ./app_min.py

echo "[min] Built: dist/NiceGUIMin.app"

# -----------------------------------------------------------------------------
# Quick size sanity check
# -----------------------------------------------------------------------------
echo "[min] Top-level Contents sizes:"
du -h -d 1 dist/NiceGUIMin.app/Contents | sort -h