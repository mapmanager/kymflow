#!/bin/bash
set -euo pipefail

APP_ROOT="$HOME/Library/Application Support/kymflow-pkg"
VENV_DIR="$APP_ROOT/venv"
INSTALL_STATE_FILE="$APP_ROOT/install_state.json"
LOG_DIR="$APP_ROOT/logs"

WORKSPACE_ROOT="$HOME/Documents/KymFlow"
EXAMPLES_DIR="$WORKSPACE_ROOT/Examples"
EXAMPLE_DATA_DIR="$WORKSPACE_ROOT/Example-Data"
USER_DIR="$WORKSPACE_ROOT/User"
LAUNCHER="$WORKSPACE_ROOT/Open KymFlow.command"

echo "=== KymFlow smoke test ==="

[ -x "$VENV_DIR/bin/python" ] || { echo "FAIL: python missing"; exit 1; }
[ -x "$VENV_DIR/bin/jupyter" ] || { echo "FAIL: jupyter missing"; exit 1; }

[ -d "$EXAMPLES_DIR" ] || { echo "FAIL: Examples missing"; exit 1; }
[ -d "$EXAMPLE_DATA_DIR" ] || { echo "FAIL: Example-Data missing"; exit 1; }
[ -d "$USER_DIR" ] || { echo "FAIL: User missing"; exit 1; }

[ -f "$INSTALL_STATE_FILE" ] || { echo "FAIL: install_state.json missing"; exit 1; }
[ -d "$LOG_DIR" ] || { echo "FAIL: logs dir missing"; exit 1; }
find "$LOG_DIR" -type f -name 'install-*.log' -print -quit | grep -q . || { echo "FAIL: no install log found"; exit 1; }

[ -x "$LAUNCHER" ] || { echo "FAIL: launcher missing"; exit 1; }

echo "Testing Python import..."
"$VENV_DIR/bin/python" -c "import kymflow"

echo "Testing Jupyter..."
"$VENV_DIR/bin/jupyter" lab --version

echo "=== PASS ==="