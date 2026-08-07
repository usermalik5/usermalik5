# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['techtool.py'],
    pathex=[],
    binaries=[],
    datas=[('scrcpy-win64-v3.3.4.zip', '.'), ('ApkIconHelper.apk', '.'), ('gelotech_database_v3.json', '.'), ('gelotech_icon.ico', '.')],
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
    a.binaries,
    a.datas,
    [],
    name='GeloTechTool',
    icon='gelotech_icon.ico',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
