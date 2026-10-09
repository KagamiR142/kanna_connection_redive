"""出刀结算单管道：damage_history 唯一预算入口；战报四态由 record_persist 写库。"""
from __future__ import annotations

from typing import Optional

from loguru import logger

from .classifier import TimelineInfo
from .kill_comp import KillCompKind
from .service import knife_budget_service
from .settlement import SettlementResult


async def settle_from_damage_history(
    viewer_id: int,
    *,
    is_kill: bool,
    damage: int,
    create_time: int,
    boss_order: int,
    boss_hp_before: Optional[int],
    kill_comp_seconds: Optional[int] = None,
    kill_comp_kind: Optional[KillCompKind] = None,
    declared_comp_apply: bool = False,
    timeline: Optional[TimelineInfo] = None,
) -> SettlementResult:
    """监控 damage_history 结算（唯一写 knife_budget 的路径）。"""
    result = await knife_budget_service.apply_settlement(
        viewer_id,
        is_kill,
        damage,
        create_time,
        boss_order=boss_order,
        boss_hp_before=boss_hp_before,
        kill_comp_seconds=kill_comp_seconds,
        kill_comp_kind=kill_comp_kind,
        declared_comp_apply=declared_comp_apply,
        timeline=timeline,
    )
    logger.debug(
        "knife_pipeline.settle: viewer={} boss={} kill={} timeline_srt={} kind={} state={}",
        viewer_id,
        boss_order,
        is_kill,
        timeline.start_remain_time if timeline else None,
        result.settled_kind,
        result.display_state,
    )
    return result


__all__ = ["settle_from_damage_history"]
