"""合刀 / cal 参数解析。"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Tuple, Union

from ..knife_budget.comp_seconds import COMP_SECONDS_MAX, COMP_SECONDS_MIN


@dataclass
class MergeKnifeParse:
    boss_hp: int
    damage1: int
    damage2: Optional[int]
    display_hp: str
    display_d1: str
    display_d2: Optional[str]
    single_knife: bool


@dataclass
class MergeKnifeCompSecondsParse:
    boss_hp: int
    target_seconds: int
    display_hp: str
    display_seconds: str


MergeKnifeResult = Union[MergeKnifeParse, MergeKnifeCompSecondsParse]


class MergeKnifeCompSecondsRangeError(ValueError):
    """带 s/秒 后缀时秒数不在合法区间。"""


def _parse_amount(token: str) -> Tuple[int, str]:
    t = token.strip()
    if not t:
        raise ValueError("empty")
    suffix = t[-1].lower()
    if suffix == "e":
        num = float(t[:-1])
        return int(round(num * 100_000_000)), f"{t[:-1]}e" if t[:-1] else "0e"
    if suffix == "w":
        num = float(t[:-1])
        return int(round(num * 10_000)), f"{t[:-1]}w" if t[:-1] else "0w"
    num = float(t)
    if num < 1_000_000:
        iv = int(round(num * 10_000))
        if num == int(num):
            return iv, f"{int(num)}w"
        return iv, f"{num}w"
    iv = int(round(num))
    return iv, str(iv)


def _parse_comp_seconds_token(token: str) -> Tuple[Optional[int], bool, bool]:
    """
    解析第二参数是否为期望返还秒数模式。
    返回 (seconds, is_comp_mode, invalid_suffix_range)。
    """
    t = token.strip()
    has_suffix = False
    if t.endswith("秒"):
        has_suffix = True
        t = t[:-1]
    elif t.lower().endswith("s"):
        has_suffix = True
        t = t[:-1]
    try:
        val = float(t)
    except ValueError:
        return None, False, False
    if val != int(val):
        return None, False, False
    sec = int(val)
    if has_suffix:
        if COMP_SECONDS_MIN <= sec <= COMP_SECONDS_MAX:
            return sec, True, False
        return None, True, True
    if 20 < sec <= COMP_SECONDS_MAX:
        return sec, True, False
    return None, False, False


def parse_merge_knife(text: str) -> Optional[MergeKnifeResult]:
    body = text.strip()
    m = re.match(r"^(?:合刀|cal)\s*(.*)$", body, flags=re.I)
    if not m:
        return None
    rest = (m.group(1) or "").strip()
    if not rest:
        return None
    parts = rest.split()
    if len(parts) not in (2, 3):
        return None
    try:
        hp, hp_d = _parse_amount(parts[0])
    except ValueError:
        return None
    if hp <= 0:
        return None

    if len(parts) == 2:
        sec, is_comp, invalid_range = _parse_comp_seconds_token(parts[1])
        if invalid_range:
            raise MergeKnifeCompSecondsRangeError()
        if is_comp and sec is not None:
            disp = parts[1].strip()
            if disp.lower().endswith("s"):
                disp_s = f"{sec}s"
            elif disp.endswith("秒"):
                disp_s = f"{sec}秒"
            else:
                disp_s = str(sec)
            return MergeKnifeCompSecondsParse(
                boss_hp=hp,
                target_seconds=sec,
                display_hp=hp_d,
                display_seconds=disp_s,
            )
        try:
            d1, d1d = _parse_amount(parts[1])
        except ValueError:
            return None
        if d1 <= 0:
            return None
        return MergeKnifeParse(
            boss_hp=hp,
            damage1=d1,
            damage2=None,
            display_hp=hp_d,
            display_d1=d1d,
            display_d2=None,
            single_knife=True,
        )

    try:
        d1, d1d = _parse_amount(parts[1])
        d2, d2d = _parse_amount(parts[2])
    except ValueError:
        return None
    if d1 <= 0 or d2 <= 0:
        return None
    return MergeKnifeParse(
        boss_hp=hp,
        damage1=d1,
        damage2=d2,
        display_hp=hp_d,
        display_d1=d1d,
        display_d2=d2d,
        single_knife=False,
    )
