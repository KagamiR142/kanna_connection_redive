"""自动报刀专用装饰器。"""
from __future__ import annotations

import functools

from hoshino.typing import CQEvent, HoshinoBot

from ..database.dal import pcr_sqla
from ..util.tools import get_qid, other_allow
from .permissions import PERM_DENIED, is_ops_admin
from .text_util import sender_placeholder


def require_ops_admin(func):
    """群聊指令：仅管理员及以上。"""

    @functools.wraps(func)
    async def wrapper(bot: HoshinoBot, ev: CQEvent, *arg, **kwarg):
        if not is_ops_admin(ev):
            await bot.send(ev, PERM_DENIED)
            return
        return await func(bot, ev, *arg, **kwarg)

    return wrapper


def check_monitor_account(slot: int = 1):
    """出刀监控：按槽位取监控账号。"""

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(bot: HoshinoBot, ev: CQEvent, *arg, **kwarg):
            qq_id, is_other = get_qid(ev)
            account = await pcr_sqla.query_monitor_account(qq_id, slot)
            if not account:
                try:
                    member = await bot.get_group_member_info(
                        group_id=ev.group_id, user_id=ev.user_id
                    )
                    tag = sender_placeholder(
                        ev.user_id, member.get("card", ""), member.get("nickname", "")
                    )
                except Exception:
                    tag = sender_placeholder(ev.user_id)
                await bot.send(
                    ev,
                    f"{tag} 无可用出刀监控账号，请添加机器人好友并私聊发送【绑定账号帮助】并配置监控账号",
                )
                return
            if is_other and not other_allow(ev, account.allow_others):
                await bot.send(ev, "权限不足，请发送【成员管理帮助】")
                return
            return await func(
                bot,
                ev,
                *arg,
                account=account,
                qq_id=qq_id,
                monitor_slot=slot,
                **kwarg,
            )

        return wrapper

    return decorator
