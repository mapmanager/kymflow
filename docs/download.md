# Download KymFlow

KymFlow is available as a one-click desktop application for macOS.

## Download

Download the latest release from the [GitHub Releases page](https://github.com/mapmanager/kymflow/releases).

The macOS application is provided as a `.zip` file containing `KymFlow.app`.

## Installation (macOS)

### Step 1: Download and Extract

1. Download the `KymFlow-macos-intel-*.zip` file from the releases page
2. Uncompress the zip file (double-click or use `unzip` in Terminal)
3. You should now have a `KymFlow.app` file

### Step 2: Run the Application (First Time)

macOS may show a warning about an "unknown developer" when you first try to open the app. This is normal for applications that aren't signed with an Apple Developer certificate. To run KymFlow:

1. **Option + Right-click** (or Control + Click) on `KymFlow.app`
2. Select **"Open"** from the context menu
3. You will see a warning dialog saying "KymFlow is from an unidentified developer"
4. Click **"Open"** in the warning dialog
5. The application will launch

!!! note "First Time Only"
    You only need to do this once. After the first time, you can double-click `KymFlow.app` normally and it will open without any warnings.

### Alternative Method

If you prefer using Terminal:

```bash
# Navigate to the folder containing KymFlow.app
cd /path/to/KymFlow.app

# Remove the quarantine attribute
xattr -d com.apple.quarantine KymFlow.app

# Now you can open it normally
open KymFlow.app
```

## System Requirements

- **macOS**: 10.13 (High Sierra) or later
- **Architecture**: Intel (x86_64)
- **Python**: Included in the app bundle (no separate installation needed)

## Troubleshooting

### App Won't Open

If the app still won't open after following the steps above:

1. Check System Preferences → Security & Privacy
2. Look for a message about KymFlow being blocked
3. Click "Open Anyway" if available

### App Crashes on Launch

- Check the Console app (Applications → Utilities → Console) for error messages
- Ensure you're running a supported macOS version
- Try downloading the latest release

## Alternative: Install from Source

If you prefer to install from source or need the latest development version, see the [Installation Guide](user-guide/installation.md) for instructions on installing via `uv` or `pip`.

## Getting Help

- **Issues**: Report problems on [GitHub Issues](https://github.com/mapmanager/kymflow/issues)
- **Documentation**: See the [User Guide](user-guide/getting-started.md) for usage instructions
