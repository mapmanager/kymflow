#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_FILE="${SCRIPT_DIR}/launch_jupyter.swift"
OUTPUT_FILE="${1:-${SCRIPT_DIR}/launch_jupyter}"

[ -f "${SOURCE_FILE}" ] || {
  echo "ERROR: missing source file: ${SOURCE_FILE}" >&2
  exit 1
}

command -v swiftc >/dev/null 2>&1 || {
  echo "ERROR: swiftc not found (install Xcode command line tools)." >&2
  exit 1
}

mkdir -p "$(dirname "${OUTPUT_FILE}")"
swiftc \
  -O \
  -target arm64-apple-macos13.0 \
  -framework AppKit \
  -framework Foundation \
  "${SOURCE_FILE}" \
  -o "${OUTPUT_FILE}"

chmod +x "${OUTPUT_FILE}"
echo "Built native launcher: ${OUTPUT_FILE}"
