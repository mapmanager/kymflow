# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['/Users/cudmore/Sites/kymflow_outer/kymflow/src/kymflow/gui_v2/app.py'],
    pathex=[],
    binaries=[],
    datas=[('/Users/cudmore/Sites/kymflow_outer/kymflow/pyinstaller/macos/build_feb_2026/.venv-build/lib/python3.11/site-packages/nicegui', 'nicegui')],
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
    name='KymFlow',
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
    icon=['/Users/cudmore/Sites/kymflow_outer/kymflow/pyinstaller/macos/kymflow.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='KymFlow',
)
app = BUNDLE(
    coll,
    name='KymFlow.app',
    icon='/Users/cudmore/Sites/kymflow_outer/kymflow/pyinstaller/macos/kymflow.icns',
    bundle_identifier='com.robertcudmore.kymflow',
)
