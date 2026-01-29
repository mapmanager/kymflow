#!/usr/bin/env bash
set -euo pipefail

# ---- make conda shell functions available ----
CONDA_BASE="${HOME}/opt/miniconda3"

if [ -f "${CONDA_BASE}/etc/profile.d/conda.sh" ]; then
    # shellcheck disable=SC1090
    . "${CONDA_BASE}/etc/profile.d/conda.sh"
else
    echo "ERROR: conda.sh not found at ${CONDA_BASE}/etc/profile.d/conda.sh" >&2
    exit 1
fi
# ---------------------------------------------

# deactivate any existing conda environment in THIS shell (if any)
conda deactivate || true

CONDA_ENV_NAME="kymflow-pyinstaller-arm"

# create env if it doesn't already exist
if ! conda env list | awk '{print $1}' | grep -qx "${CONDA_ENV_NAME}"; then
    CONDA_SUBDIR=osx-arm64 conda create -y -n "${CONDA_ENV_NAME}" python=3.11
fi

# activate env
conda activate "${CONDA_ENV_NAME}"

pip install --upgrade pip
pip install -e '../../.[gui]'
pip install -e '../../../nicewidgets/.'  # abb 2026

pip install nicegui==3.6.0

pip install pyinstaller

# dry run gui
# python -m kymflow.gui.main

# remove build and dist folders
if [ -d "dist" ]; then
    # Remove extended attributes (the @ symbol) recursively
    xattr -c -r dist 2>/dev/null || true
    # Remove ACLs
    chmod -N dist 2>/dev/null || true
    rm -rf dist
fi
if [ -d "build" ]; then
    # Remove extended attributes recursively
    xattr -c -r build 2>/dev/null || true
    # Remove ACLs
    chmod -N build 2>/dev/null || true
    rm -rf build
fi

# Disable dev reload when packaging to avoid watchdog in the bundle
export KYMFLOW_GUI_RELOAD=0

# python -m nicegui-pack --windowed "$APP_ENTRY" \
#   --workpath "$BUILD_DIR" \
#   --distpath "$DIST_DIR"

# nicegui-pack --windowed --name "KymFlow" --icon "kymflow_transparent.icns" ../../src/kymflow/gui/main.py
# nicegui-pack --windowed --name "KymFlow" --icon "kymflow.icns" ../../src/kymflow/gui/main.py

ls -l "$(which nicegui-pack)"

nicegui-pack --windowed --clean --name "KymFlow" --icon "kymflow.icns" ../../src/kymflow/gui_v2/app.py
