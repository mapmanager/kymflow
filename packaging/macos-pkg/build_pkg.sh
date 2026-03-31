#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="${SCRIPT_DIR}"

# Release tag for GitHub archive (e.g. v0.2.1). Optional first CLI arg overrides RELEASE_TAG.
if [ "${1:-}" != "" ]; then
  RELEASE_TAG="$1"
fi
RELEASE_TAG="${RELEASE_TAG:-}"
[ -n "${RELEASE_TAG}" ] || {
  echo "ERROR: Set RELEASE_TAG (e.g. v0.2.1) or pass as the first argument"
  exit 1
}

# Upstream repo for release source tarballs (fixed; not user-configurable).
KYMFLOW_GITHUB_REPO_SLUG="mapmanager/kymflow"
TARBALL_URL="https://github.com/${KYMFLOW_GITHUB_REPO_SLUG}/archive/refs/tags/${RELEASE_TAG}.tar.gz"

# Explicit installer runtime target.
# Keep this separate from pyproject's requires-python, which is only a compatibility floor/range.
INSTALL_PYTHON_VERSION="${INSTALL_PYTHON_VERSION:-3.12}"

# User-home-relative install location (no leading slash) so the installer can use
# "Install for me only" without requiring an admin password.
PKG_INSTALL_LOCATION_REL="Library/Application Support/kymflow-pkg/KymFlowPayload"

PAYLOAD_DIR="${ROOT_DIR}/payload"
PAYLOAD_KYMFLOW_DIR="${PAYLOAD_DIR}/kymflow"

SCRIPTS_DIR="${ROOT_DIR}/scripts"
APP_LAUNCHER_DIR="${ROOT_DIR}/app_launcher"
BUILD_DIR="${ROOT_DIR}/build"
PKGBUILD_SCRIPTS_DIR="${BUILD_DIR}/pkgbuild-scripts"
DIST_DIR="${ROOT_DIR}/dist"
RESOURCES_DIR="${ROOT_DIR}/resources"
DIST_XML="${ROOT_DIR}/Distribution.xml"

SECRETS_FILE="${ROOT_DIR}/_secrets.sh"

PKG_ID="org.cudmore.kymflow"

PYPROJECT_FILE="${PAYLOAD_KYMFLOW_DIR}/pyproject.toml"
PKG_VERSION="${PKG_VERSION:-}"

COMPONENT_PKG="${BUILD_DIR}/KymFlowComponent.pkg"

echo "=== KymFlow pkg build ==="
echo "RELEASE_TAG=${RELEASE_TAG}"
echo "TARBALL_URL=${TARBALL_URL}"
echo "INSTALL_PYTHON_VERSION=${INSTALL_PYTHON_VERSION}"
echo "PKG_INSTALL_LOCATION_REL=${PKG_INSTALL_LOCATION_REL}"

[ -f "${SCRIPTS_DIR}/postinstall.sh" ] || { echo "ERROR: missing scripts/postinstall.sh"; exit 1; }
[ -f "${SCRIPTS_DIR}/make_jupyter_app.sh" ] || { echo "ERROR: missing scripts/make_jupyter_app.sh"; exit 1; }
[ -f "${APP_LAUNCHER_DIR}/launch_jupyter.swift" ] || { echo "ERROR: missing app_launcher/launch_jupyter.swift"; exit 1; }
[ -x "${APP_LAUNCHER_DIR}/build_launcher.sh" ] || { echo "ERROR: missing executable app_launcher/build_launcher.sh"; exit 1; }

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
command -v swiftc >/dev/null || { echo "ERROR: swiftc not found (required for native Jupyter launcher build)"; exit 1; }
command -v python3 >/dev/null || { echo "ERROR: python3 not found"; exit 1; }
command -v curl >/dev/null || { echo "ERROR: curl not found"; exit 1; }
command -v tar >/dev/null || { echo "ERROR: tar not found"; exit 1; }
python3 -m pip --version >/dev/null 2>&1 || {
  echo "ERROR: python3 with pip is required for wheelhouse downloads (python3 -m pip --version failed)"
  exit 1
}

