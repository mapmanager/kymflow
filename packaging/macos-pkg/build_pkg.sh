#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="${SCRIPT_DIR}"
REPO_ROOT="$(cd "${ROOT_DIR}/../.." && pwd)"

# Source of truth: the current kymflow repo root
KYMFLOW_SRC="${KYMFLOW_SRC:-${REPO_ROOT}}"

PAYLOAD_DIR="${ROOT_DIR}/payload"
PAYLOAD_KYMFLOW_DIR="${PAYLOAD_DIR}/kymflow"

SCRIPTS_DIR="${ROOT_DIR}/scripts"
BUILD_DIR="${ROOT_DIR}/build"
DIST_DIR="${ROOT_DIR}/dist"

PKG_ID="org.cudmore.kymflow"
PKG_VERSION="${PKG_VERSION:-0.1.0}"

COMPONENT_PKG="${BUILD_DIR}/KymFlowComponent.pkg"
FINAL_PKG="${DIST_DIR}/KymFlow-${PKG_VERSION}.pkg"

echo "=== KymFlow pkg build ==="
echo "KYMFLOW_SRC=${KYMFLOW_SRC}"

[ -d "${KYMFLOW_SRC}" ] || { echo "ERROR: missing kymflow repo"; exit 1; }
[ -f "${KYMFLOW_SRC}/pyproject.toml" ] || { echo "ERROR: missing pyproject.toml"; exit 1; }
[ -f "${KYMFLOW_SRC}/README.md" ] || { echo "ERROR: missing README.md"; exit 1; }
[ -f "${KYMFLOW_SRC}/LICENSE" ] || { echo "ERROR: missing LICENSE"; exit 1; }
[ -d "${KYMFLOW_SRC}/src" ] || { echo "ERROR: missing src/"; exit 1; }
[ -d "${KYMFLOW_SRC}/notebooks" ] || { echo "ERROR: missing notebooks/"; exit 1; }

command -v pkgbuild >/dev/null || { echo "ERROR: pkgbuild not found"; exit 1; }
command -v productbuild >/dev/null || { echo "ERROR: productbuild not found"; exit 1; }

echo "=== Staging payload ==="

rm -rf "${PAYLOAD_KYMFLOW_DIR}"
mkdir -p "${PAYLOAD_KYMFLOW_DIR}"
mkdir -p "${BUILD_DIR}" "${DIST_DIR}"

cp "${KYMFLOW_SRC}/pyproject.toml" "${PAYLOAD_KYMFLOW_DIR}/"
cp "${KYMFLOW_SRC}/README.md" "${PAYLOAD_KYMFLOW_DIR}/"
cp "${KYMFLOW_SRC}/LICENSE" "${PAYLOAD_KYMFLOW_DIR}/"
cp -R "${KYMFLOW_SRC}/src" "${PAYLOAD_KYMFLOW_DIR}/"
cp -R "${KYMFLOW_SRC}/notebooks" "${PAYLOAD_KYMFLOW_DIR}/"

echo "Payload contents:"
find "${PAYLOAD_KYMFLOW_DIR}" -maxdepth 2

chmod +x "${SCRIPTS_DIR}/postinstall"

echo "=== Building component pkg ==="
pkgbuild \
  --root "${PAYLOAD_DIR}" \
  --scripts "${SCRIPTS_DIR}" \
  --identifier "${PKG_ID}" \
  --version "${PKG_VERSION}" \
  --install-location "/Library/Application Support/KymFlowPayload" \
  "${COMPONENT_PKG}"

echo "=== Building final pkg ==="
productbuild \
  --package "${COMPONENT_PKG}" \
  "${FINAL_PKG}"

echo "=== DONE ==="
ls -lh "${FINAL_PKG}"