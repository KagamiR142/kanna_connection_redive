"""util.display 导入路径回归（Phase 3 拆分后易写错相对路径）。"""
from __future__ import annotations

from tests._module_loader import load_module

_names = load_module("util/display/names.py", "kcr_util_display_names")
sanitize_display_name = _names.sanitize_display_name
qq_display_name = _names.qq_display_name


def test_util_display_names_import() -> None:
    assert qq_display_name(123, "测试昵称", "") == "测试昵称"


def test_sanitize_display_name_truncates() -> None:
    long_name = "一二三四五六七八九十"
    assert sanitize_display_name(long_name, fallback="x") == "一二三四五六七八九十"[:10]
