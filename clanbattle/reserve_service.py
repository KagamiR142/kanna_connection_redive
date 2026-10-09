"""预约区统一状态：预约态与留言态互斥，预约优先（单管道读写）。"""
from __future__ import annotations

from typing import List, Optional, Set, Tuple

from loguru import logger

from ..basedata import NoticeType
from ..database.dal import pcr_sqla
from ..database.models import NoticeCache

RESERVE_DISPLAY_TYPES = (
    NoticeType.subscribe.value,
    NoticeType.board_message.value,
)


async def freeze_zero_sync_orders(
    group_id: int,
    *,
    extra_orders: Optional[Set[int]] = None,
) -> Set[int]:
    """有进行中申请出刀 / 本 poll 待结算战报的 Boss：账本不向 0 双确认归零。"""
    frozen: Set[int] = set()
    for boss in range(1, 6):
        if await pcr_sqla.get_notice(NoticeType.apply.value, group_id, boss):
            frozen.add(boss)
    if extra_orders:
        frozen |= {int(o) for o in extra_orders if 1 <= int(o) <= 5}
    if frozen:
        logger.debug(
            "ledger 合刀冻结归零: group={} bosses={}",
            group_id,
            sorted(frozen),
        )
    return frozen


# orders_with_pending_damage_history 已迁至 damage_history_watermark（需按 history_id 幂等）


async def get_user_reserve(
    group_id: int, boss: int, user_id: int
) -> Optional[NoticeCache]:
    sub = await pcr_sqla.get_user_subscribe(group_id, boss, user_id)
    if sub:
        return sub
    return await pcr_sqla.get_user_board_message(group_id, boss, user_id)


def reserve_is_board_message(row: NoticeCache) -> bool:
    return int(row.notice_type or 0) == NoticeType.board_message.value


async def list_reserve_for_boss(group_id: int, boss: int) -> List[NoticeCache]:
    """同 Boss 预约+留言；每 user 至多一条（DAL 互斥保证）。"""
    rows: List[NoticeCache] = []
    rows.extend(
        await pcr_sqla.get_notice(NoticeType.subscribe.value, group_id, boss)
    )
    rows.extend(
        await pcr_sqla.get_notice(NoticeType.board_message.value, group_id, boss)
    )
    rows.sort(key=lambda r: (int(r.time or 0), int(r.id or 0)))
    return rows


async def upsert_subscribe(notice: NoticeCache) -> str:
    action = await pcr_sqla.upsert_reserve_subscribe(notice)
    logger.info(
        "预约区 subscribe: group={} user={} boss={} lap={} action={}",
        notice.group_id,
        notice.user_id,
        notice.boss,
        notice.lap,
        action,
    )
    return action


async def upsert_board_message(notice: NoticeCache) -> str:
    action = await pcr_sqla.upsert_reserve_board_message(notice)
    logger.info(
        "预约区 board_message: group={} user={} boss={} action={}",
        notice.group_id,
        notice.user_id,
        notice.boss,
        action,
    )
    return action


async def delete_user_reserve(group_id: int, boss: int, user_id: int) -> None:
    await pcr_sqla.delete_user_reserve(group_id, boss, user_id)
    logger.info(
        "预约区取消: group={} boss={} user={}",
        group_id,
        boss,
        user_id,
    )


async def delete_all_reserve(group_id: int, boss: int) -> int:
    n = await pcr_sqla.delete_all_reserve(group_id, boss)
    logger.info("预约区清空: group={} boss={} n={}", group_id, boss, n)
    return n


async def clear_board_messages_on_boss_kill(group_id: int, boss: int) -> int:
    n = await pcr_sqla.clear_board_messages_for_boss(group_id, boss)
    if n:
        logger.info(
            "留言击杀清除: group={} boss={} n={}",
            group_id,
            boss,
            n,
        )
    return n


async def count_reserve_for_boss(group_id: int, boss: int) -> int:
    return await pcr_sqla.count_reserve_for_boss(group_id, boss)
