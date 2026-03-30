#!/bin/bash
set -euo pipefail

log() {
  echo "[KymFlow postinstall] $*"
}

fail() {
  echo "[KymFlow postinstall] ERROR: $*" >&2
  exit 1
}

# Installer.app does not show postinstall error text in its failure UI. Show a native alert
# on the console user's session (postinstall runs as root).
installer_gui_alert() {
  local title="$1"
  local body="$2"
  if [ -z "${CURRENT_USER:-}" ] || [ "${CURRENT_USER}" = "root" ]; then
    return 0
  fi
  if ! command -v sudo >/dev/null 2>&1 || ! command -v osascript >/dev/null 2>&1; then
    return 0
  fi
  # Body must not contain double quotes (semver messages are safe).
  sudo -u "${CURRENT_USER}" /usr/bin/osascript \
    -e "display alert \"${title}\" message \"${body}\" as critical buttons {\"OK\"} default button \"OK\"" \
    2>/dev/null || true
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

# Compare numeric dotted versions like 0.2.3
# Returns:
#   0 if equal
#   1 if first > second
#   2 if first < second
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

CURRENT_USER="$(stat -f%Su /dev/console)"

USER_HOME="${HOME:-}"
if [ -z "${USER_HOME}" ] || [ ! -d "${USER_HOME}" ]; then
  USER_HOME="$(dscl . -read "/Users/${CURRENT_USER}" NFSHomeDirectory | awk '{print $2}')"
fi

[ -n "${USER_HOME}" ] || fail "Could not determine user home"
[ -d "${USER_HOME}" ] || fail "Resolved user home does not exist: ${USER_HOME}"

# Explicit installer runtime target.
INSTALL_PYTHON_VERSION="${INSTALL_PYTHON_VERSION:-3.12}"

APP_ROOT="${USER_HOME}/Library/Application Support/kymflow-pkg"
INSTALL_VERSION_FILE="${APP_ROOT}/install_version.txt"
INSTALL_STATE_FILE="${APP_ROOT}/install_state.json"
LOG_DIR="${APP_ROOT}/logs"
# postinstall runs as root; uv must not use ~/.cache/uv (user-owned) or writes fail with EACCES.
UV_CACHE_DIR="${APP_ROOT}/.cache/uv"
export UV_CACHE_DIR

mkdir -p "${APP_ROOT}" "${LOG_DIR}" "${UV_CACHE_DIR}"

LOG_FILE="${LOG_DIR}/install-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee -a "${LOG_FILE}") 2>&1

UV_ROOT="${APP_ROOT}/uv"
UV_BIN="${UV_ROOT}/uv"
VENV_DIR="${APP_ROOT}/venv"
PAYLOAD_ROOT="${APP_ROOT}/payload"
PYTHON_BIN="${VENV_DIR}/bin/python"
JUPYTER_BIN="${VENV_DIR}/bin/jupyter"

WORKSPACE_ROOT="${USER_HOME}/Documents/KymFlow"
EXAMPLES_DIR="${WORKSPACE_ROOT}/Examples"
EXAMPLE_DATA_DIR="${WORKSPACE_ROOT}/Example-Data"
USER_DIR="${WORKSPACE_ROOT}/User"
LAUNCHER_PATH="${WORKSPACE_ROOT}/Open KymFlow.command"

# Matches packaging/macos-pkg/build_pkg.sh: pkg install-location is user-home-relative
# (Library/Application Support/kymflow-pkg/KymFlowPayload) so the payload lands under
# ~/Library/Application Support/... without requiring /Library or sudo for the payload.
PKG_PAYLOAD_ROOT="${USER_HOME}/Library/Application Support/kymflow-pkg/KymFlowPayload"
PKG_PAYLOAD_RESOURCES="${PKG_PAYLOAD_ROOT}/resources"
PKG_KYMFLOW_SRC="${PKG_PAYLOAD_ROOT}/kymflow"
PACKAGED_PYPROJECT="${PKG_KYMFLOW_SRC}/pyproject.toml"
WHEELS_IN_PAYLOAD="${PKG_PAYLOAD_ROOT}/wheels"

log "LOG_FILE=${LOG_FILE}"
log "CURRENT_USER=${CURRENT_USER}"
log "USER_HOME=${USER_HOME}"
log "APP_ROOT=${APP_ROOT}"
log "PKG_KYMFLOW_SRC=${PKG_KYMFLOW_SRC}"
log "INSTALL_PYTHON_VERSION=${INSTALL_PYTHON_VERSION}"

[ -d "${PKG_KYMFLOW_SRC}" ] || fail "Package payload missing at ${PKG_KYMFLOW_SRC}"
[ -f "${PKG_KYMFLOW_SRC}/pyproject.toml" ] || fail "pyproject.toml missing in payload"
[ -f "${PKG_KYMFLOW_SRC}/README.md" ] || fail "README.md missing in payload"
[ -f "${PKG_KYMFLOW_SRC}/LICENSE" ] || fail "LICENSE missing in payload"
[ -d "${PKG_KYMFLOW_SRC}/src" ] || fail "src/ missing in payload"
[ -d "${PKG_KYMFLOW_SRC}/notebooks" ] || fail "notebooks/ missing in payload"

PACKAGED_VERSION="$(read_project_version "${PACKAGED_PYPROJECT}")"
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
      installer_gui_alert "KymFlow installation stopped" "This installer is older than the version already on your Mac (installed ${INSTALLED_VERSION}, this package is ${PACKAGED_VERSION}). Downgrades are not supported. Uninstall the existing KymFlow first, or use a newer package. For details, open the log in ~/Library/Application Support/kymflow-pkg/logs/"
      fail "Downgrade not allowed by script: installed version is ${INSTALLED_VERSION}, packaged version is ${PACKAGED_VERSION}"
      ;;
    *)
      fail "Unexpected version comparison result: ${cmp_result}"
      ;;
  esac
