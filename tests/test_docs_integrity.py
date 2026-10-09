"""文档链接与检查脚本冒烟测试。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]


def test_docs_internal_links() -> None:
    proc = subprocess.run(
        [sys.executable, str(MODULE_ROOT / "scripts" / "check_docs.py"), "--skip-help"],
        cwd=MODULE_ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_help_sync_script_check_mode() -> None:
    proc = subprocess.run(
        [sys.executable, str(MODULE_ROOT / "scripts" / "sync_help_text.py"), "--check"],
        cwd=MODULE_ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
