#!/usr/bin/env python3
"""GeloTech agent preflight.

Run this before starting a coding task.  It deliberately has no external
runtime dependencies and exits non-zero when required repository instructions
are missing or empty.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (ROOT / "AGENTS.md", ROOT / "README.md")


def main() -> int:
    print("=" * 68)
    print(" GELOTECH AGENT PREFLIGHT")
    print("=" * 68)
    print()
    print("MANDATORY: read these files before modifying any code:")
    print()

    failed = False
    for path in REQUIRED:
        rel = path.relative_to(ROOT)
        if not path.is_file():
            print(f"[FAIL] {rel} is missing")
            failed = True
            continue
        data = path.read_bytes()
        if not data.strip():
            print(f"[FAIL] {rel} is empty")
            failed = True
            continue
        digest = hashlib.sha256(data).hexdigest()[:12]
        print(f"[ OK ] {rel} (sha256:{digest})")

    print()
    print("Required workflow:")
    print("  1. Read AGENTS.md completely.")
    print("  2. Read the relevant README.md sections completely.")
    print("  3. Inspect the existing implementation before editing.")
    print("  4. Reproduce/trace the problem and identify the root cause.")
    print("  5. Make the smallest correct change.")
    print("  6. Run the required source-level verification.")
    print("  7. Review git diff before committing.")
    print()

    if failed:
        print("PREFLIGHT FAILED: restore the required instruction files first.")
        return 1

    print("PREFLIGHT PASSED: instruction files are present and non-empty.")
    print("IMPORTANT: passing preflight does not replace actually reading them.")
    print("=" * 68)
    return 0


if __name__ == "__main__":
    sys.exit(main())