fi

mkdir -p "${WORKSPACE_ROOT}" "${USER_DIR}"

rm -rf "${PAYLOAD_ROOT}"
mkdir -p "${PAYLOAD_ROOT}/kymflow"

rsync -av \
  --exclude '.DS_Store' \
  --exclude '.ipynb_checkpoints' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  "${PKG_KYMFLOW_SRC}/" \
  "${PAYLOAD_ROOT}/kymflow/"

mkdir -p "${PAYLOAD_ROOT}/resources"
if [ -f "${PKG_PAYLOAD_RESOURCES}/AppIcon.icns" ]; then
  cp "${PKG_PAYLOAD_RESOURCES}/AppIcon.icns" "${PAYLOAD_ROOT}/resources/AppIcon.icns"
  log "Staged AppIcon.icns into installed payload"
else
  log "No AppIcon.icns in package payload (legacy installer); Jupyter app may have no custom icon"
fi

if [ ! -x "${UV_BIN}" ]; then
  log "Installing uv"
  curl -LsSf https://astral.sh/uv/install.sh | env UV_UNMANAGED_INSTALL="${UV_ROOT}" UV_NO_MODIFY_PATH=1 UV_CACHE_DIR="${UV_CACHE_DIR}" sh
fi

[ -x "${UV_BIN}" ] || fail "uv not found after install: ${UV_BIN}"

log "Ensuring Python ${INSTALL_PYTHON_VERSION} is installed"
"${UV_BIN}" python install "${INSTALL_PYTHON_VERSION}"

# Reuse the existing venv when possible; create it only if missing or broken.
if [ ! -x "${PYTHON_BIN}" ]; then
  log "Creating virtual environment at ${VENV_DIR}"
  "${UV_BIN}" venv --python "${INSTALL_PYTHON_VERSION}" "${VENV_DIR}"
else
  log "Reusing existing virtual environment at ${VENV_DIR}"
fi

[ -x "${PYTHON_BIN}" ] || fail "python not found in venv: ${PYTHON_BIN}"

# Skip expensive reinstall work only for same-version reinstalls when the existing venv
# can actually import kymflow at the packaged version.
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
    log "Same-version reinstall with healthy existing venv detected; skipping runtime package reinstall"
  else
    log "Existing venv did not validate for packaged version; performing runtime reinstall"
  fi
fi

if [ "${SKIP_RUNTIME_REINSTALL}" != "1" ]; then
  # Prefer bundled wheelhouse (built by build_pkg.sh from uv.lock + jupyter extra) for speed and reproducibility.
  # Fallback: PyPI when no wheels, empty wheelhouse, or install failure (e.g. old tags without jupyter in lock).
  pyproject_has_jupyter_extra() {
    [ -f "${PAYLOAD_ROOT}/kymflow/pyproject.toml" ] || return 1
    grep -qE '^jupyter[[:space:]]*=' "${PAYLOAD_ROOT}/kymflow/pyproject.toml"
  }

  wheelhouse_has_wheels() {
    [ -d "${WHEELS_IN_PAYLOAD}" ] || return 1
    find "${WHEELS_IN_PAYLOAD}" -maxdepth 1 -name '*.whl' -print -quit | grep -q .
  }

  install_runtime_pypi_jupyter_then_kymflow() {
    log "Installing from PyPI (jupyterlab + ipykernel, then kymflow)"
    "${UV_BIN}" pip install --python "${PYTHON_BIN}" jupyterlab ipykernel
    "${UV_BIN}" pip install --python "${PYTHON_BIN}" "${PAYLOAD_ROOT}/kymflow"
  }

  install_runtime_pypi_kymflow_jupyter_extra() {
    log "Installing from PyPI (kymflow[jupyter])"
    "${UV_BIN}" pip install --python "${PYTHON_BIN}" "${PAYLOAD_ROOT}/kymflow[jupyter]"
  }

  if wheelhouse_has_wheels && pyproject_has_jupyter_extra; then
    log "Wheelhouse found at ${WHEELS_IN_PAYLOAD}; attempting offline-capable install"
    if "${UV_BIN}" pip install --python "${PYTHON_BIN}" \
      --no-index --find-links "${WHEELS_IN_PAYLOAD}" \
      "${PAYLOAD_ROOT}/kymflow[jupyter]"; then
      log "Installed kymflow[jupyter] from wheelhouse (no PyPI)"
    else
      log "Wheelhouse install failed; falling back to PyPI"
      install_runtime_pypi_kymflow_jupyter_extra
    fi
  else
    if wheelhouse_has_wheels && ! pyproject_has_jupyter_extra; then
      log "Wheelhouse present but pyproject has no jupyter extra (legacy tag); installing from PyPI (wheelhouse ignored)"
    elif ! wheelhouse_has_wheels; then
      log "No wheelhouse in payload; installing from PyPI"
    fi
    if pyproject_has_jupyter_extra; then
      install_runtime_pypi_kymflow_jupyter_extra
    else
      install_runtime_pypi_jupyter_then_kymflow
    fi
  fi

  [ -x "${JUPYTER_BIN}" ] || fail "jupyter not found in venv: ${JUPYTER_BIN}"

  log "Registering Jupyter kernel (as ${CURRENT_USER}, not root)"
  if command -v sudo >/dev/null 2>&1; then
    sudo -u "${CURRENT_USER}" env HOME="${USER_HOME}" "${PYTHON_BIN}" -m ipykernel install \
      --user --name kymflow --display-name "Python (kymflow)"
  else
    fail "sudo is required to register the Jupyter kernel as the console user"
  fi
