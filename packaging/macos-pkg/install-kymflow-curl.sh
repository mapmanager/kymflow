#!/bin/bash
set -euo pipefail
#
# KymFlow curl installer (macOS). Installs from:
#   https://github.com/mapmanager/kymflow/archive/refs/tags/<RELEASE_TAG>.tar.gz
#
# "Latest" (default, or --latest): tag_name from GitHub GET .../releases/latest
# (the newest published GitHub Release, not an arbitrary git tag).
#

log() {
  echo "[kymflow-install] $*"
}

fail() {
  echo "[kymflow-install] ERROR: $*" >&2
  exit 1
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

read_project_version() {
  local pyproject_file="$1"
  python3 - <<'PY' "$pyproject_file"
import re
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text(encoding="utf-8")
match = re.search(r'(?m)^\s*version\s*=\s*"([^"]+)"\s*$', text)
if not match:
    raise SystemExit("Could not find project version in pyproject.toml")
print(match.group(1))
PY
}

compare_versions() {
  local v1="$1"
  local v2="$2"

  python3 - <<'PY' "$v1" "$v2"
import sys

def parse(v: str):
    try:
        return [int(x) for x in v.strip().split(".")]
    except ValueError:
        raise SystemExit(f"Unsupported non-numeric version format: {v}")

a = parse(sys.argv[1])
b = parse(sys.argv[2])

n = max(len(a), len(b))
a += [0] * (n - len(a))
b += [0] * (n - len(b))

if a == b:
    raise SystemExit(0)
elif a > b:
    raise SystemExit(1)
else:
    raise SystemExit(2)
PY
}

usage() {
  cat <<'EOF'
Usage:
  ./install-kymflow-curl.sh [--latest | --tag vX.Y.Z]

  With no arguments and no RELEASE_TAG env: installs the tag from the latest
  published GitHub Release (GET .../releases/latest).

Options:
  --latest     Use the latest GitHub Release tag (same as default when RELEASE_TAG unset)
  --tag TAG    Install exactly this tag (e.g. v0.2.1)
  -h, --help   Show this help

Environment (optional):
  RELEASE_TAG              Tag to install (e.g. v0.2.1). Overridden by --tag or --latest.
  INSTALL_PYTHON_VERSION   Python for uv (default: 3.12)
  APP_ROOT                   Install root (default: ~/Library/Application Support/kymflow-pkg)
  WORKSPACE_ROOT             Workspace (default: ~/Documents/KymFlow)

Tarball URL pattern:
  https://github.com/mapmanager/kymflow/archive/refs/tags/<RELEASE_TAG>.tar.gz

Examples:
  ./install-kymflow-curl.sh
  ./install-kymflow-curl.sh --latest
  ./install-kymflow-curl.sh --tag v0.2.1
  RELEASE_TAG=v0.2.1 ./install-kymflow-curl.sh

Pipe one-liner (always review before running remote scripts):
  curl -fsSL https://raw.githubusercontent.com/mapmanager/kymflow/v0.2.1/packaging/macos-pkg/install-kymflow-curl.sh | bash
  curl -fsSL https://raw.githubusercontent.com/mapmanager/kymflow/v0.2.1/packaging/macos-pkg/install-kymflow-curl.sh | bash -s -- --tag v0.2.1
  curl -fsSL https://raw.githubusercontent.com/mapmanager/kymflow/v0.2.1/packaging/macos-pkg/install-kymflow-curl.sh | bash -s -- --latest

First-time installs can take several minutes (PyPI). Re-runs are faster when the
version is unchanged and the existing venv is healthy.
EOF
}

resolve_latest_release_tag() {
  local api_url="https://api.github.com/repos/${kymflow_github_repo_slug}/releases/latest"
  local json
  json="$(curl -fsSL "${api_url}")" || fail "Could not fetch ${api_url}. Set --tag vX.Y.Z or RELEASE_TAG=vX.Y.Z, or check network."
  [ -n "${json}" ] || fail "Empty response from ${api_url}."
  # stdin must be the JSON only: do not use "python3 - <<PY" here — the heredoc would replace the pipe.
  printf '%s' "${json}" | python3 -c 'import json
import sys

data = json.load(sys.stdin)
tag = data.get("tag_name")
if not tag:
    sys.stderr.write("GitHub API response missing tag_name\n")
    raise SystemExit(1)
print(tag)'
}

[ "$(uname -s)" = "Darwin" ] || fail "This installer currently supports macOS only"

need_cmd curl
need_cmd python3
need_cmd rsync
need_cmd mktemp
need_cmd find

# Upstream repo for release source tarballs (fixed; not user-configurable).
kymflow_github_repo_slug="mapmanager/kymflow"

RELEASE_TAG_FROM_ENV="${RELEASE_TAG:-}"
RELEASE_TAG_CLI=""
USE_LATEST_FLAG=0
while [ $# -gt 0 ]; do
  case "$1" in
    --tag)
      [ -n "${2:-}" ] || fail "--tag requires a value (e.g. v0.2.1)"
      RELEASE_TAG_CLI="$2"
      shift 2
      ;;
    --latest)
      USE_LATEST_FLAG=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "Unknown argument: $1 (use --help)"
      ;;
  esac
