"""出刀记录四态：与 SettlementResult / RecordDao 字段映射（全模块单入口）。"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from .classifier import TimelineInfo
from .knife_state import KnifeDisplayState
from .settlement import SettlementResult
from .timeline_knife import timeline_knife_display_state


def semantics_from_settlement(result: SettlementResult) -> Dict[str, Any]:
    """结算结果 → RecordDao 的 knife_state / flag / is_kill（与报刀推送同源）。"""
    state = KnifeDisplayState(int(result.display_state))
    return {
        "knife_state": int(state),
        "flag": float(result.record_flag),
        "is_kill": int(result.record_is_kill),
    }


def provisional_knife_state_from_timeline(
    timeline: TimelineInfo,
    *,
    is_kill: bool,
    budget: Optional[Any] = None,
) -> int:
    """
    battle_log 入库前的占位四态（结算写库后会覆盖）。
    与战报 timeline 展示共用 timeline_knife_display_state。
    """
    return int(
        timeline_knife_display_state(timeline, is_kill=is_kill, budget=budget)
    )


def semantics_locked(row: Any) -> bool:
    """是否已由 damage_history 结算写库（禁止 battle_log merge 覆盖四态）。"""
    from ..database.record_row import knife_semantics_locked

    return knife_semantics_locked(row)


__all__ = [
    "provisional_knife_state_from_timeline",
    "semantics_from_settlement",
    "semantics_locked",
]
