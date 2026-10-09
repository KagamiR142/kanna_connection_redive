"""damage_history 水位线：同秒合刀条目须按 history_id 幂等，不能仅用 create_time 截断。"""
from __future__ import annotations

from typing import Any, Iterable, List, Sequence, Set

from ..database.dal import pcr_sqla


def iter_histories_at_or_after_watermark(
    damage_history: Sequence[Any],
    latest_time: int,
) -> Iterable[Any]:
    """damage_history 为 API 倒序（新→旧）；遇到严格更旧的时间戳则停止。"""
    watermark = int(latest_time or 0)
    for history in damage_history or []:
        create_time = int(getattr(history, "create_time", None) or 0)
        if create_time < watermark:
            break
        yield history


def collect_damage_histories_to_process(
    damage_history: Sequence[Any],
    latest_time: int,
) -> List[Any]:
    """返回本 poll 待尝试结算的 history，按时间从旧到新。"""
    batch = list(iter_histories_at_or_after_watermark(damage_history, latest_time))
    batch.reverse()
    return batch


async def is_history_settlement_pending(
    group_id: int,
    history,
) -> bool:
    log_id = int(getattr(history, "history_id", None) or 0)
    if log_id <= 0:
        return True
    locked = await pcr_sqla.is_record_settlement_locked(group_id, log_id)
    return not locked


async def has_unsettled_damage_history(
    group_id: int,
    damage_history: Sequence[Any],
    latest_time: int,
) -> bool:
    for history in iter_histories_at_or_after_watermark(damage_history, latest_time):
        if await is_history_settlement_pending(group_id, history):
            return True
    return False


async def list_unsettled_damage_histories(
    group_id: int,
    damage_history: Sequence[Any],
    latest_time: int,
) -> List[Any]:
    pending: List[Any] = []
    for history in iter_histories_at_or_after_watermark(damage_history, latest_time):
        if await is_history_settlement_pending(group_id, history):
            pending.append(history)
    return pending


async def orders_with_pending_damage_history(
    group_id: int,
    damage_history: Sequence[Any],
    latest_time: int,
) -> Set[int]:
    """本 poll 尚未结算的 damage_history 涉及的 Boss 槽位（含同秒晚到条目）。"""
    orders: Set[int] = set()
    for history in iter_histories_at_or_after_watermark(damage_history, latest_time):
        if not await is_history_settlement_pending(group_id, history):
            continue
        order = int(getattr(history, "order_num", None) or 0)
        if 1 <= order <= 5:
            orders.add(order)
    return orders


def format_history_batch_for_log(histories: Sequence[Any]) -> str:
    parts = []
    for history in histories:
        parts.append(
            "log_id={} viewer={} t={}".format(
                int(getattr(history, "history_id", None) or 0),
                int(getattr(history, "viewer_id", None) or 0),
                int(getattr(history, "create_time", None) or 0),
            )
        )
    return "[" + ", ".join(parts) + "]"


__all__ = [
    "collect_damage_histories_to_process",
    "format_history_batch_for_log",
    "has_unsettled_damage_history",
    "is_history_settlement_pending",
    "iter_histories_at_or_after_watermark",
    "list_unsettled_damage_histories",
    "orders_with_pending_damage_history",
]
