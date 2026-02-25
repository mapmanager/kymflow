APP_PLIST="dist/KymFlow.app/Contents/Info.plist"


APP_VERSION="$(python -c 'from importlib.metadata import version; print(version("kymflow"))' 2>/dev/null || echo '0.0.0')"
BUNDLE_BUILD="$(python -c 'from kymflow import _build_info; print(getattr(_build_info, "BUILD_BUNDLE_VERSION", "0"))' 2>/dev/null || echo "0")"


if [ -f "$APP_PLIST" ]; then
  echo "[build_arm] Setting macOS bundle version in Info.plist: $APP_VERSION"

  # CFBundleShortVersionString (user-visible)
  /usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $APP_VERSION" "$APP_PLIST" 2>/dev/null \
    || /usr/libexec/PlistBuddy -c "Add :CFBundleShortVersionString string $APP_VERSION" "$APP_PLIST"

# CFBundleVersion (build number)
 /usr/libexec/PlistBuddy -c "Set :CFBundleVersion $BUNDLE_BUILD" "$APP_PLIST" 2>/dev/null \
   || /usr/libexec/PlistBuddy -c "Add :CFBundleVersion string $BUNDLE_BUILD" "$APP_PLIST"
   
  echo "[build_arm] Info.plist now contains:"
  /usr/libexec/PlistBuddy -c "Print :CFBundleShortVersionString" "$APP_PLIST" || true
  /usr/libexec/PlistBuddy -c "Print :CFBundleVersion" "$APP_PLIST" || true
else
  echo "WARNING: Info.plist not found at $APP_PLIST"
fi