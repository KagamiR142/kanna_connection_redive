"""合刀解析与模板 E 单元测试。"""
from __future__ import annotations

from tests._module_loader import load_module

_mkp = load_module("clanbattle/merge_knife_parser.py", "kcr_merge_knife_parser")
_mks = load_module("clanbattle/merge_knife_service.py", "kcr_merge_knife_service")
_cs = load_module("knife_budget/comp_seconds.py", "kcr_comp_seconds")

parse_merge_knife = _mkp.parse_merge_knife
MergeKnifeCompSecondsParse = _mkp.MergeKnifeCompSecondsParse
MergeKnifeParse = _mkp.MergeKnifeParse
MergeKnifeCompSecondsRangeError = _mkp.MergeKnifeCompSecondsRangeError
build_merge_knife_reply = _mks.build_merge_knife_reply
min_identical_damage_for_target_comp = _cs.min_identical_damage_for_target_comp


def test_merge_knife_90_enters_template_e() -> None:
    parsed = parse_merge_knife("合刀 576885 90")
    assert isinstance(parsed, MergeKnifeCompSecondsParse)
    assert parsed.target_seconds == 90
    reply = build_merge_knife_reply(parsed)
    assert "期望返还时间=90" in reply
    assert "467744w" in reply


def test_merge_knife_20_is_damage_mode() -> None:
    parsed = parse_merge_knife("合刀 576885 20")
    assert isinstance(parsed, MergeKnifeParse)
    assert parsed.single_knife
    assert parsed.damage1 == 20 * 10_000


def test_merge_knife_320_is_damage_mode() -> None:
    parsed = parse_merge_knife("合刀 576885 320")
    assert isinstance(parsed, MergeKnifeParse)
    assert parsed.damage1 == 320 * 10_000


def test_merge_knife_90s_suffix() -> None:
    parsed = parse_merge_knife("合刀 6000w 90s")
    assert isinstance(parsed, MergeKnifeCompSecondsParse)
    assert parsed.target_seconds == 90


def test_merge_knife_15s_out_of_range() -> None:
    try:
        parse_merge_knife("合刀 6000w 15s")
        assert False, "expected MergeKnifeCompSecondsRangeError"
    except MergeKnifeCompSecondsRangeError:
        pass


def test_comp_seconds_damage_values() -> None:
    h = 576885 * 10_000
    d1 = min_identical_damage_for_target_comp(h, 90, 1)
    d2 = min_identical_damage_for_target_comp(h, 90, 2)
    d3 = min_identical_damage_for_target_comp(h, 90, 3)
    assert d1 // 10_000 == 2472364
    assert d2 // 10_000 == 467744
    assert d3 // 10_000 == 258306


def test_single_knife_full_comp_damage_not_abbreviated() -> None:
    parsed = parse_merge_knife("合刀 5770 5000")
    assert isinstance(parsed, MergeKnifeParse)
    reply = build_merge_knife_reply(parsed)
    assert "33000000伤害可满补" in reply
    assert "46033334伤害可满补" in reply
    assert "3300w伤害可满补" not in reply
