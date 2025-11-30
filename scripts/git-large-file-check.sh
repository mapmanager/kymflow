#!/usr/bin/env bash
# Shared script: check for too-large files in git

set -euo pipefail

# ===== configuration =====
MAX_SIZE_MB=60                     # change this if needed
MAX_SIZE_BYTES=$((MAX_SIZE_MB * 1024 * 1024))

MODE="${1:-staged}"                # "staged" or "tracked"

# Select file list based on mode
case "$MODE" in
  staged)
    echo "🔍 Large file check (> ${MAX_SIZE_MB}MB) on STAGED files..."
    FILES=$(git diff --cached --name-only --diff-filter=ACM)
    ;;
  tracked)
    echo "🔍 Large file check (> ${MAX_SIZE_MB}MB) on ALL TRACKED files..."
    FILES=$(git ls-files)
    ;;
  *)
    echo "Unknown mode '$MODE' (expected 'staged' or 'tracked')" >&2
    exit 1
    ;;
esac

if [ -z "${FILES}" ]; then
  echo "✓ No files to check."
  exit 0
fi

BLOCK=0

for file in $FILES; do
  if [ ! -f "$file" ]; then
    continue
  fi

  size_bytes=$(wc -c < "$file" | tr -d '[:space:]')

  if [ "$size_bytes" -gt "$MAX_SIZE_BYTES" ]; then
    size_mb=$((size_bytes / 1024 / 1024))
    echo "❌ ERROR: '$file' is ${size_mb}MB (limit: ${MAX_SIZE_MB}MB)"
    BLOCK=1
  fi
done

if [ "$BLOCK" -ne 0 ]; then
  echo
  echo "❌ Operation aborted — large files detected."
  echo "Fix the files or add them to Git LFS."
  exit 1
fi

# PASS MESSAGE
echo "✓ All files OK — no large files detected."

exit 0
