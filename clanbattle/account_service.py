"""用户绑定账号解析（账号编号 1–30）。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from loguru import logger

from ..database.dal import pcr_sqla
from ..knife_budget.service import knife_budget_service
from .member_identity import display_slot, resolve_member_display_name


@dataclass
class BoundAccount:
    slot: int
    viewer_id: int
    account_id: int
    name: str


async def list_member_bound_accounts(
    user_id: int, *, group_id: Optional[int] = None
) -> List[BoundAccount]:
    """成员自助绑定（Web user_account），不含监控 Account 旧表。"""
    rows = await pcr_sqla.query_user_accounts(user_id)
    accounts: List[BoundAccount] = []
    for row in rows:
        if not row.viewer_id:
            continue
        vid = int(row.viewer_id)
        slot = display_slot(row.sort_order)
        name = await resolve_member_display_name(
            vid, group_id=group_id, user_id=user_id
        )
        accounts.append(
            BoundAccount(
                slot=slot,
                viewer_id=vid,
                account_id=int(row.account_id or 0),
                name=name,
            )
        )
    return accounts


async def list_bound_accounts(
    user_id: int, *, group_id: Optional[int] = None
) -> List[BoundAccount]:
    """兼容旧调用：等同 list_member_bound_accounts。"""
    return await list_member_bound_accounts(user_id, group_id=group_id)


async def viewer_to_slot(user_id: int, viewer_id: int) -> int:
    for row in await pcr_sqla.query_user_accounts(user_id):
        if int(row.viewer_id or 0) == int(viewer_id):
            return display_slot(row.sort_order)
    return 0


async def _has_knife_budget(viewer_id: int) -> bool:
    summary = await knife_budget_service.remaining_summary(viewer_id)
    return summary["points"] > 0


async def pick_member_account(
    user_id: int, slot: Optional[int] = None, *, group_id: Optional[int] = None
) -> Optional[BoundAccount]:
    accounts = await list_member_bound_accounts(user_id, group_id=group_id)
    if not accounts:
        logger.debug("pick_member_account: user_id={} 无成员绑定", user_id)
        return None
    if slot is not None and 1 <= slot <= 30:
        for acc in accounts:
            if acc.slot == slot:
                logger.debug(
                    "pick_member_account: user_id={} slot={} viewer_id={} name={}",
                    user_id,
                    slot,
                    acc.viewer_id,
                    acc.name,
                )
                return acc
        logger.debug(
            "pick_member_account: user_id={} slot={} 无效", user_id, slot
        )
    for acc in accounts:
        if await _has_knife_budget(acc.viewer_id):
            logger.debug(
                "pick_member_account: user_id={} slot={} viewer_id={} name={}",
                user_id,
                acc.slot,
                acc.viewer_id,
                acc.name,
            )
            return acc
    logger.debug(
        "pick_member_account: user_id={} 点数耗尽 slot=1 viewer_id={} name={}",
        user_id,
        accounts[0].viewer_id,
        accounts[0].name,
    )
    return accounts[0]


async def pick_account(
    user_id: int, slot: Optional[int] = None, *, group_id: Optional[int] = None
) -> Optional[BoundAccount]:
    """指令/报刀用成员绑定；监控槽位请走 login 模块。"""
    return await pick_member_account(user_id, slot, group_id=group_id)


async def user_all_knife_points_exhausted(user_id: int) -> bool:
    """名下所有绑定账号今日点数均已用尽；无绑定账号时返回 False。"""
    accounts = await list_member_bound_accounts(user_id)
    if not accounts:
        return False
    for acc in accounts:
        summary = await knife_budget_service.remaining_summary(acc.viewer_id)
        if float(summary.get("points") or 0) > 0:
            return False
    logger.debug("user_all_knife_points_exhausted: user_id={}", user_id)
    return True
