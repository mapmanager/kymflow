source ./secrets.sh

TESTAPP="dist/NotarySmoke.app"
TESTZIP="dist/NotarySmoke.zip"
BUNDLE_ID="com.robertcudmore.notarysmoke"

rm -rf "$TESTAPP" "$TESTZIP"
mkdir -p "$TESTAPP/Contents/MacOS" "$TESTAPP/Contents"

cat > "$TESTAPP/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleExecutable</key><string>NotarySmoke</string>
  <key>CFBundleIdentifier</key><string>$BUNDLE_ID</string>
  <key>CFBundleName</key><string>NotarySmoke</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>0.0.1</string>
  <key>CFBundleVersion</key><string>1</string>
</dict></plist>
EOF

cat > "$TESTAPP/Contents/MacOS/NotarySmoke" <<'EOF'
#!/bin/bash
echo "notary smoke test"
EOF
chmod +x "$TESTAPP/Contents/MacOS/NotarySmoke"

codesign --force --options runtime --timestamp --sign "$SIGN_ID" "$TESTAPP/Contents/MacOS/NotarySmoke"
codesign --force --options runtime --timestamp --sign "$SIGN_ID" "$TESTAPP"
codesign --verify --deep --strict --verbose=2 "$TESTAPP"

ditto -c -k --sequesterRsrc --keepParent "$TESTAPP" "$TESTZIP"

xcrun notarytool submit "$TESTZIP" --keychain-profile "$NOTARY_PROFILE"