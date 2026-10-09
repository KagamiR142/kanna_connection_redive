#!/usr/bin/env python3
"""本地开发一键检查（文档 + 测试 + ruff）。"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("KCR_TOOLING", "1")


def run(cmd: list[str], *, optional: bool = False) -> bool:
    print(f"\n>>> {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=MODULE_ROOT)
    if proc.returncode != 0 and not optional:
        return False
    return proc.returncode == 0


def main() -> int:
    steps = [
        ([sys.executable, "scripts/sync_help_text.py", "--check"], False),
        ([sys.executable, "scripts/check_docs.py"], False),
        ([sys.executable, "-m", "pytest"], False),
        (["ruff", "check", "scripts", "tests", "conftest.py"], True),
    ]
    failed = False
    for cmd, optional in steps:
        ok = run(cmd, optional=optional)
        if not ok and not optional:
            failed = True
            print(f"FAILED: {' '.join(cmd)}")
    if failed:
        print("\n检查未通过。")
        return 1
    print("\n全部检查通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
