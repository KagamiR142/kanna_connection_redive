"""当日 knife_budget 计数漂移：timeline/API 与本地 budget 不一致时的软着陆（仅钳制，不抛错）。"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from loguru import logger

if TYPE_CHECKING:
    from ..database.models import KnifeBudget

MAX_USED_FULL = 3
MAX_USED_POINTS = 3.0
MAX_AVAIL_COMP = 3


def add_used_points(budget: "KnifeBudget", delta: float) -> float:
    """累加点数并钳制到 [0, 3]；返回实际写入后的 used_points。"""
    cur = float(budget.used_points or 0)
    budget.used_points = min(MAX_USED_POINTS, max(0.0, cur + float(delta)))
    return float(budget.used_points)


def try_consume_full_slot(
    budget: "KnifeBudget",
    *,
    viewer_id: Optional[int],
    boss_order: int,
    reason: str,
) -> bool:
    """
    尝试消耗一格整刀名额。若 used_full 已满仍返回 False（记 drift 日志），不抛异常。
    """
    used = int(budget.used_full or 0)
    if used < MAX_USED_FULL:
        budget.used_full = used + 1
        return True
    logger.warning(
        "budget_drift 整刀但 used_full={}（仍按 timeline/API 记刀） reason={} viewer={} boss={}",
        used,
        reason,
        viewer_id,
        boss_order,
    )
    return False


def try_consume_comp_slot(
    budget: "KnifeBudget",
    *,
    viewer_id: Optional[int],
    boss_order: int,
    reason: str,
) -> bool:
    avail = int(budget.avail_comp or 0)
    if avail > 0:
        budget.avail_comp = avail - 1
        return True
    logger.warning(
        "budget_drift 补偿但 avail_comp=0（仍按 timeline/API 记刀） reason={} viewer={} boss={}",
        reason,
        viewer_id,
        boss_order,
    )
    return False


def sanitize_budget_counters(
    budget: "KnifeBudget",
    *,
    viewer_id: Optional[int] = None,
    context: str = "",
) -> None:
    """
    将当日 budget 计数钳制到合法区间，避免异常值导致后续逻辑崩溃。
    不跨日修正；仅保证数值可安全参与运算。
    """
    vid = viewer_id or getattr(budget, "viewer_id", None)
    fixes: list[str] = []

    uf = int(budget.used_full or 0)
    if uf < 0:
        budget.used_full = 0
        fixes.append("used_full<0")
    elif uf > MAX_USED_FULL:
        budget.used_full = MAX_USED_FULL
        fixes.append("used_full>3")

    ac = int(budget.avail_comp or 0)
    if ac < 0:
        budget.avail_comp = 0
        fixes.append("avail_comp<0")
    elif ac > MAX_AVAIL_COMP:
        budget.avail_comp = MAX_AVAIL_COMP
        fixes.append("avail_comp>3")

    up = float(budget.used_points or 0)
    if up < 0:
        budget.used_points = 0.0
        fixes.append("used_points<0")
    elif up > MAX_USED_POINTS:
        budget.used_points = MAX_USED_POINTS
        fixes.append("used_points>3")

    if fixes:
        logger.warning(
            "budget_drift sanitize: viewer={} context={} fixes={} uf={} ac={} pts={}",
            vid,
            context or "-",
            ",".join(fixes),
            budget.used_full,
            budget.avail_comp,
            budget.used_points,
        )


__all__ = [
    "MAX_USED_FULL",
    "MAX_USED_POINTS",
    "add_used_points",
    "sanitize_budget_counters",
    "try_consume_comp_slot",
    "try_consume_full_slot",
]
