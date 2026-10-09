"""合刀线提醒开关与管理员重算。"""
from __future__ import annotations

import re

from hoshino.typing import CQEvent, HoshinoBot
from loguru import logger

from ..command_match import strict_rex
from ..merge_line.service import (
    admin_recompute_all_merge_lines,
    admin_recompute_merge_line,
    set_reminder_enabled,
)
from ..permissions import PERM_DENIED, is_ops_admin
from .context import extract_plain, require_group, sender_tag


def register_merge_line_handlers(sv) -> None:
    @sv.on_rex(strict_rex(r"开启合刀线提醒"))
    async def enable_merge_line_reminder(bot: HoshinoBot, ev: CQEvent):
        if not require_group(ev):
            return
        if not is_ops_admin(ev):
            await bot.send(ev, PERM_DENIED)
            return
        await set_reminder_enabled(ev.group_id, True)
        await bot.send(
            ev, f"{await sender_tag(bot, ev)} 已开启合刀线提醒"
        )
        logger.info("开启合刀线提醒 group={} by={}", ev.group_id, ev.user_id)

    @sv.on_rex(strict_rex(r"关闭合刀线提醒"))
    async def disable_merge_line_reminder(bot: HoshinoBot, ev: CQEvent):
        if not require_group(ev):
            return
        if not is_ops_admin(ev):
            await bot.send(ev, PERM_DENIED)
            return
        await set_reminder_enabled(ev.group_id, False)
        await bot.send(
            ev, f"{await sender_tag(bot, ev)} 已关闭合刀线提醒"
        )
        logger.info("关闭合刀线提醒 group={} by={}", ev.group_id, ev.user_id)

    @sv.on_rex(strict_rex(r"重新计算合刀线\s*([1-5aA])"))
    async def recompute_merge_line(bot: HoshinoBot, ev: CQEvent):
        if not require_group(ev):
            return
        if not is_ops_admin(ev):
            await bot.send(ev, PERM_DENIED)
            return
        plain = extract_plain(ev)
        m = re.search(r"重新计算合刀线\s*([1-5aA])", plain)
        if not m:
            return
        token = m.group(1)
        sender = await sender_tag(bot, ev)
        if token.lower() == "a":
            ok, msg = await admin_recompute_all_merge_lines(ev.group_id)
        else:
            ok, msg = await admin_recompute_merge_line(ev.group_id, int(token))
        await bot.send(ev, f"{sender}\n{msg}" if "\n" in msg else f"{sender} {msg}")
