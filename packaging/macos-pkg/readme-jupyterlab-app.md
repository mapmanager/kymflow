# KymFlow Jupyter Launcher App Plan (`README-jupyterlab-app.md`)

_Last updated: 2026-03-30T01:42:21.283583+00:00_

**Implementation status:** Implemented in **`scripts/make_jupyter_app.sh`**, wired from **`postinstall.sh`**, **`install-kymflow-curl.sh`**, and **`build_pkg.sh`**. **`CFBundleShortVersionString`** / **`CFBundleVersion`** match the installed KymFlow version passed as the fourth argument. **`conclusion.html`** mentions **`KymFlow Jupyter.app`** and first-launch Gatekeeper (**right-click → Open**).

## Purpose

This document defines the next installer improvement for the current KymFlow macOS package:

- keep the existing installed JupyterLab workflow
- replace or supplement the installed `.command` launcher with a small macOS `.app`
- keep the launcher behavior rooted at:

```text
~/Documents/KymFlow
```

- use a custom icon: **build-time source** is **`packaging/macos-pkg/icons/icon-green.icns`** (local-only, not in the GitHub release tarball). It is staged as **`payload/resources/AppIcon.icns`** in the installer and copied into **`~/Library/.../payload/resources/`** at install time for the helper.

This document is written so that an LLM or developer can implement the change directly.

---

## Source of truth used for this document

This plan is based only on the current uploaded files:

- `build_pkg.sh`
- `postinstall.sh`
- `smoke_test.sh`
- `Distribution.xml`
- `README-kymflow-pkg.md`

The current launcher behavior in `postinstall.sh` is:

- create:
  ```text
  ~/Documents/KymFlow/Open KymFlow.command
  ```
- launcher runs:
  ```text
  $HOME/Library/Application Support/kymflow-pkg/venv/bin/jupyter
  ```
- launcher roots Jupyter at:
  ```text
  ~/Documents/KymFlow
  ```

The current workspace model is:

```text
~/Documents/KymFlow/
  Examples/
  Example-Data/
  User/
  Open KymFlow.command
  KymFlow Jupyter.app/
```

The current runtime root is:

```text
~/Library/Application Support/kymflow-pkg
```

---

## Important path/location rule for this change

For this launcher-app change, all **new** files created by the implementation must stay in user-owned locations under the user home directory.

Use only paths under:

- `~/Library/...`
- `~/Documents/...`

Do **not** introduce any new system-level launcher locations under `/Applications` or other system-wide destinations for this work.

The app to create is:

```text
~/Documents/KymFlow/KymFlow Jupyter.app
```

The **packaging-tree** icon source is **`icons/icon-green.icns`** (under **`macos-pkg/`**). The **installed** icon path read by the helper is **`${APP_ROOT}/payload/resources/AppIcon.icns`**.

---

## Goal

Create a minimal generated app bundle for the existing Jupyter launcher.

The `.app` must:

- be created during install
- launch the same JupyterLab flow as the current `.command` file
- not open a visible Terminal window the way a `.command` file does
- be safe to regenerate on reinstall
- use the current installed venv under:
  ```text
  ~/Library/Application Support/kymflow-pkg/venv
  ```

The existing `.command` file should remain in place initially as a fallback.

---

## Scope

### In scope

- add a helper script to create the Jupyter app bundle
- update `postinstall.sh` to call that helper
- copy the app icon into the bundle
- write `Info.plist`
- write the app executable wrapper
- keep current Jupyter root:
  ```text
  ~/Documents/KymFlow
  ```
- optionally update `smoke_test.sh` to assert the app exists

### Out of scope

- changing the Jupyter command itself
- adding the hypothetical NiceGUI desktop app
- moving launchers to `/Applications`
- removing the `.command` launcher immediately
- changing **`Distribution.xml`** or **`welcome.html`** ( **`conclusion.html`** was updated for `.app` next steps + Gatekeeper)
- building a fully separate distributable prebuilt `.app`

