#!/usr/bin/env python3
"""从 docs/user/自动报刀帮助.qq.txt 生成 clanbattle/user_help.py。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
SOURCE = MODULE_ROOT / "docs" / "user" / "自动报刀帮助.qq.txt"
TARGET = MODULE_ROOT / "clanbattle" / "user_help.py"


def parse_help_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not line.startswith("【"):
            raise ValueError(f"帮助行必须以【开头: {line!r}")
        lines.append(line)
    if not lines:
        raise ValueError("帮助源文件为空")
    return lines


def build_module_content_multiline(lines: list[str]) -> str:
    """使用三引号拼接，避免转义问题。"""
    quoted = "\n".join(lines)
    return (
        '"""QQ 自动报刀帮助正文（由 scripts/sync_help_text.py 生成，请勿手改）。"""\n'
        "from __future__ import annotations\n\n"
        f'HELP_TEXT = """{quoted}""".strip()\n'
    )


def load_source() -> list[str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(SOURCE)
    return parse_help_lines(SOURCE.read_text(encoding="utf-8"))


def read_existing_help() -> str | None:
    if not TARGET.is_file():
        return None
    ns: dict = {}
    exec(TARGET.read_text(encoding="utf-8"), ns)
    return ns.get("HELP_TEXT")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="仅检查生成文件是否与源一致，不写入",
    )
    args = parser.parse_args()

    lines = load_source()
    new_content = build_module_content_multiline(lines)
    new_help = "\n".join(lines)

    if args.check:
        existing = read_existing_help()
        if existing is None:
            print("缺少 clanbattle/user_help.py，请运行: python scripts/sync_help_text.py")
            return 1
        if existing != new_help:
            print("clanbattle/user_help.py 与 docs/user/自动报刀帮助.qq.txt 不一致")
            print("请运行: python scripts/sync_help_text.py")
            return 1
        print("help text OK")
        return 0

    TARGET.write_text(new_content, encoding="utf-8", newline="\n")
    print(f"已写入 {TARGET.relative_to(MODULE_ROOT)}（{len(lines)} 条）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
