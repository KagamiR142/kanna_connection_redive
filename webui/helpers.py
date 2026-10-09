"""Web API 路由共用辅助函数。"""
from __future__ import annotations

from typing import Optional

from ..database.dal import Account, RefreshAccount, pcr_sqla
from ..clanbattle.base import DEFAULT_RANK_LINES
from .web_model import GroupAccountInfo, RankLine, RankLineResponse


def rank_line_response(
    data: dict,
    cached: bool,
    monitor_running: bool,
    updated_at: int,
    stale: bool = False,
) -> RankLineResponse:
    """把 query_rank_lines 的结果（或缓存里还原出来的同一结构）转成接口响应"""
    return RankLineResponse(
        clan_battle_id=data["clan_battle_id"],
        lines=[RankLine(**line) if line else None for line in data["lines"]],
        my=RankLine(**data["my"]) if data.get("my") else None,
        default_ranks=list(DEFAULT_RANK_LINES),
        cached=cached,
        stale=stale,
        monitor_running=monitor_running,
        updated_at=updated_at,
    )


def account_info(account: Optional[Account]) -> GroupAccountInfo:
    """把 Account 行转成前端要的账号信息（现在一个 QQ 只有一个全局号）"""
    if account is None:
        return GroupAccountInfo()
    return GroupAccountInfo(
        bound=True,
        account_id=account.id,
        name=account.name or "",
        platform=int(account.platform),
        viewer_id=account.viewer_id,
    )


async def login_new_account(
    account: Account, refresh: Optional[RefreshAccount] = None
) -> Optional[Account]:
    """登录校验 + 落库：成功返回填好昵称/viewer_id 的 Account，登录不上返回 None"""
    from ..client import check_client
    from ..login import query

    client = await query(account, True)
    load_index = await check_client(client)
    if not load_index:
        return None
    account.viewer_id = load_index.user_info.viewer_id
    account.name = load_index.user_info.user_name
    await pcr_sqla.add_account(
        account.user_id,
        account.dict(exclude_none=True),
        group_id=int(account.group_id or 0),
    )
    if refresh is not None:
        await pcr_sqla.add_refresh(refresh)
    return account
