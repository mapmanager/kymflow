#!/usr/bin/env bash
# Local-only secrets for signing + notarization.
#
# Copy to _secrets.sh and edit:
#   cp _secrets.example.sh _secrets.sh
#   chmod 600 _secrets.sh

# Developer ID Application: Robert Cudmore (794C773KDS)
# export SIGN_ID='Developer ID Application: <YOUR_NAME> (<TEAM_ID>)'
export SIGN_ID='Developer ID Application: Robert Cudmore (794C773KDS)'

# Name you used with: xcrun notarytool store-credentials <NAME> ...
# my-notarytool-profile-feb2025
#export NOTARY_PROFILE='<YOUR_NOTARYTOOL_PROFILE_NAME>'
export NOTARY_PROFILE='my-notarytool-profile-feb2025'
