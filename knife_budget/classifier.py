"""混合刀型判定：timeline 为主，补偿优先预算推测为辅（设计文档第四章）。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from loguru import logger

from ..database.models import KnifeBudget


@dataclass
class TimelineInfo:
    battle_time: int
    start_remain_time: int


def timeline_flag(
    timeline: TimelineInfo, budget: Optional[KnifeBudget] = None
) -> float:
    """RecordDao.flag；实现见 `timeline_knife.timeline_record_flag`。"""
    from .timeline_knife import timeline_record_flag

    return timeline_record_flag(timeline, budget=budget)


def classify_hybrid(
    timeline: TimelineInfo,
    budget: KnifeBudget,
    is_kill: bool = False,
    boss_hp_before: Optional[int] = None,
    damage: Optional[int] = None,
) -> Tuple[float, KnifeBudget, bool]:
    """返回 (flag, 更新后的 budget, is_anomaly)。"""
    from .timeline_knife import is_timeline_comp_entry

    t_flag = timeline_flag(timeline)

    from .comp_pool import consume_comp_from_pool

    if is_timeline_comp_entry(timeline):
        if is_kill:
            if budget.avail_comp > 0:
                budget.avail_comp -= 1
            budget.used_points = min(3.0, budget.used_points + 0.5)
            consume_comp_from_pool(budget, viewer_id=budget.viewer_id)
            return 0.5, budget, False
        if budget.avail_comp > 0:
            budget.avail_comp -= 1
            budget.used_points = min(3.0, budget.used_points + 0.5)
            consume_comp_from_pool(budget, viewer_id=budget.viewer_id)
            return 0.5, budget, False

    if t_flag == 1.0:
        budget.used_points = min(3.0, budget.used_points + 0.5)
        if is_kill and budget.used_full < 3:
            budget.used_full += 1
            budget.avail_comp += 1
            if boss_hp_before is not None and damage:
                from .comp_seconds import assign_kill_comp_seconds

                assign_kill_comp_seconds(
                    budget,
                    boss_hp_before,
                    damage,
                    viewer_id=budget.viewer_id,
                    context="classifier_timeline_kill",
                )
        return 1.0, budget, False

    if is_kill and budget.used_full < 3:
        budget.used_full += 1
        budget.avail_comp += 1
        budget.used_points = min(3.0, budget.used_points + 0.5)
        if boss_hp_before is not None and damage:
            from .comp_seconds import assign_kill_comp_seconds

            assign_kill_comp_seconds(
                budget,
                boss_hp_before,
                damage,
                viewer_id=budget.viewer_id,
                context="classifier_kill",
            )
        return 0.0, budget, False

    if budget.avail_comp > 0:
        budget.avail_comp -= 1
        budget.used_points = min(3.0, budget.used_points + 0.5)
        consume_comp_from_pool(budget, viewer_id=budget.viewer_id)
        return 0.5, budget, False

    if budget.used_full < 3:
        budget.used_full += 1
        budget.used_points = min(3.0, budget.used_points + 1.0)
        return 0.0, budget, False

    logger.warning(
        "刀型异常：viewer_id={} used_full={} avail_comp={} is_kill={}",
        budget.viewer_id,
        budget.used_full,
        budget.avail_comp,
        is_kill,
    )
    return t_flag, budget, True
