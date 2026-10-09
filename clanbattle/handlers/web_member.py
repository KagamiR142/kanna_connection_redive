"""Web 公会绑定与面板提示。"""
from __future__ import annotations

from hoshino.typing import CQEvent, HoshinoBot
from loguru import logger

from ..command_match import proxy_rex
from ..permissions import PERM_DENIED, is_ops_admin
from .context import require_group, sender_tag


def register_web_member_handlers(sv) -> None:
    @sv.on_rex(proxy_rex(r"绑定本群公会"))
    async def bind_clan_group_cmd(bot: HoshinoBot, ev: CQEvent):
        if not require_group(ev):
            return
        from ...webui.services.guild_membership_service import bind_user_to_clan_group

        try:
            gname = await bind_user_to_clan_group(
                int(ev.group_id), int(ev.user_id), bot=bot
            )
            await bot.send(
                ev,
                f"绑定本群公会成功（{gname}）。Web 端请使用同一 QQ 登录；"
                "若群内有多台机器人，请以本 bot 的回复为准。",
            )
        except Exception:
            logger.exception("绑定本群公会失败 group={} user={}", ev.group_id, ev.user_id)
            await bot.send(ev, "绑定本群公会失败，请稍后重试或联系会战管理员。")

    @sv.on_prefix("删除本群公会绑定")
    async def delete_clan_group_bind(bot: HoshinoBot, ev: CQEvent):
        if not require_group(ev):
            return
        from ...webui.services.guild_membership_service import unbind_user_from_clan_group

        target_id = int(ev.user_id)
        for seg in ev.message:
            if seg.type == "at" and seg.data.get("qq"):
                if not is_ops_admin(ev):
                    await bot.send(ev, PERM_DENIED)
                    return
                target_id = int(seg.data["qq"])
                break
        try:
            await unbind_user_from_clan_group(int(ev.group_id), target_id)
            await bot.send(ev, "删除本群公会绑定成功")
        except Exception:
            logger.exception(
                "删除本群公会绑定失败 group={} target={}", ev.group_id, target_id
            )
            await bot.send(ev, "删除本群公会绑定失败，请稍后重试。")

    @sv.on_rex(r"^\s*(?:面板|网页端登录)\s*$")
    async def panel_link_deprecated(bot: HoshinoBot, ev: CQEvent):
        await bot.send(
            ev,
            "面板临时链接已停用。请私聊发送【注册】获取 Web 密码，"
            "使用 QQ 号与密码登录会战管理平台。"
            f" {await sender_tag(bot, ev)}",
        )
