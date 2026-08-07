# -*- mode: python ; coding: utf-8 -*-
# Obfuscated build: entry + tech modules from build/pyarmor_out (PyArmor),
# plus the PyArmor runtime package. All non-code resources unchanged.

import os

PYARMOR_OUT = os.path.join('build', 'pyarmor_out')

a = Analysis(
    [os.path.join(PYARMOR_OUT, 'techtool.py')],
    pathex=[PYARMOR_OUT, '.'],
    binaries=[(os.path.join(PYARMOR_OUT, 'pyarmor_runtime_000000', 'pyarmor_runtime.pyd'), '.')],
    datas=[('scrcpy-win64-v3.3.4.zip', '.'), ('ApkIconHelper.apk', '.'), ('gelotech_database_v3.json', '.'), ('banking_apps.json', '.'), ('gelotech_icon.ico', '.')],
    hiddenimports=['customtkinter', 'PIL', 'PIL.Image', 'PIL.ImageDraw', 'PIL.ImageFont', 'requests',
                   'tkinter', 'tkinter.messagebox', 'tkinter.ttk',
                   'datetime', 'functools', 'hashlib', 'json', 'os', 're', 'shutil', 'subprocess',
                   'sys', 'tempfile', 'threading', 'time',
                   'tech_common', 'tech_ui', 'tech_settings', 'tech_admin', 'tech_secscan', 'tech_secops', 'tech_secops2', 'tech_vtop', 'tech_misc'],
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
