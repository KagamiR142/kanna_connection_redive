"""出刀记录 a 模式解析。"""
from __future__ import annotations

from tests._module_loader import load_module

_cp = load_module("clanbattle/command_parser.py", "kcr_cp")
parse_boss_lap_records = _cp.parse_boss_lap_records


def test_boss_lap_records_all_laps_modes() -> None:
    p = parse_boss_lap_records("出刀记录2a")
    assert p is not None
    assert p.boss == 2
    assert p.all_laps
    assert p.day_token is None
    assert p.lap is None

    p2 = parse_boss_lap_records("出刀记录2at")
    assert p2.all_laps
    assert p2.day_token == "t"

    p3 = parse_boss_lap_records("出刀记录2ay")
    assert p3.all_laps
    assert p3.day_token == "y"


def test_boss_lap_records_lap_still_works() -> None:
    p = parse_boss_lap_records("出刀记录229")
    assert p is not None
    assert p.boss == 2
    assert p.lap == 29
    assert not p.all_laps
