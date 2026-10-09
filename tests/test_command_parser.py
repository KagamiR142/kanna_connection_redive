"""指令解析单元测试（无需 Hoshino 环境）。"""
from __future__ import annotations

from tests._module_loader import load_module

_cp = load_module("clanbattle/command_parser.py", "kcr_command_parser")
parse_board_message = _cp.parse_board_message
parse_boss_lap_records = _cp.parse_boss_lap_records
parse_cancel_board_message = _cp.parse_cancel_board_message
parse_tree = _cp.parse_tree
parse_cancel_tree = _cp.parse_cancel_tree


def test_board_message_colon_variants() -> None:
    for sep in (":", "：", "﹕", "︰"):
        p = parse_board_message(f"留言3{sep}今晚别动")
        assert p is not None
        assert p.boss == 3
        assert p.remark == "今晚别动"


def test_cancel_board_message() -> None:
    boss, ok = parse_cancel_board_message("取消留言2")
    assert ok
    assert boss == 2


def test_parse_tree_variants() -> None:
    p = parse_tree("挂树")
    assert p is not None
    assert p.boss is None
    assert p.remark == ""
    p2 = parse_tree("挂树：失误了")
    assert p2 is not None
    assert p2.boss is None
    assert p2.remark == "失误了"
    p3 = parse_tree("挂树3")
    assert p3 is not None
    assert p3.boss == 3
    p4 = parse_tree("挂树3：留言")
    assert p4 is not None
    assert p4.boss == 3
    assert p4.remark == "留言"
    assert parse_cancel_tree("取消挂树")
    assert not parse_cancel_tree("挂树")


def test_boss_lap_records() -> None:
    p = parse_boss_lap_records("出刀记录3")
    assert p is not None
    assert p.boss == 3
    p_sp = parse_boss_lap_records("出刀记录 3 a")
    assert p_sp is not None
    assert p_sp.boss == 3
    assert p_sp.all_laps
    assert p.lap is None
    p2 = parse_boss_lap_records("出刀记录1周目15")
    assert p2.lap == 15
    p3 = parse_boss_lap_records("出刀记录2 29")
    assert p3.boss == 2
    assert p3.lap == 29
    p4 = parse_boss_lap_records("出刀记录229")
    assert p4.boss == 2
    assert p4.lap == 29
    p5 = parse_boss_lap_records("出刀记录3a")
    assert p5.all_laps
