# -*- coding: utf-8 -*-
"""Repeatable GeloTech release build helper.

This script intentionally does not commit, tag, push, or publish releases.
It validates the source tree, runs tests, regenerates PyArmor output, and
builds the supported obfuscated PyInstaller executable.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULES = [
    "techtool.py", "tech_common.py", "tech_ui.py", "tech_settings.py", "tech_admin.py",
    "tech_reg.py", "tech_secscan.py", "tech_secops.py", "tech_secops3.py", "tech_secops2.py",
    "tech_secops4.py", "tech_dash.py", "tech_vtop.py", "tech_misc.py", "tech_hardening.py",
    "tech_hardening_ops.py", "tech_dashboard_redesign.py", "tech_phone_mirror.py",
    "tech_phone_mirror_embedded.py", "tech_phone_mirror_host.py", "tech_phone_mirror_fix.py",
    "tech_phone_mirror_restore_patch.py", "tech_navigation.py", "tech_task_manager.py",
    "tech_database.py", "tech_phone_mirror/__init__.py", "runtime_hook_gelotech.py", "sitecustomize.py",
]


def run(*args):
    print("+", " ".join(map(str, args)))
    subprocess.run(args, cwd=ROOT, check=True)


def preflight():
    run(sys.executable, str(ROOT / "scripts" / "agent_preflight.py"))
    run(sys.executable, "-m", "compileall", "-q", ".")
    run(sys.executable, "-m", "pytest", "-q")


def build(obfuscated=True):
    if not obfuscated:
        run(sys.executable, "-m", "PyInstaller", "GeloTechTool.spec", "--noconfirm")
        return
    missing = [name for name in MODULES if not (ROOT / name).is_file()]
    if missing:
        raise SystemExit("Missing release module(s): " + ", ".join(missing))
    pyarmor = shutil.which("pyarmor")
    if not pyarmor:
        raise SystemExit("PyArmor is required for the supported release build.")
    run(pyarmor, "gen", "-O", "build/pyarmor_out", *MODULES)
    run(sys.executable, "-m", "PyInstaller", "GeloTechTool_obf.spec", "--noconfirm")


def main():
    parser = argparse.ArgumentParser(description="Build GeloTech Tool consistently.")
    parser.add_argument("--standard", action="store_true", help="Build the non-obfuscated debug EXE.")
    parser.add_argument("--skip-tests", action="store_true", help="Skip preflight/tests (not recommended).")
    args = parser.parse_args()

    if not args.skip_tests:
        preflight()
    build(obfuscated=not args.standard)
    print("Release build completed. No Git commit, tag, push, or release was performed.")


if __name__ == "__main__":
    main()
