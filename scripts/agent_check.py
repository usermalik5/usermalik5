#!/usr/bin/env python3
"""Fast GeloTech agent environment check.

Verifies, where available, the Python interpreter, dev tools (pytest, ruff,
basedpyright), required project files, test discovery, and syntax compilation.
Optional tools are reported clearly instead of failing the whole workflow.

No network access and no application imports are required.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = (
    "AGENTS.md",
    "README.md",
    "PROCESS_GUIDE.md",
    "pyproject.toml",
    "requirements-dev.txt",
    "scripts/agent_preflight.py",
    "scripts/agent_check.py",
)


def _section(title: str) -> None:
    print("=" * 60)
    print(f" {title}")
    print("=" * 60)


def _have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def _version(cmd: str) -> str:
    try:
        out = subprocess.run(
            [cmd, "--version"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        line = (out.stdout or out.stderr).strip().splitlines()[0]
        return line
    except Exception:
        return "unknown"


def _check(label: str, ok: bool, detail: str = "") -> None:
    mark = "OK" if ok else "MISSING"
    line = f"[{mark}] {label}"
    if detail:
        line += f"  ({detail})"
    print(line)


def main() -> int:
    _section("GELOTECH AGENT ENVIRONMENT")
    print()

    # Python (always present; report its actual version).
    py_ver = sys.version.split()[0]
    _check("Python", True, py_ver)

    # pytest (required for the supported workflow).
    pytest_ok = _have("pytest")
    _check("pytest", pytest_ok, _version("pytest") if pytest_ok else "")

    # ruff (optional dev tool).
    ruff_ok = _have("ruff")
    _check("Ruff", ruff_ok, _version("ruff") if ruff_ok else "not installed")

    # basedpyright (optional dev tool).
    bp_ok = _have("basedpyright")
    _check("BasedPyright", bp_ok, _version("basedpyright") if bp_ok else "not installed")

    # Required project files.
    print()
    files_ok = True
    for rel in REQUIRED_FILES:
        ok = (ROOT / rel).is_file()
        files_ok = files_ok and ok
        _check(rel, ok)

    # Test discovery.
    print()
    tests_dir = ROOT / "tests"
    tests_ok = tests_dir.is_dir() and bool(list(tests_dir.glob("test_*.py")))
    detail = "no test_*.py found"
    collected = 0
    if tests_ok:
        try:
            res = subprocess.run(
                [sys.executable, "-m", "pytest", "--collect-only", "-q"],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=ROOT,
            )
            for line in (res.stdout or "").splitlines():
                m = re.match(r"^.*\.py:\s*(\d+)\s*$", line.strip())
                if m:
                    collected += int(m.group(1))
            detail = f"{collected} tests collected"
            tests_ok = res.returncode == 0 and collected > 0
        except Exception as exc:  # noqa: BLE001 - report, never crash the check
            detail = f"collection error: {exc}"
            tests_ok = False
    _check("tests discovered", tests_ok, detail)

    # Syntax compilation.
    print()
    try:
        res = subprocess.run(
            [sys.executable, "-m", "compileall", "-q", "."],
            capture_output=True,
            text=True,
            timeout=180,
            cwd=ROOT,
        )
        compile_ok = res.returncode == 0
        detail = "" if compile_ok else (res.stderr or res.stdout).strip().splitlines()[-1]
    except Exception as exc:  # noqa: BLE001
        compile_ok = False
        detail = str(exc)
    _check("syntax compilation", compile_ok, detail)

    print()
    if not (pytest_ok and files_ok):
        print("RESULT: required components missing; environment is NOT ready.")
        return 1
    if not (ruff_ok and bp_ok):
        print("RESULT: environment ready (optional dev tools missing; install via requirements-dev.txt).")
    else:
        print("RESULT: environment ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
