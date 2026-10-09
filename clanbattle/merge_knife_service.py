"""合刀 / cal 文案（补偿秒数与 comp_seconds 模块一致）。"""
from __future__ import annotations

from ..knife_budget.comp_seconds import (
    calc_comp_seconds,
    min_damage_for_full_comp,
    min_first_damage_when_partner_second,
    min_identical_damage_for_target_comp,
    min_partner_damage_for_kill_full_comp,
)
from .merge_knife_parser import MergeKnifeCompSecondsParse, MergeKnifeParse, MergeKnifeResult


def _fmt_damage(value: int) -> str:
    if value <= 0:
        return "0"
    if value % 10_000 == 0 and value < 100_000_000:
        return f"{value // 10_000}w"
    return str(value)


def _fmt_damage_required(value: int) -> str:
    """满补线等精确阈值：始终展示完整整数，不做 w 缩写。"""
    return "0" if value <= 0 else str(value)


def _order_line(
    first_label: str,
    second_label: str,
    remaining: int,
    second_damage: int,
) -> str:
    sec = calc_comp_seconds(remaining, second_damage)
    line = f"若{first_label}先出，{second_label}后出，补偿{sec}秒。"
    if sec < 90:
        need_d = _fmt_damage_required(min_damage_for_full_comp(remaining))
        line += f"若需要满补，另一刀至少需要{need_d}"
    return line


def _kill_first_line(kill_label: str, boss_hp: int, kill_damage: int) -> str:
    partner_d = _fmt_damage_required(
        min_partner_damage_for_kill_full_comp(boss_hp, kill_damage)
    )
    return (
        f"若{kill_label}先出，可直接击杀boss。"
        f"若想获得满补，另一刀伤害不能低于{partner_d}"
    )


def _single_knife_lines(h: int, d1: int, label: str) -> list[str]:
    need_second = _fmt_damage_required(min_damage_for_full_comp(h - d1))
    need_first = _fmt_damage_required(min_first_damage_when_partner_second(h, d1))
    return [
        f"若{label}先出，后出刀需{need_second}伤害可满补",
        f"若{label}后出，先出刀需{need_first}伤害可满补",
    ]


def build_merge_knife_comp_seconds_reply(parsed: MergeKnifeCompSecondsParse) -> str:
    h = parsed.boss_hp
    s = parsed.target_seconds
    lines = [
        f"boss血量={parsed.display_hp}",
        f"期望返还时间={parsed.display_seconds}",
        "刀数 || 所需伤害",
    ]
    for n in (1, 2, 3):
        dmg = min_identical_damage_for_target_comp(h, s, n)
        dmg_w = dmg // 10_000
        lines.append(f"{n}刀      {dmg_w}w")
    return "\n".join(lines)


def build_merge_knife_reply(parsed: MergeKnifeResult) -> str:
    if isinstance(parsed, MergeKnifeCompSecondsParse):
        return build_merge_knife_comp_seconds_reply(parsed)
    h = parsed.boss_hp
    d1 = parsed.damage1
    hp_d, a = parsed.display_hp, parsed.display_d1

    if parsed.single_knife:
        lines = [
            f"boss血量={hp_d}",
            f"对boss伤害={a}",
            *_single_knife_lines(h, d1, a),
        ]
        return "\n".join(lines)

    d2 = parsed.damage2 or 0
    b = parsed.display_d2 or ""
    lines = [
        f"boss血量={hp_d}",
        f"对boss伤害={a} | {b}",
    ]

    if d1 + d2 < h:
        lines.append(f"剩余{_fmt_damage(h - d1 - d2)}")
        return "\n".join(lines)

    if d1 >= h:
        lines.append(_kill_first_line(a, h, d1))
    if d2 >= h:
        lines.append(_kill_first_line(b, h, d2))

    if h > d1 and h > d2:
        lines.append(_order_line(a, b, h - d1, d2))
        lines.append(_order_line(b, a, h - d2, d1))

    return "\n".join(lines)


MERGE_KNIFE_FORMAT_HELP = (
    "合刀格式：合刀<boss血量> <第一刀伤害> [<第二刀伤害>]\n"
    "或：cal<boss血量> <第一刀伤害> [<第二刀伤害>]\n"
    "合刀与第一个数之间的空格可省略；参数之间必须有空格。\n"
    "省略第二刀时：第二参数 21～90 为期望返还秒数（模板 E）；≤20 为伤害（模板 D）。\n"
    "数字小于100万自动×1万（展示加w）；末尾w表示×1万；末尾e表示×1亿。\n"
    "例：合刀600 320 330 / 合刀3600 2950 / 合刀576885 90 / cal 43238 35600 25000"
)

MERGE_KNIFE_COMP_SECONDS_RANGE_HELP = (
    "期望返还时间须在 21～90 秒之间（例：合刀 6000w 21 或 合刀6000w 90s）"
)