done

if [ -n "${RELEASE_TAG_CLI}" ]; then
  RELEASE_TAG="${RELEASE_TAG_CLI}"
elif [ "${USE_LATEST_FLAG}" = "1" ]; then
  log "Resolving latest GitHub Release tag for ${kymflow_github_repo_slug}..."
  RELEASE_TAG="$(resolve_latest_release_tag)"
elif [ -n "${RELEASE_TAG_FROM_ENV}" ]; then
  RELEASE_TAG="${RELEASE_TAG_FROM_ENV}"
else
  log "No tag specified; using latest GitHub Release for ${kymflow_github_repo_slug}..."
  RELEASE_TAG="$(resolve_latest_release_tag)"
fi

[ -n "${RELEASE_TAG}" ] || fail "Could not determine RELEASE_TAG"

RELEASE_URL="https://github.com/${kymflow_github_repo_slug}/archive/refs/tags/${RELEASE_TAG}.tar.gz"

INSTALL_PYTHON_VERSION="${INSTALL_PYTHON_VERSION:-3.12}"

CURRENT_USER="${SUDO_USER:-$(id -un)}"
USER_HOME="$(dscl . -read "/Users/${CURRENT_USER}" NFSHomeDirectory 2>/dev/null | awk '{print $2}')"
if [ -z "${USER_HOME}" ]; then
  USER_HOME="${HOME:-}"
fi

[ -n "${USER_HOME}" ] || fail "Could not determine user home"
[ -d "${USER_HOME}" ] || fail "Resolved user home does not exist: ${USER_HOME}"

APP_ROOT="${APP_ROOT:-${USER_HOME}/Library/Application Support/kymflow-pkg}"
LOG_DIR="${APP_ROOT}/logs"
INSTALL_VERSION_FILE="${APP_ROOT}/install_version.txt"
INSTALL_STATE_FILE="${APP_ROOT}/install_state.json"
UV_CACHE_DIR="${APP_ROOT}/.cache/uv"
export UV_CACHE_DIR

UV_ROOT="${APP_ROOT}/uv"
UV_BIN="${UV_ROOT}/uv"
VENV_DIR="${APP_ROOT}/venv"
PYTHON_BIN="${VENV_DIR}/bin/python"
JUPYTER_BIN="${VENV_DIR}/bin/jupyter"
PAYLOAD_ROOT="${APP_ROOT}/payload"

WORKSPACE_ROOT="${WORKSPACE_ROOT:-${USER_HOME}/Documents/KymFlow}"
EXAMPLES_DIR="${WORKSPACE_ROOT}/Examples"
EXAMPLE_DATA_DIR="${WORKSPACE_ROOT}/Example-Data"
USER_DIR="${WORKSPACE_ROOT}/User"
LAUNCHER_PATH="${WORKSPACE_ROOT}/Open KymFlow.command"

