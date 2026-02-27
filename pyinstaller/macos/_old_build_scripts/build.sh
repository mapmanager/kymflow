# check we are run in pyinstaller/macos/build.sh
if [ "$(basename "$0")" != "build.sh" ]; then
    echo "Error: This script must be run in pyinstaller/macos/build.sh"
    exit 1
fi

#!/usr/bin/env bash
set -euo pipefail

# Build a macOS bundle using NiceGUI's PyInstaller helper.
# Requires: `python -m pip install nicegui pyinstaller` in your environment.

# /Users/cudmore/Sites/kymflow
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/../.. && pwd)"
DIST_DIR="$ROOT_DIR/pyinstaller/macos/dist"
BUILD_DIR="$ROOT_DIR/pyinstaller/macos/build"

# abb 2026
APP_ENTRY="$ROOT_DIR/src/kymflow/gui_v2/app.py"

echo "ROOT_DIR: $ROOT_DIR"
echo "DIST_DIR: $DIST_DIR"
echo "BUILD_DIR: $BUILD_DIR"
echo "APP_ENTRY: $APP_ENTRY"

# abort
# exit 1

CONDA_ENV_NAME="kymflow-pyinstaller-arm"
source /Users/cudmore/opt/miniconda3/etc/profile.d/conda.sh
conda activate "$CONDA_ENV_NAME"
conda env config vars set CONDA_SUBDIR=osx-arm64

# NEED TO REACTIVATE ENV !!!
conda deactivate
conda activate $CONDA_ENV_NAME


# pip install -e ../../.

# dry run gui
# python -m kymflow.gui.main

chmod -N "$DIST_DIR"

# delete dist and build dirs
rm -rf "$DIST_DIR" "$BUILD_DIR"
# and create them again
mkdir -p "$DIST_DIR" "$BUILD_DIR"

# Disable dev reload when packaging to avoid watchdog in the bundle
export KYMFLOW_GUI_RELOAD=0

# python -m nicegui-pack --windowed "$APP_ENTRY" \
#   --workpath "$BUILD_DIR" \
#   --distpath "$DIST_DIR"

# nicegui-pack --windowed ../../src/kymflow/gui/main.py
nicegui-pack --windowed --name "KymFlow" --icon "kymflow_transparent.icns" ../../src/kymflow/gui/main.py

# PyInstaller command:
# python -m PyInstaller --name Your App Name --windowed --add-data /Users/cudmore/opt/miniconda3/envs/kymflow-pyinstaller-arm/lib/python3.11/site-packages/nicegui:nicegui ../../src/kymflow/gui/main.py


echo "Built bundle(s) in $DIST_DIR"
