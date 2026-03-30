# Jupyter launcher app icon

Place **`icon-green.icns`** in this directory before running **`build_pkg.sh`**.

The file is **not** part of the GitHub release tarball; it is a **local packaging asset**. Without it, **`build_pkg.sh`** exits with an error pointing here.

After a successful pkg install, a copy is staged as **`payload/resources/AppIcon.icns`** inside the installer and ends up under **`~/Library/Application Support/kymflow-pkg/payload/resources/`** for **`make_jupyter_app.sh`**.

For **`install-kymflow-curl.sh`**, the same filename is optional: if present next to the curl script, it is copied into the installed payload for a custom Dock/Finder icon.