mkdir -p "${APP_ROOT}" "${LOG_DIR}" "${UV_CACHE_DIR}"

LOG_FILE="${LOG_DIR}/install-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee -a "${LOG_FILE}") 2>&1

log "CURRENT_USER=${CURRENT_USER}"
log "USER_HOME=${USER_HOME}"
log "APP_ROOT=${APP_ROOT}"
log "WORKSPACE_ROOT=${WORKSPACE_ROOT}"
log "RELEASE_TAG=${RELEASE_TAG}"
log "RELEASE_URL=${RELEASE_URL}"
log "INSTALL_PYTHON_VERSION=${INSTALL_PYTHON_VERSION}"
log "LOG_FILE=${LOG_FILE}"

TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/kymflow-install.XXXXXX")"
ARCHIVE_PATH="${TMP_DIR}/release-archive"
EXTRACT_DIR="${TMP_DIR}/extract"

cleanup() {
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

mkdir -p "${EXTRACT_DIR}"

log "Downloading release archive"
curl -fL "${RELEASE_URL}" -o "${ARCHIVE_PATH}"

need_cmd tar
log "Extracting tar archive"
tar -xzf "${ARCHIVE_PATH}" -C "${EXTRACT_DIR}"

SOURCE_ROOT="$(find "${EXTRACT_DIR}" -type f -name pyproject.toml -print | head -n 1 | xargs -I{} dirname "{}")"
[ -n "${SOURCE_ROOT}" ] || fail "Could not locate pyproject.toml inside extracted archive"

log "SOURCE_ROOT=${SOURCE_ROOT}"

[ -f "${SOURCE_ROOT}/pyproject.toml" ] || fail "pyproject.toml missing in source root"
[ -d "${SOURCE_ROOT}/src" ] || fail "src/ missing in source root"
[ -d "${SOURCE_ROOT}/notebooks" ] || fail "notebooks/ missing in source root"

PACKAGED_VERSION="$(read_project_version "${SOURCE_ROOT}/pyproject.toml")"
INSTALLED_VERSION=""
INSTALL_MODE="first_install"

if [ -f "${INSTALL_VERSION_FILE}" ]; then
  INSTALLED_VERSION="$(cat "${INSTALL_VERSION_FILE}")"
fi

log "PACKAGED_VERSION=${PACKAGED_VERSION}"

if [ -z "${INSTALLED_VERSION}" ]; then
  INSTALL_MODE="first_install"
  log "No installed version found; treating as first install"
else
  log "INSTALLED_VERSION=${INSTALLED_VERSION}"

  if compare_versions "${PACKAGED_VERSION}" "${INSTALLED_VERSION}"; then
    cmp_result=0
  else
    cmp_result=$?
  fi

  case "${cmp_result}" in
    0)
      INSTALL_MODE="reinstall_same"
      log "Installed version matches packaged version (${PACKAGED_VERSION}); treating as reinstall"
      ;;
    1)
      INSTALL_MODE="upgrade"
      log "Upgrading from ${INSTALLED_VERSION} to ${PACKAGED_VERSION}"
      ;;
    2)
      fail "Downgrade not allowed by script: installed version is ${INSTALLED_VERSION}, packaged version is ${PACKAGED_VERSION}"
      ;;
    *)
      fail "Unexpected version comparison result: ${cmp_result}"
      ;;
  esac
fi

mkdir -p "${WORKSPACE_ROOT}" "${USER_DIR}"

log "Refreshing payload"
rm -rf "${PAYLOAD_ROOT}"
mkdir -p "${PAYLOAD_ROOT}/kymflow"

rsync -av \
  --exclude '.DS_Store' \
  --exclude '.ipynb_checkpoints' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  "${SOURCE_ROOT}/" \
  "${PAYLOAD_ROOT}/kymflow/"

