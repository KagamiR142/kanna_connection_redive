"""整刀击杀补偿秒数：合刀 (90R/D) 与收尾 (110−T) 统一入口（§1.3.3～§1.3.4）。"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

from loguru import logger

from .comp_seconds import (
    CompSecondsOutOfRangeError,
    calc_cleanup_comp_seconds,
    calc_comp_seconds,
    validate_comp_seconds,
)


class KillCompKind(str, Enum):
    MERGE = "merge"
    CLEANUP = "cleanup"
    ANOMALY = "anomaly"
    NONE = "none"


@dataclass
class KillCompResult:
    kind: KillCompKind
    seconds: Optional[int] = None
    remaining: int = 0
    damage: int = 0


def classify_kill_comp(remaining: int, damage: int, *, is_kill: bool) -> KillCompKind:
    if not is_kill or damage <= 0:
        return KillCompKind.NONE
    r, d = int(remaining), int(damage)
    if d > r:
        return KillCompKind.MERGE
    if d == r:
        return KillCompKind.CLEANUP
    if r > 0:
        logger.info(
            "击杀按合刀处理(D<R): R={} D={} 使用 R_eff=D",
            r,
            d,
        )
        return KillCompKind.MERGE
    logger.warning(
        "击杀补偿分类异常: R={} D={} (D<R 且 kill=true)",
        r,
        d,
    )
    return KillCompKind.ANOMALY


def resolve_kill_comp_seconds(
    remaining: int,
    damage: int,
    *,
    is_kill: bool,
    battle_time: Optional[int] = None,
    viewer_id: Optional[int] = None,
    context: str = "kill",
) -> KillCompResult:
    """计算击杀补偿秒数；写入 budget / 报刀推送共用此结果。"""
    kind = classify_kill_comp(remaining, damage, is_kill=is_kill)
    if kind == KillCompKind.NONE:
        return KillCompResult(kind=kind, remaining=remaining, damage=damage)
    if kind == KillCompKind.ANOMALY:
        return KillCompResult(kind=kind, remaining=remaining, damage=damage)

    if kind == KillCompKind.MERGE:
        r_merge = int(remaining)
        if int(damage) < r_merge:
            r_merge = int(damage)
        sec = calc_comp_seconds(r_merge, damage)
        try:
            validate_comp_seconds(
                sec,
                boss_hp_before=r_merge,
                damage=damage,
                viewer_id=viewer_id,
                context=context,
            )
        except CompSecondsOutOfRangeError:
            logger.error(
                "合刀击杀补偿越界 context={} viewer={} R={} D={} sec={}",
                context,
                viewer_id,
                remaining,
                damage,
                sec,
            )
            return KillCompResult(
                kind=KillCompKind.ANOMALY, remaining=remaining, damage=damage
            )
        logger.info(
            "合刀击杀补偿: context={} viewer={} R={} D={} sec={}",
            context,
            viewer_id,
            remaining,
            damage,
            sec,
        )
        return KillCompResult(
            kind=kind, seconds=sec, remaining=remaining, damage=damage
        )

    if battle_time is None:
        logger.warning(
            "收尾击杀缺少 battle_time: viewer={} R={} D={}",
            viewer_id,
            remaining,
            damage,
        )
        return KillCompResult(
            kind=KillCompKind.ANOMALY, remaining=remaining, damage=damage
        )
    sec = calc_cleanup_comp_seconds(int(battle_time))
    try:
        validate_comp_seconds(
            sec,
            boss_hp_before=remaining,
            damage=damage,
            viewer_id=viewer_id,
            context=context,
        )
    except CompSecondsOutOfRangeError:
        logger.error(
            "收尾击杀补偿越界 context={} viewer={} T={} sec={}",
            context,
            viewer_id,
            battle_time,
            sec,
        )
        return KillCompResult(
            kind=KillCompKind.ANOMALY, remaining=remaining, damage=damage
        )
    logger.info(
        "收尾击杀补偿: context={} viewer={} R={} D={} T={} sec={}",
        context,
        viewer_id,
        remaining,
        damage,
        battle_time,
        sec,
    )
    return KillCompResult(kind=kind, seconds=sec, remaining=remaining, damage=damage)


def format_kill_comp_push_prefix(result: KillCompResult) -> Optional[str]:
    if result.kind == KillCompKind.MERGE and result.seconds is not None:
        return f"成功击杀并获得了{result.seconds}秒的补偿。"
    if result.kind == KillCompKind.CLEANUP and result.seconds is not None:
        return f"成功击杀并获得了{result.seconds}秒的补偿。"
    if result.kind == KillCompKind.ANOMALY:
        return "成功击杀，补偿秒数异常，请联系管理。"
    return None
