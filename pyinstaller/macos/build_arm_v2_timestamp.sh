# -----------------------------------------------------------------------------
# Build stamp: write a tiny module that will be bundled by PyInstaller
# -----------------------------------------------------------------------------
BUILD_TS_UTC="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
BUILD_LOCAL="$(date '+%Y-%m-%d %H:%M:%S %Z')"
GIT_SHA="$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
GIT_DIRTY="$(git diff --quiet && echo 'clean' || echo 'dirty')"

BUILD_INFO_PATH="../../src/kymflow/_build_info.py"

cat > "$BUILD_INFO_PATH" <<EOF
# Auto-generated at build time. DO NOT EDIT.
BUILD_TIMESTAMP = "${BUILD_LOCAL}"
BUILD_GIT_STATUS = "SHA:${GIT_SHA} STATUS:${GIT_DIRTY}"
EOF

echo "[build_arm] Wrote build info: $BUILD_INFO_PATH"
echo "[build_arm] ---- _build_info.py ----"
cat "$BUILD_INFO_PATH"
echo "[build_arm] ------------------------"