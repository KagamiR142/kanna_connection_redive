"""结算刀型与点数（设计文档 §1.3 + §4.2，四态口径）。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from loguru import logger

from ..database.models import KnifeBudget
from .budget_drift import (
    add_used_points,
    sanitize_budget_counters,
    try_consume_comp_slot,
    try_consume_full_slot,
)
from .classifier import TimelineInfo
from .comp_seconds import assign_kill_comp_seconds, assign_kill_comp_seconds_value
from .kill_comp import KillCompKind
from .knife_state import (
    KnifeDisplayState,
    record_flag_for_state,
    record_is_kill_for_state,
)
from .comp_pool import consume_comp_from_pool
from .timeline_knife import resolve_timeline_verdict

SettledKind = Literal["full", "comp"]


@dataclass
class SettlementResult:
    display_state: KnifeDisplayState
    settled_kind: SettledKind
    points_delta: float
    record_flag: float
    record_is_kill: int
    generated_comp: bool = False
    consumed_comp: bool = False


def _estimate_boss_hp_before(
    boss_current_hp: Optional[int], damage: int, is_kill: bool
) -> int:
    if not is_kill or damage <= 0:
        return 0
    if boss_current_hp is not None and boss_current_hp >= 0:
        return int(boss_current_hp) + int(damage)
    return int(damage)


def _assign_kill_comp_seconds(
    budget: KnifeBudget,
    *,
    kill_comp_seconds: Optional[int],
    hp_before: int,
    damage: int,
    boss_order: int,
    viewer_id: Optional[int],
    kill_comp_kind: Optional[KillCompKind] = None,
) -> None:
    if kill_comp_seconds is not None:
        assign_kill_comp_seconds_value(
            budget,
            kill_comp_seconds,
            boss_order=boss_order,
            viewer_id=viewer_id,
            boss_hp_before=int(hp_before or 0),
            damage=int(damage or 0),
            context="settlement_kill",
        )
        return
    if kill_comp_kind in (
        KillCompKind.CLEANUP,
        KillCompKind.ANOMALY,
        KillCompKind.NONE,
    ):
        logger.debug(
            "跳过合刀公式兜底: viewer={} kind={} R={} D={}",
            viewer_id,
            kill_comp_kind,
            hp_before,
            damage,
        )
        return
    if kill_comp_kind == KillCompKind.MERGE and damage > 0 and hp_before > 0:
        assign_kill_comp_seconds(
            budget,
            hp_before,
            damage,
            boss_order=boss_order,
            viewer_id=viewer_id,
            context="settlement_kill",
        )
    elif damage > 0 and hp_before <= 0 and kill_comp_kind == KillCompKind.MERGE:
        assign_kill_comp_seconds(
            budget,
            max(damage, 1),
            damage,
            boss_order=boss_order,
            viewer_id=viewer_id,
            context="settlement_kill_est_hp",
        )


def _finish(
    budget: KnifeBudget,
    result: SettlementResult,
    *,
    viewer_id: Optional[int],
    boss_order: int,
    context: str,
) -> SettlementResult:
    sanitize_budget_counters(
        budget, viewer_id=viewer_id, context=context or "settlement"
    )
    return result


def _settle_comp_kill(
    budget: KnifeBudget,
    *,
    viewer_id: Optional[int],
    boss_order: int,
    reason: str,
    matched_seconds: Optional[int] = None,
) -> SettlementResult:
    try_consume_comp_slot(
        budget, viewer_id=viewer_id, boss_order=boss_order, reason=reason
    )
    consume_comp_from_pool(
        budget, seconds=matched_seconds, viewer_id=viewer_id
    )
    add_used_points(budget, 0.5)
    state = KnifeDisplayState.COMP_KILL
    logger.info(
        "结算补偿击杀({}): viewer={} boss={} used_pts={} matched_s={}",
        reason,
        viewer_id,
        boss_order,
        budget.used_points,
        matched_seconds,
    )
    return _finish(
        budget,
        SettlementResult(
            display_state=state,
            settled_kind="comp",
            points_delta=0.5,
            record_flag=record_flag_for_state(state),
            record_is_kill=record_is_kill_for_state(state),
            consumed_comp=True,
        ),
        viewer_id=viewer_id,
        boss_order=boss_order,
        context=f"comp_kill:{reason}",
    )


def _settle_comp_non_kill(
    budget: KnifeBudget,
    *,
    viewer_id: Optional[int],
    boss_order: int,
    reason: str,
    matched_seconds: Optional[int] = None,
) -> SettlementResult:
    try_consume_comp_slot(
        budget, viewer_id=viewer_id, boss_order=boss_order, reason=reason
    )
    consume_comp_from_pool(
        budget, seconds=matched_seconds, viewer_id=viewer_id
    )
    add_used_points(budget, 0.5)
    state = KnifeDisplayState.COMP
    logger.info(
        "结算补偿({}): viewer={} boss={} used_pts={} matched_s={}",
        reason,
        viewer_id,
        boss_order,
        budget.used_points,
        matched_seconds,
    )
    return _finish(
        budget,
        SettlementResult(
            display_state=state,
            settled_kind="comp",
            points_delta=0.5,
            record_flag=record_flag_for_state(state),
            record_is_kill=0,
            consumed_comp=True,
        ),
        viewer_id=viewer_id,
        boss_order=boss_order,
        context=f"comp:{reason}",
    )


def _settle_timeline_forced_full(
    budget: KnifeBudget,
    *,
    is_kill: bool,
    damage: int,
    hp_before: int,
    boss_order: int,
    viewer_id: Optional[int],
    kill_comp_seconds: Optional[int],
    kill_comp_kind: Optional[KillCompKind] = None,
) -> SettlementResult:
    reason = "timeline_full"
    if is_kill:
        gained_slot = try_consume_full_slot(
            budget, viewer_id=viewer_id, boss_order=boss_order, reason=reason
        )
        budget.avail_comp = int(budget.avail_comp or 0) + 1
        _assign_kill_comp_seconds(
            budget,
            kill_comp_seconds=kill_comp_seconds,
            hp_before=hp_before,
            damage=damage,
            boss_order=boss_order,
            viewer_id=viewer_id,
            kill_comp_kind=kill_comp_kind,
        )
        add_used_points(budget, 0.5)
        state = KnifeDisplayState.KILL
        logger.info(
            "结算 timeline 整刀击杀: viewer={} boss={} gained_full_slot={} used_pts={}",
            viewer_id,
            boss_order,
            gained_slot,
            budget.used_points,
        )
        return _finish(
            budget,
            SettlementResult(
                display_state=state,
                settled_kind="full",
                points_delta=0.5,
                record_flag=record_flag_for_state(state),
                record_is_kill=record_is_kill_for_state(state),
                generated_comp=True,
            ),
            viewer_id=viewer_id,
            boss_order=boss_order,
            context="timeline_full_kill",
        )

    try_consume_full_slot(
        budget, viewer_id=viewer_id, boss_order=boss_order, reason=reason
    )
    add_used_points(budget, 1.0)
    state = KnifeDisplayState.FULL
    logger.info(
        "结算 timeline 整刀: viewer={} boss={} used_pts={}",
        viewer_id,
        boss_order,
        budget.used_points,
    )
    return _finish(
        budget,
        SettlementResult(
            display_state=state,
            settled_kind="full",
            points_delta=1.0,
            record_flag=record_flag_for_state(state),
            record_is_kill=0,
        ),
        viewer_id=viewer_id,
        boss_order=boss_order,
        context="timeline_full",
    )


def apply_settlement_to_budget(
    budget: KnifeBudget,
    *,
    is_kill: bool,
    damage: int,
    boss_order: int = 0,
    boss_hp_before: Optional[int] = None,
    viewer_id: Optional[int] = None,
    kill_comp_seconds: Optional[int] = None,
    kill_comp_kind: Optional[KillCompKind] = None,
    declared_comp_apply: bool = False,
    timeline: Optional[TimelineInfo] = None,
) -> SettlementResult:
    """在已有 budget 行上应用一次结算，返回四态结果（纯函数，不写库）。"""
    sanitize_budget_counters(budget, viewer_id=viewer_id, context="pre_settlement")
    hp_before = boss_hp_before
    if hp_before is None:
        hp_before = _estimate_boss_hp_before(None, damage, is_kill)

    verdict = resolve_timeline_verdict(
        timeline, budget, is_kill=is_kill, viewer_id=viewer_id
    )
    if verdict.force_comp_settlement:
        reason = "timeline"
        if verdict.matched_comp_seconds is not None:
            reason = f"timeline={verdict.matched_comp_seconds}s"
        matched = verdict.matched_comp_seconds
        if is_kill:
            return _settle_comp_kill(
                budget,
                viewer_id=viewer_id,
                boss_order=boss_order,
                reason=reason,
                matched_seconds=matched,
            )
        return _settle_comp_non_kill(
            budget,
            viewer_id=viewer_id,
            boss_order=boss_order,
            reason=reason,
            matched_seconds=matched,
        )

    if verdict.force_full_settlement:
        return _settle_timeline_forced_full(
            budget,
            is_kill=is_kill,
            damage=damage,
            hp_before=int(hp_before or 0),
            boss_order=boss_order,
            viewer_id=viewer_id,
            kill_comp_seconds=kill_comp_seconds,
            kill_comp_kind=kill_comp_kind,
        )

    if is_kill:
        if declared_comp_apply and budget.avail_comp > 0:
            return _settle_comp_kill(
                budget,
                viewer_id=viewer_id,
                boss_order=boss_order,
                reason="申请带b",
                matched_seconds=None,
            )
        if int(budget.used_full or 0) < 3:
            budget.used_full = int(budget.used_full or 0) + 1
            budget.avail_comp = int(budget.avail_comp or 0) + 1
            add_used_points(budget, 0.5)
            _assign_kill_comp_seconds(
                budget,
                kill_comp_seconds=kill_comp_seconds,
                hp_before=int(hp_before or 0),
                damage=damage,
                boss_order=boss_order,
                viewer_id=viewer_id,
                kill_comp_kind=kill_comp_kind,
            )
            state = KnifeDisplayState.KILL
            logger.info(
                "结算击杀: viewer={} boss={} dmg={} comp_sec={} used_pts={}",
                viewer_id,
                boss_order,
                damage,
                budget.comp_seconds,
                budget.used_points,
            )
            return _finish(
                budget,
                SettlementResult(
                    display_state=state,
                    settled_kind="full",
                    points_delta=0.5,
                    record_flag=record_flag_for_state(state),
                    record_is_kill=record_is_kill_for_state(state),
                    generated_comp=True,
                ),
                viewer_id=viewer_id,
                boss_order=boss_order,
                context="kill",
            )
        if budget.avail_comp > 0:
            return _settle_comp_kill(
                budget,
                viewer_id=viewer_id,
                boss_order=boss_order,
                reason="无整刀名额",
                matched_seconds=None,
            )
        logger.warning(
            "刀型异常(击杀): viewer={} used_full={} avail_comp={}（仍记击杀）",
            viewer_id,
            budget.used_full,
            budget.avail_comp,
        )
        add_used_points(budget, 0.5)
        state = KnifeDisplayState.KILL
        return _finish(
            budget,
            SettlementResult(
                display_state=state,
                settled_kind="full",
                points_delta=0.5,
                record_flag=record_flag_for_state(state),
                record_is_kill=1,
            ),
            viewer_id=viewer_id,
            boss_order=boss_order,
            context="kill_anomaly",
        )

    if budget.avail_comp > 0:
        return _settle_comp_non_kill(
            budget,
            viewer_id=viewer_id,
            boss_order=boss_order,
            reason="budget",
            matched_seconds=None,
        )

    if int(budget.used_full or 0) < 3:
        budget.used_full = int(budget.used_full or 0) + 1
        add_used_points(budget, 1.0)
        state = KnifeDisplayState.FULL
        logger.info(
            "结算整刀: viewer={} boss={} used_pts={}",
            viewer_id,
            boss_order,
            budget.used_points,
        )
        return _finish(
            budget,
            SettlementResult(
                display_state=state,
                settled_kind="full",
                points_delta=1.0,
                record_flag=record_flag_for_state(state),
                record_is_kill=0,
            ),
            viewer_id=viewer_id,
            boss_order=boss_order,
            context="full",
        )

    try_consume_full_slot(
        budget,
        viewer_id=viewer_id,
        boss_order=boss_order,
        reason="整刀名额已用尽",
    )
    add_used_points(budget, 1.0)
    logger.warning(
        "刀型异常(整刀): viewer={} used_full={} avail_comp={}（仍记整刀）",
        viewer_id,
        budget.used_full,
        budget.avail_comp,
    )
    state = KnifeDisplayState.FULL
    return _finish(
        budget,
        SettlementResult(
            display_state=state,
            settled_kind="full",
            points_delta=1.0,
            record_flag=record_flag_for_state(state),
            record_is_kill=0,
        ),
        viewer_id=viewer_id,
        boss_order=boss_order,
        context="full_anomaly",
    )
