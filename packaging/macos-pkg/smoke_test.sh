#!/bin/bash
set -euo pipefail

APP_ROOT="$HOME/Library/Application Support/kymflow-pkg"
VENV_DIR="${APP_ROOT}/venv"
WORKSPACE="$HOME/Documents/KymFlow"
NOTEBOOKS="$WORKSPACE/Notebooks"
DATA="$WORKSPACE/Data"
LAUNCHER="$WORKSPACE/Open KymFlow.command"

echo "=== KymFlow smoke test ==="

[ -x "$VENV_DIR/bin/python" ] || { echo "FAIL: python missing"; exit 1; }
[ -x "$VENV_DIR/bin/jupyter" ] || { echo "FAIL: jupyter missing"; exit 1; }
[ -d "$NOTEBOOKS" ] || { echo "FAIL: notebooks missing"; exit 1; }
[ -d "$DATA" ] || { echo "FAIL: data missing"; exit 1; }
[ -x "$LAUNCHER" ] || { echo "FAIL: launcher missing"; exit 1; }

echo "Testing Python import..."
"$VENV_DIR/bin/python" -c "import kymflow"

echo "Testing Jupyter..."
"$VENV_DIR/bin/jupyter" lab --version

echo "=== PASS ==="