mkdir -p "${PAYLOAD_ROOT}/resources"
# App icon is not in the release tarball. Only when this script is run from a file path (not `curl | bash`).
CURL_SCRIPT_DIR=""
if [ -n "${BASH_SOURCE[0]:-}" ] && [ -f "${BASH_SOURCE[0]}" ]; then
  CURL_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi
CURL_ICON_SRC="${CURL_SCRIPT_DIR}/icons/icon-green.icns"
if [ -n "${CURL_SCRIPT_DIR}" ] && [ -f "${CURL_ICON_SRC}" ]; then
  cp "${CURL_ICON_SRC}" "${PAYLOAD_ROOT}/resources/AppIcon.icns"
  log "Staged AppIcon.icns from packaging tree (local curl run)"
fi

if [ ! -x "${UV_BIN}" ]; then
  log "Installing uv"
  curl -LsSf https://astral.sh/uv/install.sh | env UV_UNMANAGED_INSTALL="${UV_ROOT}" UV_NO_MODIFY_PATH=1 UV_CACHE_DIR="${UV_CACHE_DIR}" sh
fi

[ -x "${UV_BIN}" ] || fail "uv not found after install: ${UV_BIN}"

log "Ensuring Python ${INSTALL_PYTHON_VERSION} is installed"
"${UV_BIN}" python install "${INSTALL_PYTHON_VERSION}"

if [ ! -x "${PYTHON_BIN}" ]; then
  log "Creating virtual environment at ${VENV_DIR}"
  "${UV_BIN}" venv --python "${INSTALL_PYTHON_VERSION}" "${VENV_DIR}"
else
  log "Reusing existing virtual environment at ${VENV_DIR}"
fi

[ -x "${PYTHON_BIN}" ] || fail "python not found in venv: ${PYTHON_BIN}"

SKIP_RUNTIME_REINSTALL="0"
if [ "${INSTALL_MODE}" = "reinstall_same" ] && [ -x "${PYTHON_BIN}" ] && [ -x "${JUPYTER_BIN}" ]; then
  if "${PYTHON_BIN}" - <<'PY' "${PACKAGED_VERSION}"
import sys
from importlib.metadata import version
import kymflow  # noqa: F401

installed = version("kymflow")
expected = sys.argv[1]
raise SystemExit(0 if installed == expected else 1)
PY
  then
    SKIP_RUNTIME_REINSTALL="1"
    log "Same-version reinstall with healthy existing venv detected; skipping runtime reinstall"
  else
    log "Existing venv did not validate for packaged version; performing runtime reinstall"
  fi
fi

if [ "${SKIP_RUNTIME_REINSTALL}" != "1" ]; then
  pyproject_has_jupyter_extra() {
    [ -f "${PAYLOAD_ROOT}/kymflow/pyproject.toml" ] || return 1
    grep -qE '^jupyter[[:space:]]*=' "${PAYLOAD_ROOT}/kymflow/pyproject.toml"
  }

  if pyproject_has_jupyter_extra; then
    log "Installing kymflow[jupyter] from PyPI (matches optional-dependencies in pyproject.toml)"
    "${UV_BIN}" pip install --python "${PYTHON_BIN}" "${PAYLOAD_ROOT}/kymflow[jupyter]"
  else
    log "Installing JupyterLab and ipykernel, then kymflow (legacy tarball without jupyter extra)"
    "${UV_BIN}" pip install --python "${PYTHON_BIN}" jupyterlab ipykernel
    "${UV_BIN}" pip install --python "${PYTHON_BIN}" "${PAYLOAD_ROOT}/kymflow"
  fi

  [ -x "${JUPYTER_BIN}" ] || fail "jupyter not found in venv: ${JUPYTER_BIN}"

  log "Registering Jupyter kernel"
  "${PYTHON_BIN}" -m ipykernel install --user --name kymflow --display-name "Python (kymflow)" || true
else
  log "Skipping JupyterLab/ipykernel/kymflow reinstall for same-version reinstall"
fi

