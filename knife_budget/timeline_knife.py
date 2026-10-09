"""timeline_report 刀型 — 游戏 API 数据，全模块单管道（最高优先级）。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, TYPE_CHECKING

from loguru import logger

from .classifier import TimelineInfo
from .knife_state import KnifeDisplayState

if TYPE_CHECKING:
    from ..database.models import KnifeBudget

# 进本分配时长 < 90s → 补偿刀进本（无 comp_seconds 可比对时的兜底）
COMP_ENTRY_MAX_SECONDS = 90


@dataclass(frozen=True)
class TimelineVerdict:
    """timeline + budget 对结算/四态的统一判定。"""

    force_comp_settlement: bool = False
    force_full_settlement: bool = False
    display_state: Optional[KnifeDisplayState] = None
    matched_comp_seconds: Optional[int] = None


def comp_seconds_candidates(budget: "KnifeBudget") -> List[int]:
    from .comp_pool import comp_seconds_candidates as pool_candidates

    return pool_candidates(budget)


def account_has_comp_for_timeline(budget: "KnifeBudget") -> bool:
    from .comp_pool import pool_has_comp_resources

    return pool_has_comp_resources(budget)


def points_remaining_for_budget(budget: "KnifeBudget") -> float:
    """当日剩余可消耗点数（步长 0.5），用于击杀是否还能用整刀。"""
    return max(0.0, 3.0 - float(getattr(budget, "used_points", 0) or 0))


def is_timeline_comp_entry(timeline: Optional[TimelineInfo]) -> bool:
    """进本分配 <90s（无 budget 比对时的兜底）。"""
    if timeline is None:
        return False
    return int(timeline.start_remain_time or 0) < COMP_ENTRY_MAX_SECONDS


def _display_from_timeline(timeline: TimelineInfo, *, is_kill: bool) -> KnifeDisplayState:
    if int(timeline.battle_time or 0) < int(timeline.start_remain_time or 0):
        return KnifeDisplayState.KILL if is_kill else KnifeDisplayState.FULL
    if is_timeline_comp_entry(timeline):
        return KnifeDisplayState.COMP_KILL if is_kill else KnifeDisplayState.COMP
    return KnifeDisplayState.KILL if is_kill else KnifeDisplayState.FULL


def resolve_timeline_verdict(
    timeline: Optional[TimelineInfo],
    budget: Optional["KnifeBudget"],
    *,
    is_kill: bool,
    viewer_id: Optional[int] = None,
) -> TimelineVerdict:
    """
    结算/四态共用。

    击杀且 srt>=90 且 points 剩余>=1.0 时优先整刀击杀（高于补偿池秒数匹配）。
    非击杀：有 comp_seconds 时优先 start_remain_time==x 匹配；
    不匹配且仍有整刀槽位 → 整刀（高于 <90 兜底）。
    """
    if timeline is None or budget is None:
        return TimelineVerdict()

    srt = int(timeline.start_remain_time or 0)
    has_full = int(budget.used_full or 0) < 3
    points_remain = points_remaining_for_budget(budget)
    candidates = comp_seconds_candidates(budget)
    vid = viewer_id or getattr(budget, "viewer_id", None)

    if (
        is_kill
        and srt >= COMP_ENTRY_MAX_SECONDS
        and points_remain >= 1.0
    ):
        logger.info(
            "timeline击杀优先整刀: viewer={} start_remain={} points_remain={} "
            "used_pts={} comp_candidates={}",
            vid,
            srt,
            points_remain,
            budget.used_points,
            candidates,
        )
        return TimelineVerdict(
            force_full_settlement=True,
            display_state=KnifeDisplayState.KILL,
        )

    if candidates and account_has_comp_for_timeline(budget):
        for x in candidates:
            if srt == x:
                state = KnifeDisplayState.COMP_KILL if is_kill else KnifeDisplayState.COMP
                logger.info(
                    "timeline秒数匹配补偿: viewer={} start_remain={} comp_seconds={} kill={}",
                    vid,
                    srt,
                    x,
                    is_kill,
                )
                return TimelineVerdict(
                    force_comp_settlement=True,
                    display_state=state,
                    matched_comp_seconds=x,
                )
        if has_full:
            state = KnifeDisplayState.KILL if is_kill else KnifeDisplayState.FULL
            logger.info(
                "timeline秒数不匹配有余整刀: viewer={} start_remain={} candidates={} -> 整刀",
                vid,
                srt,
                candidates,
            )
            return TimelineVerdict(
                force_full_settlement=True,
                display_state=state,
            )

    if is_timeline_comp_entry(timeline):
        state = _display_from_timeline(timeline, is_kill=is_kill)
        logger.debug(
            "timeline补偿进本兜底(<90): viewer={} start_remain={} battle_time={}",
            vid,
            srt,
            timeline.battle_time,
        )
        return TimelineVerdict(
            force_comp_settlement=True,
            display_state=state,
            matched_comp_seconds=srt if srt > 0 else None,
        )

    if has_full and srt >= COMP_ENTRY_MAX_SECONDS:
        state = KnifeDisplayState.KILL if is_kill else KnifeDisplayState.FULL
        return TimelineVerdict(force_full_settlement=True, display_state=state)

    return TimelineVerdict()


def timeline_record_flag(
    timeline: TimelineInfo, budget: Optional["KnifeBudget"] = None
) -> float:
    """RecordDao.flag：尾刀 1.0 / 补偿 0.5 / 整刀 0.0。"""
    if int(timeline.battle_time or 0) < int(timeline.start_remain_time or 0):
        return 1.0
    if budget is not None:
        verdict = resolve_timeline_verdict(
            timeline, budget, is_kill=False, viewer_id=getattr(budget, "viewer_id", None)
        )
        if verdict.force_comp_settlement:
            return 0.5
        if verdict.force_full_settlement:
            return 0.0
    if is_timeline_comp_entry(timeline):
        return 0.5
    return 0.0


def timeline_knife_display_state(
    timeline: TimelineInfo,
    *,
    is_kill: bool,
    budget: Optional["KnifeBudget"] = None,
) -> KnifeDisplayState:
    """战报四态：timeline + budget 比对优先。"""
    if budget is not None:
        verdict = resolve_timeline_verdict(
            timeline, budget, is_kill=is_kill, viewer_id=getattr(budget, "viewer_id", None)
        )
        if verdict.display_state is not None:
            return verdict.display_state
    return _display_from_timeline(timeline, is_kill=is_kill)


def log_timeline_comp_entry(
    timeline: TimelineInfo,
    *,
    viewer_id: Optional[int] = None,
    log_id: Optional[int] = None,
    context: str = "",
    budget: Optional["KnifeBudget"] = None,
) -> None:
    if budget is not None:
        verdict = resolve_timeline_verdict(
            timeline, budget, is_kill=False, viewer_id=viewer_id
        )
        if verdict.force_comp_settlement or verdict.force_full_settlement:
            logger.info(
                "timeline结算判定{}: viewer={} log_id={} start_remain={} comp_match={} force_full={}",
                f" {context}" if context else "",
                viewer_id,
                log_id,
                timeline.start_remain_time,
                verdict.matched_comp_seconds,
                verdict.force_full_settlement,
            )
            return
    if is_timeline_comp_entry(timeline):
        logger.info(
            "timeline补偿进本{}: viewer={} log_id={} battle_time={} start_remain={}",
            f" {context}" if context else "",
            viewer_id,
            log_id,
            timeline.battle_time,
            timeline.start_remain_time,
        )
