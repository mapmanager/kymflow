#!/usr/bin/env bash
set -euo pipefail

# -----------------------------------------------------------------------------
# Always run from this script's directory so relative paths are stable.
# This prevents "dist not empty" weirdness when you accidentally run from elsewhere.
# -----------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "[build_arm] CWD: $(pwd)"

# ---- abb 20260225 - include nicegui-pack build time ----
source ./build_arm_v2_timestamp.sh

# Cleanup on exit (success or failure)
cleanup_build_info() {
    if [ -n "${BUILD_INFO_PATH:-}" ] && [ -f "$BUILD_INFO_PATH" ]; then
        rm -f "$BUILD_INFO_PATH"
        echo "[build_arm] Cleanup: removed $BUILD_INFO_PATH"
    fi
}
trap cleanup_build_info EXIT
# ---- END abb 20260225 - include nicegui-pack build time ----


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
    echo "[build_arm] Creating conda env: ${CONDA_ENV_NAME} (python=3.11, osx-arm64)"
    CONDA_SUBDIR=osx-arm64 conda create -y -n "${CONDA_ENV_NAME}" python=3.11
else
    echo "[build_arm] Using existing conda env: ${CONDA_ENV_NAME}"
fi

# activate env
conda activate "${CONDA_ENV_NAME}"

echo "[build_arm] Python: $(python -V)"
echo "[build_arm] Pip: $(python -m pip -V)"

# -----------------------------------------------------------------------------
# Hard guardrail: ensure matplotlib is not present (persistent env can keep it).
# Option 1: explicitly uninstall matplotlib before installing anything.
# -----------------------------------------------------------------------------
echo "[build_arm] Uninstalling matplotlib if present (sanity for persistent env)..."
python -m pip uninstall -y matplotlib 2>/dev/null || true

echo "[build_arm] Sanity check: matplotlib should NOT be importable (pre-install)"
python -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('matplotlib') is None else 1)" \
  || { echo "ERROR: matplotlib is still present in the environment (pre-install)." >&2; exit 1; }

# -----------------------------------------------------------------------------
# Installs
# -----------------------------------------------------------------------------
echo "[build_arm] Upgrading pip..."
python -m pip install --upgrade pip

echo "[build_arm] Installing kymflow (editable) with [gui]..."
python -m pip install -e '../../.[gui]'

echo "[build_arm] Installing nicewidgets (editable) with [no_mpl]..."
python -m pip install -e '../../../nicewidgets/.[no_mpl]'  # abb 2026

echo "[build_arm] Pinning nicegui==3.7.1 for clarity..."
python -m pip install 'nicegui==3.7.1'

echo "[build_arm] Installing pyinstaller..."
python -m pip install pyinstaller

# -----------------------------------------------------------------------------
# Post-install sanity: prove matplotlib didn’t get pulled in by any dependency.
# -----------------------------------------------------------------------------
echo "[build_arm] Sanity check: matplotlib should NOT be importable (post-install)"
python -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('matplotlib') is None else 1)" \
  || { echo "ERROR: matplotlib was pulled into the environment (post-install)." >&2; exit 1; }

# -----------------------------------------------------------------------------
# Clean build artifacts (in this script dir)
# -----------------------------------------------------------------------------
echo "[build_arm] Cleaning dist/ and build/ (if present) under: $(pwd)"

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

# -----------------------------------------------------------------------------
# Verify nicegui-pack is available (it is not on PyPI; must come from your env/path)
# -----------------------------------------------------------------------------
echo "[build_arm] Locating nicegui-pack..."
if ! command -v nicegui-pack >/dev/null 2>&1; then
    echo "ERROR: nicegui-pack not found on PATH in env '${CONDA_ENV_NAME}'." >&2
    echo "       Since nicegui-pack is not on PyPI, ensure it is installed/available in this environment." >&2
    exit 1
fi

echo "[build_arm] nicegui-pack: $(command -v nicegui-pack)"
# If --version isn't supported, don't fail the build; just print what we can.
nicegui-pack --version 2>/dev/null || true

# -----------------------------------------------------------------------------
# Build
# -----------------------------------------------------------------------------
echo "[build_arm] Running nicegui-pack..."
nicegui-pack --windowed --clean --name "KymFlow" --icon "kymflow.icns" ../../src/kymflow/gui_v2/app.py

echo "[build_arm] Done."