#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="${SCRIPT_DIR}"
REPO_ROOT="$(cd "${ROOT_DIR}/../.." && pwd)"

# Source of truth: the current kymflow repo root
KYMFLOW_SRC="${KYMFLOW_SRC:-${REPO_ROOT}}"

# Explicit installer runtime target.
# Keep this separate from pyproject's requires-python, which is only a compatibility floor/range.
INSTALL_PYTHON_VERSION="${INSTALL_PYTHON_VERSION:-3.12}"

PAYLOAD_DIR="${ROOT_DIR}/payload"
PAYLOAD_KYMFLOW_DIR="${PAYLOAD_DIR}/kymflow"

SCRIPTS_DIR="${ROOT_DIR}/scripts"
BUILD_DIR="${ROOT_DIR}/build"
PKGBUILD_SCRIPTS_DIR="${BUILD_DIR}/pkgbuild-scripts"
DIST_DIR="${ROOT_DIR}/dist"
RESOURCES_DIR="${ROOT_DIR}/resources"
DIST_XML="${ROOT_DIR}/Distribution.xml"

SECRETS_FILE="${ROOT_DIR}/_secrets.sh"

PKG_ID="org.cudmore.kymflow"

PYPROJECT_FILE="${KYMFLOW_SRC}/pyproject.toml"
PKG_VERSION="${PKG_VERSION:-$(python3 - <<'PY' "${PYPROJECT_FILE}"
import re
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text(encoding="utf-8")
match = re.search(r'(?m)^\s*version\s*=\s*"([^"]+)"\s*$', text)
if not match:
    raise SystemExit("Could not find project version in pyproject.toml")
print(match.group(1))
PY
)}"

COMPONENT_PKG="${BUILD_DIR}/KymFlowComponent.pkg"
FINAL_PKG="${DIST_DIR}/KymFlow-${PKG_VERSION}.pkg"

echo "=== KymFlow pkg build ==="
echo "KYMFLOW_SRC=${KYMFLOW_SRC}"
echo "INSTALL_PYTHON_VERSION=${INSTALL_PYTHON_VERSION}"
echo "PKG_VERSION=${PKG_VERSION}"

[ -d "${KYMFLOW_SRC}" ] || { echo "ERROR: missing kymflow repo"; exit 1; }
[ -f "${KYMFLOW_SRC}/pyproject.toml" ] || { echo "ERROR: missing pyproject.toml"; exit 1; }
[ -f "${KYMFLOW_SRC}/README.md" ] || { echo "ERROR: missing README.md"; exit 1; }
[ -f "${KYMFLOW_SRC}/LICENSE" ] || { echo "ERROR: missing LICENSE"; exit 1; }
[ -d "${KYMFLOW_SRC}/src" ] || { echo "ERROR: missing src/"; exit 1; }
[ -d "${KYMFLOW_SRC}/notebooks" ] || { echo "ERROR: missing notebooks/"; exit 1; }
[ -f "${SCRIPTS_DIR}/postinstall.sh" ] || { echo "ERROR: missing scripts/postinstall.sh"; exit 1; }

[ -f "${DIST_XML}" ] || { echo "ERROR: missing Distribution.xml"; exit 1; }
[ -d "${RESOURCES_DIR}" ] || { echo "ERROR: missing resources/"; exit 1; }
[ -f "${RESOURCES_DIR}/welcome.html" ] || { echo "ERROR: missing resources/welcome.html"; exit 1; }
[ -f "${RESOURCES_DIR}/conclusion.html" ] || { echo "ERROR: missing resources/conclusion.html"; exit 1; }
[ -f "${RESOURCES_DIR}/license.txt" ] || { echo "ERROR: missing resources/license.txt"; exit 1; }

[ -f "${SECRETS_FILE}" ] || { echo "ERROR: missing ${SECRETS_FILE}"; exit 1; }

# shellcheck disable=SC1090
source "${SECRETS_FILE}"

[ -n "${SIGN_INSTALLER_ID:-}" ] || { echo "ERROR: SIGN_INSTALLER_ID is not set in ${SECRETS_FILE}"; exit 1; }

command -v pkgbuild >/dev/null || { echo "ERROR: pkgbuild not found"; exit 1; }
command -v productbuild >/dev/null || { echo "ERROR: productbuild not found"; exit 1; }
command -v pkgutil >/dev/null || { echo "ERROR: pkgutil not found"; exit 1; }
command -v python3 >/dev/null || { echo "ERROR: python3 not found"; exit 1; }
command -v rsync >/dev/null || { echo "ERROR: rsync not found"; exit 1; }

echo "=== Staging payload ==="

rm -rf "${PAYLOAD_KYMFLOW_DIR}"
mkdir -p "${PAYLOAD_KYMFLOW_DIR}"
mkdir -p "${BUILD_DIR}" "${DIST_DIR}"

cp "${KYMFLOW_SRC}/pyproject.toml" "${PAYLOAD_KYMFLOW_DIR}/"
cp "${KYMFLOW_SRC}/README.md" "${PAYLOAD_KYMFLOW_DIR}/"
cp "${KYMFLOW_SRC}/LICENSE" "${PAYLOAD_KYMFLOW_DIR}/"

mkdir -p "${PAYLOAD_KYMFLOW_DIR}/src"
rsync -av \
  --exclude '.DS_Store' \
  --exclude '.ipynb_checkpoints' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  "${KYMFLOW_SRC}/src/" \
  "${PAYLOAD_KYMFLOW_DIR}/src/"

mkdir -p "${PAYLOAD_KYMFLOW_DIR}/notebooks"
rsync -av \
  --exclude '.DS_Store' \
  --exclude '.ipynb_checkpoints' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  "${KYMFLOW_SRC}/notebooks/" \
  "${PAYLOAD_KYMFLOW_DIR}/notebooks/"

echo "Payload contents:"
find "${PAYLOAD_KYMFLOW_DIR}" -maxdepth 2

echo "=== Preparing pkgbuild scripts directory ==="
rm -rf "${PKGBUILD_SCRIPTS_DIR}"
mkdir -p "${PKGBUILD_SCRIPTS_DIR}"
cp "${SCRIPTS_DIR}/postinstall.sh" "${PKGBUILD_SCRIPTS_DIR}/postinstall"
chmod +x "${PKGBUILD_SCRIPTS_DIR}/postinstall"

echo "=== Building component pkg ==="
pkgbuild \
  --root "${PAYLOAD_DIR}" \
  --scripts "${PKGBUILD_SCRIPTS_DIR}" \
  --identifier "${PKG_ID}" \
  --version "${PKG_VERSION}" \
  --install-location "/Library/Application Support/KymFlowPayload" \
  "${COMPONENT_PKG}"

echo "=== Building signed final pkg with Distribution.xml and resources ==="
productbuild \
  --distribution "${DIST_XML}" \
  --resources "${RESOURCES_DIR}" \
  --package-path "${BUILD_DIR}" \
  --sign "${SIGN_INSTALLER_ID}" \
  "${FINAL_PKG}"

echo "=== Verifying signature ==="
pkgutil --check-signature "${FINAL_PKG}"

echo "=== DONE ==="
ls -lh "${FINAL_PKG}"