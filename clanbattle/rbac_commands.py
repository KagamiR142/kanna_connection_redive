"""超级管理员私聊：任命 / 撤销 / 列表 会战管理员。"""
from __future__ import annotations

import re

from hoshino.typing import CQEvent, HoshinoBot
from loguru import logger

from ..rbac import (
    appoint_delegated_admin,
    is_super_admin,
    list_delegated_admins,
    revoke_delegated_admin,
    super_admin_qq,
)


def register_role_commands(sv) -> None:
    @sv.on_rex(r"^\s*任命管理员\s*(\d+)\s*$")
    async def appoint_admin_cmd(bot: HoshinoBot, ev: CQEvent):
        if not ev.is_private():
            await bot.send(ev, "请私聊机器人发送【任命管理员 QQ号】")
            return
        if not is_super_admin(ev.user_id):
            await bot.send(ev, "仅超级管理员可任命管理员")
            return
        m = re.match(r"^\s*任命管理员\s*(\d+)\s*$", ev.message.extract_plain_text())
        if not m:
            return
        target = int(m.group(1))
        try:
            await appoint_delegated_admin(target, appointed_by=int(ev.user_id))
            await bot.send(ev, f"已任命管理员：{target}")
        except (ValueError, PermissionError) as e:
            await bot.send(ev, str(e))

    @sv.on_rex(r"^\s*撤销管理员\s*(\d+)\s*$")
    async def revoke_admin_cmd(bot: HoshinoBot, ev: CQEvent):
        if not ev.is_private():
            await bot.send(ev, "请私聊机器人发送【撤销管理员 QQ号】")
            return
        if not is_super_admin(ev.user_id):
            await bot.send(ev, "仅超级管理员可撤销管理员")
            return
        m = re.match(r"^\s*撤销管理员\s*(\d+)\s*$", ev.message.extract_plain_text())
        if not m:
            return
        target = int(m.group(1))
        try:
            await revoke_delegated_admin(target, revoked_by=int(ev.user_id))
            await bot.send(ev, f"已撤销管理员：{target}")
        except (ValueError, PermissionError) as e:
            await bot.send(ev, str(e))

    @sv.on_fullmatch("管理员列表", only_to_me=True)
    async def list_admin_cmd(bot: HoshinoBot, ev: CQEvent):
        if not ev.is_private():
            return
        if not is_super_admin(ev.user_id):
            await bot.send(ev, "仅超级管理员可查看完整管理员列表")
            return
        rows = await list_delegated_admins()
        super_q = super_admin_qq()
        lines = [f"超级管理员：{super_q}"]
        if rows:
            lines.append("委派管理员（≤5）：")
            for r in rows:
                lines.append(f"  {r['qq_id']}（任命于 {r['appointed_at']}）")
        else:
            lines.append("委派管理员：无")
        await bot.send(ev, "\n".join(lines))
        logger.debug("管理员列表查询 by={}", ev.user_id)