mkdir -p "${BUILD_DIR}" "${DIST_DIR}"

ARCHIVE_PATH="${BUILD_DIR}/kymflow-${RELEASE_TAG}.tar.gz"

echo "=== Verifying tarball URL ==="
curl -fsSL -I -L "${TARBALL_URL}" >/dev/null

echo "=== Downloading release archive ==="
curl -fsSL -L "${TARBALL_URL}" -o "${ARCHIVE_PATH}"

echo "=== Staging payload from tarball (no local kymflow tree) ==="
rm -rf "${PAYLOAD_DIR}"
mkdir -p "${PAYLOAD_DIR}"

tar -xzf "${ARCHIVE_PATH}" -C "${PAYLOAD_DIR}"
TOP_LEVEL="$(tar -tzf "${ARCHIVE_PATH}" | head -1 | sed 's|/.*||')"
[ -n "${TOP_LEVEL}" ] || { echo "ERROR: could not determine top-level directory in archive"; exit 1; }
[ -d "${PAYLOAD_DIR}/${TOP_LEVEL}" ] || {
  echo "ERROR: expected extracted directory missing: ${PAYLOAD_DIR}/${TOP_LEVEL}"
  exit 1
}

mv "${PAYLOAD_DIR}/${TOP_LEVEL}" "${PAYLOAD_KYMFLOW_DIR}"

# Jupyter .app icon: local packaging asset (not in the GitHub release tarball). Staged into the pkg payload.
JUPYTER_APP_ICON_SRC="${ROOT_DIR}/icons/icon-green.icns"
# Installer GUI logo (welcome/conclusion HTML): local packaging asset.
INSTALLER_BRAND_PNG_SRC="${ROOT_DIR}/icons/icon-green.png"
mkdir -p "${PAYLOAD_DIR}/resources"
if [ ! -f "${JUPYTER_APP_ICON_SRC}" ]; then
  echo "ERROR: Jupyter launcher icon missing: ${JUPYTER_APP_ICON_SRC}"
  echo "Add packaging/macos-pkg/icons/icon-green.icns before building the installer (local-only; not from the release archive)."
  exit 1
fi
cp "${JUPYTER_APP_ICON_SRC}" "${PAYLOAD_DIR}/resources/AppIcon.icns"
if [ ! -f "${INSTALLER_BRAND_PNG_SRC}" ]; then
  echo "ERROR: Installer branding image missing: ${INSTALLER_BRAND_PNG_SRC}"
  echo "Add packaging/macos-pkg/icons/icon-green.png before building the installer."
  exit 1
fi
cp "${INSTALLER_BRAND_PNG_SRC}" "${RESOURCES_DIR}/icon-green.png"

[ -f "${PAYLOAD_KYMFLOW_DIR}/pyproject.toml" ] || { echo "ERROR: pyproject.toml missing in staged payload"; exit 1; }
[ -f "${PAYLOAD_KYMFLOW_DIR}/README.md" ] || { echo "ERROR: README.md missing in staged payload"; exit 1; }
[ -f "${PAYLOAD_KYMFLOW_DIR}/LICENSE" ] || { echo "ERROR: LICENSE missing in staged payload"; exit 1; }
[ -d "${PAYLOAD_KYMFLOW_DIR}/src" ] || { echo "ERROR: src/ missing in staged payload"; exit 1; }
[ -d "${PAYLOAD_KYMFLOW_DIR}/notebooks" ] || { echo "ERROR: notebooks/ missing in staged payload"; exit 1; }

if [ -z "${PKG_VERSION}" ]; then
  PKG_VERSION="$(python3 - <<'PY' "${PYPROJECT_FILE}"
