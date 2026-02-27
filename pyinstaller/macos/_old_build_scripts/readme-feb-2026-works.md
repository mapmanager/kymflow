


## workflow:

Run these from pyinstaller/macos/

1. Build the app
 
```
./build_arm_v2.sh
```

This uses nicegui-pack to create dist/KymFlow.app

2. Sign the app with codesign and make KymFlow-pre-notarize.zip
```
./codesign_and_zip.sh
```

This will codesign dist/KymFlow.app and then (properly) zip with ditto into KymFlow-pre-notarize.zip

3. Submit pre-notarize zip to apple cloud notarytool
```
/usr/bin/arch -arm64 /Applications/Xcode.app/Contents/Developer/usr/bin/notarytool submit dist/KymFlow-pre-notarize.zip \
  --keychain-profile "my-notarytool-profile-feb2025"
```

Wait for a valid response like this. Do not proceed if there is a `bus error`.

```
Conducting pre-submission checks for KymFlow-pre-notarize.zip and initiating connection to the Apple notary service...
Submission ID received
  id: 35d3b6df-08b7-44a9-a9e4-12ff50bbabce
Upload progress: 100.00% (113 MB of 113 MB)   
Successfully uploaded file
```

Note the id, can use this to check progess on apple notarytool cloud server.

Look for `"status":"Accepted"`.

```
xcrun notarytool info 35d3b6df-08b7-44a9-a9e4-12ff50bbabce \
  --keychain-profile "my-notarytool-profile-feb2025" \
  --output-format json
```

4. locally staple the original dist/KymFlow.app

```
xcrun stapler staple dist/KymFlow.app
spctl --assess --type execute --verbose=4 dist/KymFlow.app
```

5. make final KymFlow.zip for distribution to users.
```
ditto -c -k --sequesterRsrc --keepParent KymFlow.app KymFlow.zip
```
