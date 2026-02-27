#!/usr/bin/env bash
# Local-only secrets for signing + notarization.
#
# Copy to _secrets.sh and edit:
#   cp _secrets.example.sh _secrets.sh
#   chmod 600 _secrets.sh

export SIGN_ID='Developer ID Application: <YOUR_NAME> (<TEAM_ID>)'

# Name you used with: xcrun notarytool store-credentials <NAME> ...
export NOTARY_PROFILE='<YOUR_NOTARYTOOL_PROFILE_NAME>'