---

## Resulting file tree to create

The implementation should create this app bundle:

```text
~/Documents/KymFlow/KymFlow Jupyter.app/
  Contents/
    Info.plist
    MacOS/
      launch_jupyter
    Resources/
      AppIcon.icns
```

### Meaning of each file

- `Info.plist`
  - identifies the bundle as an app
  - sets bundle name, identifier, icon name, executable name

- `Contents/MacOS/launch_jupyter`
  - executable shell script
  - launches JupyterLab using the existing installed venv

- `Contents/Resources/AppIcon.icns`
  - app icon copied from installer resources

---

## Recommended implementation structure

## New file to add

Add this new helper script:

```text
kymflow/packaging/macos-pkg/scripts/make_jupyter_app.sh
```

Purpose:

- create or refresh `KymFlow Jupyter.app`
- isolate `.app` creation from the larger `postinstall.sh`

This is preferred because `postinstall.sh` is already large.

---

## Keep the existing `.command` launcher

The current launcher file:

```text
~/Documents/KymFlow/Open KymFlow.command
```

should remain for now.

Reasons:

- known-good fallback
- easier debugging during rollout
- lower regression risk

The first milestone is:

- keep `.command`
- add `.app`

---

## Behavior of the app wrapper

The `.app` should run the exact same installed Jupyter flow as the current `.command` launcher.

That means the generated executable inside the app should use:

```bash
APP_ROOT="$HOME/Library/Application Support/kymflow-pkg"
WORKSPACE_ROOT="$HOME/Documents/KymFlow"
JUPYTER_BIN="$APP_ROOT/venv/bin/jupyter"
```

and launch:

```bash
exec "$JUPYTER_BIN" lab --notebook-dir="$WORKSPACE_ROOT"
```

This change is only a **wrapper/UI entry point** change, not a runtime change.

---

## Logging for the `.app`

Because a `.app` launched from Finder normally does **not** open a Terminal window, the app wrapper should redirect output to a log file.

Recommended log path:

```text
~/Library/Application Support/kymflow-pkg/logs/jupyter-app-launch.log
```

Recommended behavior:

- append stdout/stderr to that log
- create the log directory if needed
- fail with a clear message in the log if Jupyter binary is missing

This makes the `.app` usable without Terminal while still preserving debuggability.

---

## Required packaging-tree asset (icon)

Place the launcher icon at:

```text
kymflow/packaging/macos-pkg/icons/icon-green.icns
```

**`build_pkg.sh`** fails fast if this file is missing. It is **not** part of the GitHub release tarball; the build machine must have it.

**`install-kymflow-curl.sh`** copies the same file into **`payload/resources/AppIcon.icns`** only when **`icons/icon-green.icns`** exists next to the curl script (typical developer layout).

---

## Helper script (source of truth)

The live script is **`scripts/make_jupyter_app.sh`**. Usage:

```text
make_jupyter_app.sh <user_home> <app_root> <workspace_root> <bundle_version>
```

- **`bundle_version`:** installed KymFlow version (e.g. from **`pyproject.toml`**), written to **`CFBundleShortVersionString`** and **`CFBundleVersion`** (XML-escaped).
- **`CFBundleIdentifier`:** **`org.cudmore.kymflow.jupyter`** (stable).

**Launcher process:** The **`MacOS/launch_jupyter`** script runs **`jupyter lab` without `exec`** so the bundle executable remains the main process Launch Services tracks (Dock/menu bar). Replacing the process with **`venv` Python** via **`exec`** caused the app icon to disappear while Jupyter still listened on port 8888.

---

## Wiring (`build_pkg.sh`, `postinstall.sh`, curl)

**`build_pkg.sh`**

