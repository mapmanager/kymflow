#!/usr/bin/env bash
# Shared configuration for the macOS build pipeline.
# This file is meant to be sourced by other scripts in this folder.

set -euo pipefail

# Directory of the script that sourced this file
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Repo root (kymflow/) assuming this folder lives at: kymflow/pyinstaller/macos/build_feb_2026
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# ---- Required knobs (edit if you copy this folder to another project) ----
export APP_NAME="${APP_NAME:-KymFlow}"                       # .app name and binary name inside Contents/MacOS/
export PYPI_PACKAGE="${PYPI_PACKAGE:-kymflow}"              # importlib.metadata version() name
export BUNDLE_ID="${BUNDLE_ID:-com.robertcudmore.kymflow}"   # reverse-DNS bundle identifier

# Entry-point python file for nicegui-pack (absolute)
export MAIN_PY="${MAIN_PY:-$REPO_ROOT/src/kymflow/gui_v2/app.py}"

# Optional icon (absolute). Prefer repo icon if present.
DEFAULT_ICON="$REPO_ROOT/pyinstaller/macos/kymflow.icns"
ALT_ICON="$SCRIPT_DIR/kymflow.icns"
if [[ -f "$DEFAULT_ICON" ]]; then
  export ICON_PATH="${ICON_PATH:-$DEFAULT_ICON}"
elif [[ -f "$ALT_ICON" ]]; then
  export ICON_PATH="${ICON_PATH:-$ALT_ICON}"
else
  export ICON_PATH="${ICON_PATH:-}"
fi

# Sibling repo path (nicewidgets) — assumed layout: <parent>/kymflow and <parent>/nicewidgets
export NICEWIDGETS_ROOT="${NICEWIDGETS_ROOT:-$REPO_ROOT/../nicewidgets}"

# Output locations (kept under this build folder)
export DIST_DIR="${DIST_DIR:-$SCRIPT_DIR/dist}"
export BUILD_DIR="${BUILD_DIR:-$SCRIPT_DIR/build}"

# Build-info module that gets bundled into the app by PyInstaller
export BUILD_INFO_PATH="${BUILD_INFO_PATH:-$REPO_ROOT/src/kymflow/_build_info.py}"

# Useful derived paths
export APP_PATH="${APP_PATH:-$DIST_DIR/${APP_NAME}.app}"
export APP_PLIST="${APP_PLIST:-$APP_PATH/Contents/Info.plist}"
export APP_MAIN_BIN="${APP_MAIN_BIN:-$APP_PATH/Contents/MacOS/${APP_NAME}}"
export PRE_NOTARIZE_ZIP="${PRE_NOTARIZE_ZIP:-$DIST_DIR/${APP_NAME}-pre-notarize.zip}"

# Notary submission id cache file (so poll/staple scripts can be run without copy/paste)
export NOTARY_SUBMISSION_ID_FILE="${NOTARY_SUBMISSION_ID_FILE:-$DIST_DIR/notary_submission_id.txt}"
