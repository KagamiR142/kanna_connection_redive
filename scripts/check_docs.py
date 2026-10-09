#!/usr/bin/env python3
"""文档完整性检查：内部链接、帮助文本同步。"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = MODULE_ROOT / "docs"
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def check_internal_links() -> list[str]:
    errors: list[str] = []
    for md in DOCS_ROOT.rglob("*.md"):
        if "backup" in md.parts:
            continue
        text = md.read_text(encoding="utf-8")
        for target in LINK_RE.findall(text):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            if target.startswith("#"):
                continue
            resolved = (md.parent / target).resolve()
            if not resolved.exists():
                errors.append(f"{md.relative_to(MODULE_ROOT)}: 链接不存在 {target}")
    return errors


def check_help_sync() -> int:
    script = MODULE_ROOT / "scripts" / "sync_help_text.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--check"],
        cwd=MODULE_ROOT,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print(proc.stdout or proc.stderr)
    return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-help", action="store_true")
    args = parser.parse_args()

    failed = False

    link_errors = check_internal_links()
    if link_errors:
        failed = True
        print("文档链接检查失败:")
        for e in link_errors:
            print(f"  - {e}")
    else:
        print(f"文档链接 OK（已扫描 {DOCS_ROOT}）")

    if not args.skip_help:
        if check_help_sync() != 0:
            failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
