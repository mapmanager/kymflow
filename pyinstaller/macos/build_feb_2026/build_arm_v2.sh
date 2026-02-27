#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# shellcheck source=/dev/null
source "$SCRIPT_DIR/_config.sh"

VENV_DIR="${SCRIPT_DIR}/.venv-build"

echo "[build] Script dir: $SCRIPT_DIR"
echo "[build] Repo root : $REPO_ROOT"
echo "[build] App name  : $APP_NAME"
echo "[build] Main py   : $MAIN_PY"
echo "[build] Dist dir  : $DIST_DIR"

# ---- Sanity checks ----
if [[ ! -f "$MAIN_PY" ]]; then
  echo "ERROR: MAIN_PY not found: $MAIN_PY"
  exit 2
fi
if [[ ! -d "$NICEWIDGETS_ROOT" ]]; then
  echo "ERROR: NICEWIDGETS_ROOT not found: $NICEWIDGETS_ROOT"
  echo "Expected sibling layout: $REPO_ROOT/../nicewidgets"
  exit 2
fi

# ---- Create/ensure uv-managed build env ----
if [[ ! -d "$VENV_DIR" ]]; then
  echo "[build] Creating uv venv: $VENV_DIR"
  uv venv "$VENV_DIR"
fi

echo "[build] Activating venv: $VENV_DIR"
# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"

echo "[build] Python: $(python -V)"
echo "[build] Pip: $(python -m pip -V)"

# ---- Hard guardrail: no matplotlib in build ----
echo "[build] Uninstalling matplotlib if present..."
uv pip uninstall matplotlib -y 2>/dev/null || true

echo "[build] Sanity check: matplotlib should NOT be importable (pre-install)"
python -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('matplotlib') is None else 1)" \
  || { echo "ERROR: matplotlib is still present (pre-install)." >&2; exit 1; }

# ---- Install toolchain (pin nicegui; nicegui-pack comes with nicegui) ----
echo "[build] Pinning nicegui==3.7.1..."
uv pip install 'nicegui==3.7.1'

echo "[build] Installing pyinstaller..."
uv pip install pyinstaller

echo "[build] Installing kymflow (editable) with [gui]..."
uv pip install -e "$REPO_ROOT/.[gui]"

echo "[build] Installing nicewidgets (editable) with [no_mpl]..."
uv pip install -e "$NICEWIDGETS_ROOT/.[no_mpl]"

# ---- Post-install: matplotlib must still be absent ----
echo "[build] Sanity check: matplotlib should NOT be importable (post-install)"
python -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('matplotlib') is None else 1)" \
  || { echo "ERROR: matplotlib was pulled in by a dependency (post-install)." >&2; exit 1; }

# ---- Hardened removal of dist/build ----
_remove_dir_with_retries() {
  local d="$1"
  local attempts="${2:-6}"
  local delay="${3:-0.2}"

  [[ -d "$d" ]] || return 0

  for i in $(seq 1 "$attempts"); do
    xattr -c -r "$d" 2>/dev/null || true
    chmod -N "$d" 2>/dev/null || true
    chmod -R u+rwX "$d" 2>/dev/null || true
    chflags -R nouchg,noschg "$d" 2>/dev/null || true
    rm -rf "$d"/* 2>/dev/null || true
    rm -rf "$d"/.[!.]* 2>/dev/null || true
    rm -rf "$d"/..?* 2>/dev/null || true
    rm -rf "$d" 2>/dev/null || true
    [[ -d "$d" ]] || return 0
    sleep "$delay"
  done

  echo "ERROR: failed to remove '$d' after ${attempts} attempts." >&2
  exit 1
}

echo "[build] Cleaning dist/ and build/ under: $SCRIPT_DIR"
_remove_dir_with_retries "$DIST_DIR"
_remove_dir_with_retries "$BUILD_DIR"
mkdir -p "$DIST_DIR" "$BUILD_DIR"

# Disable dev reload when packaging to avoid watchdog in the bundle
export KYMFLOW_GUI_RELOAD=0

# ---- Verify nicegui-pack (comes with nicegui, not a separate package) ----
echo "[build] Locating nicegui-pack..."
if ! command -v nicegui-pack >/dev/null 2>&1; then
  echo "ERROR: nicegui-pack not found on PATH." >&2
  echo "       nicegui-pack is provided by nicegui; ensure nicegui==3.7.1 is installed." >&2
  exit 1
fi

echo "[build] nicegui-pack: $(command -v nicegui-pack)"
# Note: nicegui-pack has no --version flag

# ---- Build stamp into package ----
# shellcheck source=/dev/null
source "$SCRIPT_DIR/build_arm_v2_timestamp.sh"

# ---- Run nicegui-pack (PyInstaller) ----
ARGS=(
  --windowed
  --clean
  --name "$APP_NAME"
  --osx-bundle-identifier "$BUNDLE_ID"
)

if [[ -n "${ICON_PATH:-}" && -f "${ICON_PATH}" ]]; then
  ARGS+=( --icon "$ICON_PATH" )
  echo "[build] Icon: $ICON_PATH"
else
  echo "[build] Icon: none (no valid ICON_PATH)"
fi

echo "[build] Running nicegui-pack..."
nicegui-pack "${ARGS[@]}" "$MAIN_PY"

echo "[build] Built: $APP_PATH"

# ---- Set bundle versions for About… dialog ----
bash "$SCRIPT_DIR/build_arm_v2_set_plist.sh"

# ---- Cleanup build info file so repo stays clean ----
if [[ -f "$BUILD_INFO_PATH" ]]; then
  rm -f "$BUILD_INFO_PATH"
  echo "[build] Cleanup: removed $BUILD_INFO_PATH"
fi

echo "[build] Done."