else
  log "Skipping JupyterLab/ipykernel/kymflow reinstall for same-version reinstall"
fi

# Installer-managed Examples: always refresh from packaged notebooks.
rm -rf "${EXAMPLES_DIR}"
mkdir -p "${EXAMPLES_DIR}"
log "Refreshing installer-managed examples into ${EXAMPLES_DIR}"
rsync -av \
  --exclude '.DS_Store' \
  --exclude '.ipynb_checkpoints' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  "${PAYLOAD_ROOT}/kymflow/notebooks/" \
  "${EXAMPLES_DIR}/"

# Installer-managed Example-Data: always refresh to the current managed state.
# No packaged example-data source path has been defined yet, so this currently refreshes
# the managed folder to empty.
rm -rf "${EXAMPLE_DATA_DIR}"
mkdir -p "${EXAMPLE_DATA_DIR}"
log "Refreshing installer-managed example data into ${EXAMPLE_DATA_DIR}"

# User workspace is created and then left untouched by reinstall.
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

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MAKE_JUPYTER_APP="${SCRIPT_DIR}/make_jupyter_app.sh"
if [ -x "${MAKE_JUPYTER_APP}" ]; then
  "${MAKE_JUPYTER_APP}" "${USER_HOME}" "${APP_ROOT}" "${WORKSPACE_ROOT}" "${PACKAGED_VERSION}"
else
  log "make_jupyter_app.sh not found or not executable: ${MAKE_JUPYTER_APP}"
fi

# Ensure the user owns the editable workspace so notebooks are not read-only.
chown -R "${CURRENT_USER}":staff "${WORKSPACE_ROOT}"
chmod -R u+rwX "${WORKSPACE_ROOT}"

printf '%s\n' "${PACKAGED_VERSION}" > "${INSTALL_VERSION_FILE}"
chown "${CURRENT_USER}":staff "${INSTALL_VERSION_FILE}"
chmod 644 "${INSTALL_VERSION_FILE}"

python3 - <<'PY' "${INSTALL_STATE_FILE}" "${PACKAGED_VERSION}" "${INSTALL_PYTHON_VERSION}" "${INSTALL_MODE}" "${LOG_FILE}"
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
    "updated_at_utc": datetime.now(timezone.utc).isoformat(),
}
state_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY

chown "${CURRENT_USER}":staff "${INSTALL_STATE_FILE}"
chmod 644 "${INSTALL_STATE_FILE}"

# Installer runs as root; ensure the app tree under ~/Library/Application Support/kymflow-pkg
# (payload copy, uv, venv, logs, metadata) is owned by the console user for normal cleanup.
chown -R "${CURRENT_USER}":staff "${APP_ROOT}"

log "Created launcher: ${LAUNCHER_PATH}"
log "Workspace ownership set to ${CURRENT_USER}:staff"
log "Recorded installed version: ${PACKAGED_VERSION}"
log "Recorded install state: ${INSTALL_STATE_FILE}"
log "Postinstall complete"
log ""
log "Next steps:"
log "  1. Open your KymFlow folder in Finder (Documents → KymFlow), or run: open \"${WORKSPACE_ROOT}\""
log "  2. Double-click \"KymFlow Jupyter.app\" (recommended) or \"Open KymFlow.command\" to start JupyterLab in your browser."
log "  If macOS blocks the app the first time, right-click the app → Open."
log "  Notebook files and examples live under: ${WORKSPACE_ROOT}"
log "  This install was logged to: ${LOG_FILE}"
exit 0