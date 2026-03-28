#!/bin/bash
set -euo pipefail

log() {
  echo "[KymFlow postinstall] $*"
}

fail() {
  echo "[KymFlow postinstall] ERROR: $*" >&2
  exit 1
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

UV_ROOT="${APP_ROOT}/uv"
UV_BIN="${UV_ROOT}/uv"
VENV_DIR="${APP_ROOT}/venv"
PAYLOAD_ROOT="${APP_ROOT}/payload"
PYTHON_BIN="${VENV_DIR}/bin/python"
JUPYTER_BIN="${VENV_DIR}/bin/jupyter"

WORKSPACE_ROOT="${USER_HOME}/Documents/KymFlow"
NOTEBOOKS_DIR="${WORKSPACE_ROOT}/Notebooks"
DATA_DIR="${WORKSPACE_ROOT}/Data"
LAUNCHER_PATH="${WORKSPACE_ROOT}/Open KymFlow.command"

PKG_PAYLOAD_ROOT="/Library/Application Support/KymFlowPayload"
PKG_KYMFLOW_SRC="${PKG_PAYLOAD_ROOT}/kymflow"
PACKAGED_PYPROJECT="${PKG_KYMFLOW_SRC}/pyproject.toml"

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
      fail "Downgrade not allowed: installed version is ${INSTALLED_VERSION}, packaged version is ${PACKAGED_VERSION}"
      ;;
    *)
      fail "Unexpected version comparison result: ${cmp_result}"
      ;;
  esac
fi

mkdir -p "${APP_ROOT}" "${WORKSPACE_ROOT}" "${NOTEBOOKS_DIR}" "${DATA_DIR}"

rm -rf "${PAYLOAD_ROOT}"
mkdir -p "${PAYLOAD_ROOT}/kymflow"

rsync -av \
  --exclude '.DS_Store' \
  --exclude '.ipynb_checkpoints' \
  "${PKG_KYMFLOW_SRC}/" \
  "${PAYLOAD_ROOT}/kymflow/"

if [ ! -x "${UV_BIN}" ]; then
  log "Installing uv"
  curl -LsSf https://astral.sh/uv/install.sh | env UV_UNMANAGED_INSTALL="${UV_ROOT}" UV_NO_MODIFY_PATH=1 sh
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
  log "Installing JupyterLab and ipykernel into venv"
  "${UV_BIN}" pip install --python "${PYTHON_BIN}" jupyterlab ipykernel

  log "Installing local kymflow project into venv"
  "${UV_BIN}" pip install --python "${PYTHON_BIN}" "${PAYLOAD_ROOT}/kymflow"

  [ -x "${JUPYTER_BIN}" ] || fail "jupyter not found in venv: ${JUPYTER_BIN}"

  log "Registering Jupyter kernel"
  "${PYTHON_BIN}" -m ipykernel install --user --name kymflow --display-name "Python (kymflow)" || true
else
  log "Skipping JupyterLab/ipykernel/kymflow reinstall for same-version reinstall"
fi

if [ -z "$(find "${NOTEBOOKS_DIR}" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]; then
  log "Copying starter notebooks into ${NOTEBOOKS_DIR}"
  rsync -av \
    --exclude '.DS_Store' \
    --exclude '.ipynb_checkpoints' \
    "${PAYLOAD_ROOT}/kymflow/notebooks/" \
    "${NOTEBOOKS_DIR}/"
else
  log "Notebook directory not empty; leaving user notebooks untouched"
fi

cat > "${LAUNCHER_PATH}" <<EOF
#!/bin/bash
set -euo pipefail

APP_ROOT="\$HOME/Library/Application Support/kymflow-pkg"
VENV_DIR="\${APP_ROOT}/venv"
NOTEBOOKS_DIR="\$HOME/Documents/KymFlow/Notebooks"
JUPYTER_BIN="\${VENV_DIR}/bin/jupyter"

echo "KymFlow launcher"
echo "  App root: \${APP_ROOT}"
echo "  Venv: \${VENV_DIR}"
echo "  Notebooks: \${NOTEBOOKS_DIR}"

if [ ! -x "\${JUPYTER_BIN}" ]; then
  echo "ERROR: jupyter not found at \${JUPYTER_BIN}" >&2
  exit 1
fi

mkdir -p "\${NOTEBOOKS_DIR}"
cd "\${NOTEBOOKS_DIR}"

exec "\${JUPYTER_BIN}" lab --notebook-dir="\${NOTEBOOKS_DIR}"
EOF

chmod +x "${LAUNCHER_PATH}"

# Ensure the user owns the editable workspace so notebooks are not read-only.
chown -R "${CURRENT_USER}":staff "${WORKSPACE_ROOT}"
chmod -R u+rwX "${WORKSPACE_ROOT}"

printf '%s\n' "${PACKAGED_VERSION}" > "${INSTALL_VERSION_FILE}"
chown "${CURRENT_USER}":staff "${INSTALL_VERSION_FILE}"
chmod 644 "${INSTALL_VERSION_FILE}"

log "Created launcher: ${LAUNCHER_PATH}"
log "Workspace ownership set to ${CURRENT_USER}:staff"
log "Recorded installed version: ${PACKAGED_VERSION}"
log "Postinstall complete"
exit 0