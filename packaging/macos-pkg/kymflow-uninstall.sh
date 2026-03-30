#!/bin/bash
set -euo pipefail

log() {
  echo "[kymflow-uninstall] $*"
}

fail() {
  echo "[kymflow-uninstall] ERROR: $*" >&2
  exit 1
}

usage() {
  cat <<'EOF'
Remove KymFlow files installed by the macOS .pkg or install-kymflow-curl.sh.

Removes:
  ~/Library/Application Support/kymflow-pkg  (entire tree: pkg payload KymFlowPayload/, uv, venv, payload copy, logs, uv cache, metadata)
  ~/Library/Jupyter/kernels/kymflow        (Jupyter kernelspec, if present)

Workspace (conservative):
  Deletes:  ~/Documents/KymFlow/KymFlow Jupyter.app
            ~/Documents/KymFlow/Open KymFlow.command
            ~/Documents/KymFlow/Examples/
            ~/Documents/KymFlow/Example-Data/
  Keeps:    ~/Documents/KymFlow/User/  and any other files under KymFlow/

Optional:
  Attempts:  pkgutil --forget org.cudmore.kymflow  (harmless if no receipt)

Usage:
  ./kymflow-uninstall.sh           # prompts for confirmation
  ./kymflow-uninstall.sh --yes     # non-interactive

  ./kymflow-uninstall.sh --help
EOF
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  usage
  exit 0
fi

YES=0
if [ "${1:-}" = "--yes" ]; then
  YES=1
elif [ -n "${1:-}" ]; then
  fail "Unknown argument: $1. Use --yes or --help."
fi

[ "$(uname -s)" = "Darwin" ] || fail "This script supports macOS only."

APP_ROOT="${HOME}/Library/Application Support/kymflow-pkg"
WORKSPACE_ROOT="${HOME}/Documents/KymFlow"
JUPYTER_APP_BUNDLE="${WORKSPACE_ROOT}/KymFlow Jupyter.app"
LAUNCHER_PATH="${WORKSPACE_ROOT}/Open KymFlow.command"
EXAMPLES_DIR="${WORKSPACE_ROOT}/Examples"
EXAMPLE_DATA_DIR="${WORKSPACE_ROOT}/Example-Data"
KERNEL_DIR="${HOME}/Library/Jupyter/kernels/kymflow"
PKG_ID="org.cudmore.kymflow"

echo ""
echo "Planned actions:"
echo "  rm -rf ${APP_ROOT}"
echo "  rm -rf ${KERNEL_DIR}  (if exists)"
echo "  rm -rf ${JUPYTER_APP_BUNDLE}  (if exists)"
echo "  rm -f  ${LAUNCHER_PATH}  (if exists)"
echo "  rm -rf ${EXAMPLES_DIR}  (if exists)"
echo "  rm -rf ${EXAMPLE_DATA_DIR}  (if exists)"
echo "  leave: ${WORKSPACE_ROOT}/User/ and other files under ${WORKSPACE_ROOT}/"
echo "  try:   pkgutil --forget ${PKG_ID}"
echo ""

if [ "${YES}" != "1" ]; then
  read -r -p "Type yes to proceed: " reply || true
  [ "${reply}" = "yes" ] || fail "Aborted (you did not type yes)."
fi

if [ -d "${APP_ROOT}" ]; then
  log "Removing ${APP_ROOT}"
  rm -rf "${APP_ROOT}"
else
  log "Not found (skip): ${APP_ROOT}"
fi

if [ -d "${KERNEL_DIR}" ]; then
  log "Removing Jupyter kernel ${KERNEL_DIR}"
  rm -rf "${KERNEL_DIR}"
else
  log "Not found (skip): ${KERNEL_DIR}"
fi

if [ -d "${JUPYTER_APP_BUNDLE}" ]; then
  log "Removing ${JUPYTER_APP_BUNDLE}"
  rm -rf "${JUPYTER_APP_BUNDLE}"
fi

if [ -f "${LAUNCHER_PATH}" ]; then
  log "Removing launcher ${LAUNCHER_PATH}"
  rm -f "${LAUNCHER_PATH}"
fi

if [ -d "${EXAMPLES_DIR}" ]; then
  log "Removing ${EXAMPLES_DIR}"
  rm -rf "${EXAMPLES_DIR}"
fi

if [ -d "${EXAMPLE_DATA_DIR}" ]; then
  log "Removing ${EXAMPLE_DATA_DIR}"
  rm -rf "${EXAMPLE_DATA_DIR}"
fi

if pkgutil --pkg-info-plist "${PKG_ID}" >/dev/null 2>&1; then
  log "Forgetting package receipt ${PKG_ID}"
  if pkgutil --forget "${PKG_ID}"; then
    log "pkgutil --forget succeeded"
  else
    log "pkgutil --forget failed (try: sudo pkgutil --forget ${PKG_ID})"
  fi
else
  log "No receipt for ${PKG_ID} (nothing to forget)"
fi

log "Done."
exit 0