import re
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text(encoding="utf-8")
match = re.search(r'(?m)^\s*version\s*=\s*"([^"]+)"\s*$', text)
if not match:
    raise SystemExit("Could not find project version in pyproject.toml")
print(match.group(1))
PY
)"
fi

FINAL_PKG="${DIST_DIR}/KymFlow-${PKG_VERSION}.pkg"

echo "PKG_VERSION=${PKG_VERSION}"
echo "FINAL_PKG=${FINAL_PKG}"

echo "Payload contents:"
find "${PAYLOAD_KYMFLOW_DIR}" -maxdepth 2

# Offline-capable install: bundle wheels for locked deps (jupyter extra) when the tag includes them.
WHEELS_DIR="${PAYLOAD_DIR}/wheels"
REQ_EXPORT="${BUILD_DIR}/kymflow-wheelhouse-requirements.txt"
rm -rf "${WHEELS_DIR}"
if [ -f "${PAYLOAD_KYMFLOW_DIR}/uv.lock" ] && grep -q '^name = "jupyterlab"' "${PAYLOAD_KYMFLOW_DIR}/uv.lock" 2>/dev/null; then
  if ! command -v uv >/dev/null 2>&1; then
    echo "ERROR: uv is required to export requirements for the wheelhouse (jupyter stack is in uv.lock)."
    echo "Install: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
  fi
  echo "=== Exporting locked requirements (jupyter extra, no dev) ==="
  (
    cd "${PAYLOAD_KYMFLOW_DIR}"
    uv export --frozen --extra jupyter --format requirements.txt \
      --no-emit-project --no-dev -o "${REQ_EXPORT}"
  )
  echo "=== Downloading wheelhouse to ${WHEELS_DIR} ==="
  mkdir -p "${WHEELS_DIR}"
  if python3 -m pip download -r "${REQ_EXPORT}" -d "${WHEELS_DIR}" \
    --only-binary :all: --python-version "${INSTALL_PYTHON_VERSION}"; then
    echo "Wheelhouse: all binary wheels (preferred)."
  else
    echo "WARNING: pip download --only-binary :all: failed; retrying allowing sdists (may need compilers on end-user machine if used)."
    python3 -m pip download -r "${REQ_EXPORT}" -d "${WHEELS_DIR}" \
      --python-version "${INSTALL_PYTHON_VERSION}" || {
      echo "ERROR: pip download failed; fix the export or network and retry."
      exit 1
    }
  fi
  echo "Wheel files:"
  find "${WHEELS_DIR}" -name '*.whl' | wc -l | awk '{print $1 " wheels"}'
else
  echo "=== Skipping wheelhouse (no uv.lock or jupyterlab not in lock; postinstall will use PyPI) ==="
fi

echo "=== Preparing pkgbuild scripts directory ==="
rm -rf "${PKGBUILD_SCRIPTS_DIR}"
mkdir -p "${PKGBUILD_SCRIPTS_DIR}"
cp "${SCRIPTS_DIR}/postinstall.sh" "${PKGBUILD_SCRIPTS_DIR}/postinstall"
chmod +x "${PKGBUILD_SCRIPTS_DIR}/postinstall"
cp "${SCRIPTS_DIR}/make_jupyter_app.sh" "${PKGBUILD_SCRIPTS_DIR}/make_jupyter_app.sh"
chmod +x "${PKGBUILD_SCRIPTS_DIR}/make_jupyter_app.sh"
"${APP_LAUNCHER_DIR}/build_launcher.sh" "${PKGBUILD_SCRIPTS_DIR}/launch_jupyter"

echo "=== Building component pkg ==="
pkgbuild \
  --root "${PAYLOAD_DIR}" \
  --scripts "${PKGBUILD_SCRIPTS_DIR}" \
  --identifier "${PKG_ID}" \
  --version "${PKG_VERSION}" \
  --install-location "${PKG_INSTALL_LOCATION_REL}" \
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
