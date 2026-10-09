"""帮助文本与源文件一致性。"""
from __future__ import annotations

from pathlib import Path

from tests._module_loader import load_module

MODULE_ROOT = Path(__file__).resolve().parents[1]
SOURCE = MODULE_ROOT / "docs" / "user" / "自动报刀帮助.qq.txt"

_help_mod = load_module("clanbattle/user_help.py", "kcr_user_help")
HELP_TEXT = _help_mod.HELP_TEXT


def _load_source_lines() -> list[str]:
    lines: list[str] = []
    for raw in SOURCE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            lines.append(line)
    return lines


def test_help_text_matches_source() -> None:
    expected = "\n".join(_load_source_lines())
    assert HELP_TEXT == expected


def test_help_text_starts_with_help_command() -> None:
    assert HELP_TEXT.splitlines()[0].startswith("【自动报刀帮助】")
