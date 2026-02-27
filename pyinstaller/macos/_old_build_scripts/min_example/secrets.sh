#!/usr/bin/env bash

# ----------------------------
# Code Signing Identity
# ----------------------------
# From: security find-identity -v -p codesigning
export SIGN_ID='Developer ID Application: Robert Cudmore (794C773KDS)'

# ----------------------------
# Notarytool Keychain Profile
# ----------------------------
# Created via:
# xcrun notarytool store-credentials "<profile-name>" ...
export NOTARY_PROFILE='my-notarytool-profile-feb2025'

# ----------------------------
# Optional (only if you later use direct credentials instead of keychain)
# Leave commented unless needed.
# ----------------------------
# export APPLE_ID='<your-apple-id@email.com>'
# export APPLE_TEAM_ID='<TEAMID>'
# export APPLE_APP_PASSWORD='<app-specific-password>'