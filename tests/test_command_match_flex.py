"""指令 flex-rex 与 parse 成对测试。"""
from __future__ import annotations

import re

from tests._module_loader import load_module

_cm = load_module("clanbattle/command_match.py", "kcr_command_match")
_cp = load_module("clanbattle/command_parser.py", "kcr_command_parser_flex")

strict_rex = _cm.strict_rex
proxy_rex = _cm.proxy_rex
REX_BOSS_LAP_RECORDS = _cm.REX_BOSS_LAP_RECORDS
REX_QUERY_BOSS = _cm.REX_QUERY_BOSS
REX_APPLY = _cm.REX_APPLY
REX_CLEAR_APPLY = _cm.REX_CLEAR_APPLY
REX_BOARD_MESSAGE = _cm.REX_BOARD_MESSAGE
REX_DROP_KNIFE = _cm.REX_DROP_KNIFE
REX_TODAY_REPORT_SLOT = _cm.REX_TODAY_REPORT_SLOT
REX_MONITOR_3 = _cm.REX_MONITOR_3

parse_boss_lap_records = _cp.parse_boss_lap_records
parse_apply = _cp.parse_apply
parse_clear_apply = _cp.parse_clear_apply
parse_board_message = _cp.parse_board_message


def _matches(pattern: str, text: str) -> bool:
    return re.match(pattern, text) is not None


def test_boss_lap_records_flex_rex_and_parse() -> None:
    rex = strict_rex(REX_BOSS_LAP_RECORDS)
    for text in ("出刀记录3", "出刀记录 3", "出刀记录3 a", "出刀记录 3 a"):
        assert _matches(rex, text)
        p = parse_boss_lap_records(text)
        assert p is not None
        assert p.boss == 3


def test_query_boss_flex_rex() -> None:
    rex = strict_rex(REX_QUERY_BOSS)
    assert _matches(rex, "查3")
    assert _matches(rex, "查 3")


def test_apply_flex_rex() -> None:
    rex = proxy_rex(REX_APPLY)
    assert _matches(rex, "进 3")
    assert _matches(rex, "申请出刀 2：满补")


def test_clear_apply_flex_rex() -> None:
    rex = strict_rex(REX_CLEAR_APPLY)
    assert _matches(rex, "清空申请 1")
    boss, all_bosses, matched = parse_clear_apply("清空申请 1")
    assert matched
    assert boss == 1
    assert not all_bosses


def test_board_message_flex_rex() -> None:
    rex = proxy_rex(REX_BOARD_MESSAGE)
    assert _matches(rex, "留言 3：今晚别动")
    p = parse_board_message("留言 3：今晚别动")
    assert p is not None
    assert p.boss == 3


def test_drop_knife_flex_rex() -> None:
    rex = proxy_rex(REX_DROP_KNIFE)
    assert _matches(rex, "掉刀 2")


def test_today_report_flex_rex() -> None:
    rex = proxy_rex(REX_TODAY_REPORT_SLOT)
    assert _matches(rex, "今日战报 1")


def test_monitor_flex_rex() -> None:
    rex = strict_rex(REX_MONITOR_3)
    assert _matches(rex, "出刀监控 3")
    assert _matches(rex, "开启出刀监控 3")
