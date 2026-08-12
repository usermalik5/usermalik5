# -*- mode: python ; coding: utf-8 -*-
# Obfuscated build: entry + tech modules from build/pyarmor_out (PyArmor),
# plus the PyArmor runtime package. All non-code resources unchanged.

import os

PYARMOR_OUT = os.path.join('build', 'pyarmor_out')

a = Analysis(
    [os.path.join(PYARMOR_OUT, 'techtool.py')],
    pathex=[PYARMOR_OUT, '.'],
    binaries=[(os.path.join(PYARMOR_OUT, 'pyarmor_runtime_000000', 'pyarmor_runtime.pyd'), '.')],
    datas=[('scrcpy-win64-v3.3.4.zip', '.'), ('ApkIconHelper.apk', '.'), ('banking_apps.json', '.'), ('gelotech_icon.ico', '.'), ('tech_phone_mirror.py', '.'), ('assets', 'assets')],
    hiddenimports=['customtkinter', 'PIL', 'PIL.Image', 'PIL.ImageDraw', 'PIL.ImageFont', 'PIL.ImageTk', 'requests',
                   'tkinter', 'tkinter.messagebox', 'tkinter.ttk',
                   'datetime', 'functools', 'hashlib', 'json', 'os', 're', 'shutil', 'subprocess',
                   'sys', 'tempfile', 'threading', 'time', 'base64', 'secrets', 'smtplib', 'webbrowser',
                   'email', 'email.message', 'email.utils',
                   'cryptography', 'cryptography.hazmat.primitives.asymmetric.ed25519',
                   'tech_common', 'tech_ui', 'tech_settings', 'tech_admin', 'tech_reg', 'tech_secscan',
                   'tech_secops', 'tech_secops3', 'tech_secops2', 'tech_secops4', 'tech_dash', 'tech_vtop', 'tech_misc',
                   'tech_hardening', 'tech_hardening_ops', 'tech_dashboard_redesign',
                   'tech_phone_mirror', 'tech_phone_mirror_embedded', 'tech_phone_mirror_host', 'tech_phone_mirror_fix',
                   'tech_phone_mirror_restore_patch', 'tech_navigation', 'tech_task_manager', 'tech_database',
                   'sitecustomize', 'importlib', 'importlib.util', 'inspect', 'pathlib'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['runtime_hook_gelotech.py'],
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