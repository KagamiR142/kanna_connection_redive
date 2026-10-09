"""补偿刀秒数（设计文档 §1.3）：110 - 90R/D，结果向上取整后封顶 90。"""
from __future__ import annotations

import math
from typing import Optional

from loguru import logger

# 满补临界倍率 D/R > 90/21（≈ 4.286）
FULL_COMP_DAMAGE_RATIO = 90 / 21

COMP_SECONDS_MIN = 21
COMP_SECONDS_MAX = 90


class CompSecondsOutOfRangeError(ValueError):
    """结算写入的补偿秒数不在游戏合法区间 [21, 90]。"""


def calc_cleanup_comp_seconds(battle_time: int) -> int:
    """收尾击杀：110 − 游戏内战斗耗时，封顶 90、下限 21（§1.3.4）。"""
    t = int(battle_time)
    raw = 110 - t
    return int(min(COMP_SECONDS_MAX, max(COMP_SECONDS_MIN, raw)))


def calc_comp_seconds(boss_hp_before: int, damage: int) -> int:
    """
    计算补偿秒数（向上取整后封顶 90）。
    预览/合刀场景可能得到 <21 或 0；写入 budget 前须 validate_comp_seconds。
    """
    if damage <= 0:
        return 0
    try:
        raw = 110 - (boss_hp_before / (damage / 90))
    except ZeroDivisionError:
        return 0
    if raw <= 0:
        return 0
    return int(min(COMP_SECONDS_MAX, math.ceil(raw)))


def validate_comp_seconds(
    seconds: int,
    *,
    boss_hp_before: int,
    damage: int,
    viewer_id: Optional[int] = None,
    context: str = "settlement",
) -> None:
    if COMP_SECONDS_MIN <= seconds <= COMP_SECONDS_MAX:
        return
    logger.error(
        "补偿秒数越界 context={} viewer={} R={} D={} sec={} (合法区间 {}–{})",
        context,
        viewer_id,
        boss_hp_before,
        damage,
        seconds,
        COMP_SECONDS_MIN,
        COMP_SECONDS_MAX,
    )
    raise CompSecondsOutOfRangeError(
        f"补偿秒数 {seconds} 不在 [{COMP_SECONDS_MIN}, {COMP_SECONDS_MAX}]"
    )


def assign_kill_comp_seconds_value(
    budget,
    seconds: int,
    *,
    boss_order: int = 0,
    viewer_id: Optional[int] = None,
    boss_hp_before: int = 0,
    damage: int = 0,
    context: str = "settlement",
) -> int:
    """将已算好的击杀补偿秒数写入 budget（与 resolve_kill_comp_seconds 共用）。"""
    sec = int(seconds)
    try:
        validate_comp_seconds(
            sec,
            boss_hp_before=boss_hp_before,
            damage=damage,
            viewer_id=viewer_id,
            context=context,
        )
    except CompSecondsOutOfRangeError:
        from .comp_pool import write_comp_pool

        write_comp_pool(budget, [])
        return 0
    from .comp_pool import add_comp_to_pool

    add_comp_to_pool(
        budget,
        sec,
        boss_order=boss_order,
        viewer_id=viewer_id,
    )
    logger.debug(
        "补偿秒数写入: viewer={} boss={} R={} D={} sec={}",
        viewer_id,
        boss_order,
        boss_hp_before,
        damage,
        sec,
    )
    return sec


def assign_kill_comp_seconds(
    budget,
    boss_hp_before: int,
    damage: int,
    *,
    boss_order: int = 0,
    viewer_id: Optional[int] = None,
    context: str = "settlement",
) -> int:
    """击杀产补偿：计算、校验并写入 budget；越界则清零并返回 0。"""
    sec = calc_comp_seconds(boss_hp_before, damage)
    try:
        validate_comp_seconds(
            sec,
            boss_hp_before=boss_hp_before,
            damage=damage,
            viewer_id=viewer_id,
            context=context,
        )
    except CompSecondsOutOfRangeError:
        from .comp_pool import write_comp_pool

        write_comp_pool(budget, [])
        return 0
    from .comp_pool import add_comp_to_pool

    add_comp_to_pool(
        budget,
        sec,
        boss_order=boss_order,
        viewer_id=viewer_id,
    )
    logger.debug(
        "补偿秒数写入: viewer={} boss={} R={} D={} sec={}",
        viewer_id,
        boss_order,
        boss_hp_before,
        damage,
        sec,
    )
    return sec


def min_damage_for_full_comp(remaining_hp: int) -> int:
    """后手刀获得满补（90 秒）所需的最小整数伤害（先手后剩余 R 已知）。"""
    if remaining_hp <= 0:
        return 0
    return int(math.ceil(remaining_hp * 90 / 21))


def min_first_damage_when_partner_second(
    boss_hp: int, partner_damage: int
) -> int:
    """已知后手伤害为 partner，先手至少需要的伤害使后手满补。"""
    if partner_damage <= 0:
        return 0
    need = boss_hp - partner_damage * 21 / 90
    return max(0, int(math.ceil(need)))


def min_partner_damage_for_kill_full_comp(boss_hp: int, kill_damage: int) -> int:
    """先手一刀已可击杀时，另一刀垫刀满补线。"""
    need = boss_hp - kill_damage / FULL_COMP_DAMAGE_RATIO
    return max(0, int(math.ceil(need)))


def min_identical_damage_for_target_comp(
    boss_hp: int, target_seconds: int, knife_index: int
) -> int:
    """
    n 刀相同伤害、最后一刀获目标补偿秒数 S 时，每刀最小整数伤害。
    D_n = ⌊90×H / ((111−S) + 90×(n−1))⌋（H 为 Boss 血量整数，与合刀计算器一致）。
    """
    s = int(target_seconds)
    n = int(knife_index)
    if s < COMP_SECONDS_MIN or s > COMP_SECONDS_MAX or n < 1:
        return 0
    denom = (111 - s) + 90 * (n - 1)
    if denom <= 0:
        return 0
    return (90 * int(boss_hp)) // denom
