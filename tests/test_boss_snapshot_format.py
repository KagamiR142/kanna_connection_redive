"""Boss 状态行格式单元测试。"""
from __future__ import annotations

import sys
import types

from tests._module_loader import PKG, load_module

_fake_base = types.ModuleType(f"{PKG}.clanbattle.base")
_fake_base.format_precent = lambda n: f"{n * 100:.2f}%"
_fake_base.format_bignum = lambda n: str(n)
sys.modules[f"{PKG}.clanbattle.base"] = _fake_base

_bs = load_module("clanbattle/boss_snapshot.py", "kcr_boss_snapshot")
BossSnap = _bs.BossSnap
format_apply_boss_status_line = _bs.format_apply_boss_status_line
format_boss_status_line = _bs.format_boss_status_line


def test_apply_boss_status_line_uses_w_suffix() -> None:
    snap = BossSnap(boss=1, lap=30, current_hp=1440000000, max_hp=1440000000, fighter_num=0)
    line = format_apply_boss_status_line(snap)
    assert line == "30周目 144000w/144000w，100.00%"


def test_report_boss_status_line_unchanged() -> None:
    snap = BossSnap(boss=1, lap=30, current_hp=1440000000, max_hp=1440000000, fighter_num=0)
    line = format_boss_status_line(snap)
    assert "144000w" in line
    assert "（" in line
