"""指令上下文：代发用户与账号解析。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Set

from hoshino.typing import CQEvent, HoshinoBot
from loguru import logger

from .account_service import BoundAccount, pick_account
from ..util.message_sanitize import safe_plain
from .text_util import strip_trailing_cq_at

PROXY_COMMANDS: Set[str] = {
    "subscribe",
    "cancel_subscribe",
    "apply",
    "cancel_apply",
    "tree",
    "sl",
    "sl_query",
    "drop",
    "drop_comp",
    "today_report",
    "season_report",
}


@dataclass
class CommandContext:
    operator_id: int
    target_user_id: int
    proxy_applied: bool
    plain: str
    account: Optional[BoundAccount] = None


async def build_context(
    bot: HoshinoBot,
    ev: CQEvent,
    *,
    command_key: str,
    allow_proxy: bool = True,
    account_slot: Optional[int] = None,
) -> CommandContext:
    plain, proxy_qq = strip_trailing_cq_at(ev.message)
    plain = safe_plain(plain)
    operator_id = ev.user_id
    target_user_id = operator_id
    proxy_applied = False

    if allow_proxy and command_key in PROXY_COMMANDS and proxy_qq:
        if await _member_in_group(bot, ev.group_id, proxy_qq):
            target_user_id = proxy_qq
            proxy_applied = True
            logger.info(
                "代发: operator={} target={} cmd={}",
                operator_id,
                target_user_id,
                command_key,
            )
        else:
            logger.warning(
                "代发失败: proxy_qq={} 不在群 {}，按真实发送者执行",
                proxy_qq,
                ev.group_id,
            )

    group_id = int(ev.group_id) if getattr(ev, "group_id", None) else None
    account = await pick_account(
        target_user_id, account_slot, group_id=group_id
    )
    return CommandContext(
        operator_id=operator_id,
        target_user_id=target_user_id,
        proxy_applied=proxy_applied,
        plain=plain,
        account=account,
    )


async def _member_in_group(bot: HoshinoBot, group_id: int, user_id: int) -> bool:
    try:
        await bot.get_group_member_info(group_id=group_id, user_id=user_id)
        return True
    except Exception:
        return False
