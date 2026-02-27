# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['app_min.py'],
    pathex=[],
    binaries=[],
    datas=[('/Users/cudmore/Sites/kymflow_outer/kymflow/pyinstaller/macos/min_example/.venv_min/lib/python3.11/site-packages/nicegui', 'nicegui')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='NiceGUIMin',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='NiceGUIMin',
)
app = BUNDLE(
    coll,
    name='NiceGUIMin.app',
    icon=None,
    bundle_identifier='com.robertcudmore.niceguimin',
)