- Copies **`icons/icon-green.icns`** → **`payload/resources/AppIcon.icns`** (fails if missing).
- Copies **`scripts/make_jupyter_app.sh`** into **`build/pkgbuild-scripts/`** next to **`postinstall`** so **`pkgbuild --scripts`** ships both.

**`postinstall.sh`**

- Defines **`PKG_PAYLOAD_RESOURCES`** (`…/KymFlowPayload/resources`).
- After rsync of **`kymflow/`** into **`${APP_ROOT}/payload/`**, creates **`${PAYLOAD_ROOT}/resources`** and copies **`AppIcon.icns`** from the **package payload** when present (legacy pkgs without it log and continue).
- After **`Open KymFlow.command`**: **`SCRIPT_DIR="$(dirname "$0")"`**, runs **`"${SCRIPT_DIR}/make_jupyter_app.sh" … "${PACKAGED_VERSION}"`**.
- **`chown -R "${CURRENT_USER}:staff" "${WORKSPACE_ROOT}"`** still covers the new **`.app`**.

**`install-kymflow-curl.sh`**

- Optionally copies **`icons/icon-green.icns`** (next to the curl script) into **`payload/resources/AppIcon.icns`**.
- Runs **`"${SOURCE_ROOT}/packaging/macos-pkg/scripts/make_jupyter_app.sh"`** with the same four arguments after creating the **`.command`** file.

The **`.command`** launcher remains unchanged.

---

## Recommended installed tree after this change

After install, expected workspace tree becomes:

```text
~/Documents/KymFlow/
  Examples/
  Example-Data/
  User/
  Open KymFlow.command
  KymFlow Jupyter.app/
    Contents/
      Info.plist
      MacOS/
        launch_jupyter
      Resources/
        AppIcon.icns
```

Expected user app-support tree remains:

```text
~/Library/Application Support/kymflow-pkg/
  uv/
  venv/
  payload/
    kymflow/
    resources/
      AppIcon.icns
  logs/
  install_version.txt
  install_state.json
```

---

## `smoke_test.sh`

**Implemented:** asserts **`[ -d "$WORKSPACE_ROOT/KymFlow Jupyter.app" ]`** in addition to the **`.command`** check. See **`smoke_test.sh`** in the repo.

---

## Recommended implementation order (checklist)

1. Ensure **`icons/icon-green.icns`** exists on the **pkg** build machine.
2. Ship **`scripts/make_jupyter_app.sh`** and wire **`build_pkg.sh`**, **`postinstall.sh`**, **`install-kymflow-curl.sh`**, **`smoke_test.sh`** (done in tree).
3. Install and verify **`.command`** and **`KymFlow Jupyter.app`** (Gatekeeper first open as needed).

---

## Acceptance criteria

The change is complete when all of the following are true:

- pkg install succeeds
- workspace contains:
  - `Open KymFlow.command`
  - `KymFlow Jupyter.app`
- double-clicking `KymFlow Jupyter.app` launches JupyterLab
- JupyterLab is rooted at:
  ```text
  ~/Documents/KymFlow
  ```
- Terminal does not visibly open during app launch
- the app icon is shown
- `smoke_test.sh` passes

---

## Notes for implementation

- The `.app` is a generated local wrapper app, not a separate signed distributed app artifact.
- This is why no additional app-signing workflow is required for this task.
- The critical current trust boundary remains the signed installer package.
- The new `.app` is only a better user-facing launcher for the already-installed Jupyter runtime.
- **Gatekeeper:** users may need **right-click → Open** the first time; **`conclusion.html`** mentions this.

---

## Bottom line

The correct implementation is:

- keep the current Jupyter launcher behavior
- move `.app` creation into a dedicated helper script
- stage **`icons/icon-green.icns`** as **`payload/resources/AppIcon.icns`**
- generate:
  ```text
  ~/Documents/KymFlow/KymFlow Jupyter.app
  ```
- keep `Open KymFlow.command` as fallback
- update smoke test to verify the app exists