log "Refreshing installer-managed examples"
rm -rf "${EXAMPLES_DIR}"
mkdir -p "${EXAMPLES_DIR}"
rsync -av \
  --exclude '.DS_Store' \
  --exclude '.ipynb_checkpoints' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  "${PAYLOAD_ROOT}/kymflow/notebooks/" \
  "${EXAMPLES_DIR}/"

log "Refreshing installer-managed example data"
rm -rf "${EXAMPLE_DATA_DIR}"
mkdir -p "${EXAMPLE_DATA_DIR}"
if [ -d "${PAYLOAD_ROOT}/kymflow/example-data" ]; then
  rsync -av \
    --exclude '.DS_Store' \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    "${PAYLOAD_ROOT}/kymflow/example-data/" \
    "${EXAMPLE_DATA_DIR}/"
else
  log "No example-data directory present in payload; leaving Example-Data empty"
fi

mkdir -p "${USER_DIR}"

cat > "${LAUNCHER_PATH}" <<EOF
#!/bin/bash
set -euo pipefail

APP_ROOT="\$HOME/Library/Application Support/kymflow-pkg"
WORKSPACE_ROOT="\$HOME/Documents/KymFlow"
JUPYTER_BIN="\${APP_ROOT}/venv/bin/jupyter"

echo "KymFlow launcher"
echo "  App root: \${APP_ROOT}"
echo "  Workspace: \${WORKSPACE_ROOT}"

if [ ! -x "\${JUPYTER_BIN}" ]; then
  echo "ERROR: jupyter not found at \${JUPYTER_BIN}" >&2
  exit 1
fi

mkdir -p "\${WORKSPACE_ROOT}"
cd "\${WORKSPACE_ROOT}"

exec "\${JUPYTER_BIN}" lab --notebook-dir="\${WORKSPACE_ROOT}"
EOF

chmod +x "${LAUNCHER_PATH}"

MAKE_JUPYTER_APP="${SOURCE_ROOT}/packaging/macos-pkg/scripts/make_jupyter_app.sh"
if [ -x "${MAKE_JUPYTER_APP}" ]; then
  "${MAKE_JUPYTER_APP}" "${USER_HOME}" "${APP_ROOT}" "${WORKSPACE_ROOT}" "${PACKAGED_VERSION}"
else
  log "make_jupyter_app.sh not found or not executable: ${MAKE_JUPYTER_APP}"
fi

chown -R "${CURRENT_USER}":staff "${WORKSPACE_ROOT}" || true
chmod -R u+rwX "${WORKSPACE_ROOT}"

printf '%s\n' "${PACKAGED_VERSION}" > "${INSTALL_VERSION_FILE}"
chmod 644 "${INSTALL_VERSION_FILE}"

python3 - <<'PY' "${INSTALL_STATE_FILE}" "${PACKAGED_VERSION}" "${INSTALL_PYTHON_VERSION}" "${INSTALL_MODE}" "${LOG_FILE}" "${RELEASE_URL}"
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

state_file = Path(sys.argv[1])
data = {
    "version": sys.argv[2],
    "python_version": sys.argv[3],
    "install_mode": sys.argv[4],
    "log_file": sys.argv[5],
    "release_url": sys.argv[6],
    "updated_at_utc": datetime.now(timezone.utc).isoformat(),
}
state_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY

chmod 644 "${INSTALL_STATE_FILE}"

log "Created launcher: ${LAUNCHER_PATH}"
log "Recorded installed version: ${PACKAGED_VERSION}"
log "Recorded install state: ${INSTALL_STATE_FILE}"
log "Install complete"
log ""
log "Next steps:"
log "  1. Open your KymFlow folder in Finder (Documents → KymFlow), or run: open \"${WORKSPACE_ROOT}\""
log "  2. Double-click \"KymFlow Jupyter.app\" (recommended) or \"Open KymFlow.command\" to start JupyterLab in your browser."
log "  If macOS blocks the app the first time, right-click the app → Open."
log "  Notebook files and examples live under: ${WORKSPACE_ROOT}"
log "  This install was logged to: ${LOG_FILE}"