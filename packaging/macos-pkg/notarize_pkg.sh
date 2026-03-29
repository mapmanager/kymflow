#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="${SCRIPT_DIR}"
DIST_DIR="${ROOT_DIR}/dist"
SECRETS_FILE="${ROOT_DIR}/_secrets.sh"

[ -f "${SECRETS_FILE}" ] || { echo "ERROR: missing ${SECRETS_FILE}"; exit 1; }

# shellcheck disable=SC1090
source "${SECRETS_FILE}"

[ -n "${NOTARY_PROFILE:-}" ] || { echo "ERROR: NOTARY_PROFILE is not set in ${SECRETS_FILE}"; exit 1; }

command -v xcrun >/dev/null || { echo "ERROR: xcrun not found"; exit 1; }
command -v spctl >/dev/null || { echo "ERROR: spctl not found"; exit 1; }

PKG_PATH="$(ls -t "${DIST_DIR}"/KymFlow-*.pkg 2>/dev/null | head -n 1 || true)"
[ -n "${PKG_PATH}" ] || { echo "ERROR: no pkg found in ${DIST_DIR}"; exit 1; }
[ -f "${PKG_PATH}" ] || { echo "ERROR: pkg path not found: ${PKG_PATH}"; exit 1; }

echo "=== KymFlow pkg notarization ==="
echo "PKG_PATH=${PKG_PATH}"
echo "NOTARY_PROFILE=${NOTARY_PROFILE}"

echo "=== Submitting for notarization ==="
xcrun notarytool submit "${PKG_PATH}" \
  -p "${NOTARY_PROFILE}" \
  --wait

echo "=== Stapling ==="
xcrun stapler staple "${PKG_PATH}"

echo "=== Validating stapled ticket ==="
xcrun stapler validate "${PKG_PATH}"

echo "=== Gatekeeper assessment ==="
spctl -a -vv --type install "${PKG_PATH}"

echo "=== DONE ==="