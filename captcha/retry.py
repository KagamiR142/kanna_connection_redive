"""管理员私聊触发重新登录与过码。"""
from __future__ import annotations

from hoshino import Service
from hoshino.typing import CQEvent, HoshinoBot
from loguru import logger

from ..clanbattle_setting import get_clanbattle_settings
from ..login import client_cache
from .admin_manual import cancel_active_captcha, submit_bdval
from .session import get_active_session

sv = Service("会战过码管理", visible=False, enable_on_default=True)


def _is_admin(user_id: int) -> bool:
    return user_id == get_clanbattle_settings().admin_qq


async def force_relogin_all_monitors() -> list[int]:
    """停止所有出刀监控循环，清空登录缓存，等待用户重新开启或自动重启。"""
    from ..clanbattle import clanbattle_info

    affected = []
    for group_id, clan_info in list(clanbattle_info.items()):
        clan_info.loop_num += 1
        affected.append(group_id)
        logger.info(f"[重试过码] 已停止群 {group_id} 的监控循环")
    client_cache.clear()
    return affected


def register_retry_handlers() -> None:
    settings = get_clanbattle_settings()

    @sv.on_fullmatch(*settings.captcha_retry_commands, only_to_me=True)
    async def retry_captcha(bot: HoshinoBot, ev: CQEvent):
        if not _is_admin(ev.user_id):
            await bot.send(ev, "仅管理员可使用此指令")
            return
        cancel_active_captcha()
        groups = await force_relogin_all_monitors()
        if groups:
            await bot.send(
                ev,
                "已取消当前过码并停止以下群的监控循环，请重新发送「出刀监控」：\n"
                + ", ".join(str(g) for g in groups),
            )
        else:
            await bot.send(ev, "已取消当前过码。当前没有运行中的出刀监控，请发送「出刀监控」。")

    @sv.on_prefix("bdval", only_to_me=True)
    async def bdval_private(bot: HoshinoBot, ev: CQEvent):
        if not _is_admin(ev.user_id):
            return
        if not get_clanbattle_settings().captcha_fallback_bdval:
            return
        value = ev.message.extract_plain_text().strip()
        if not value:
            await bot.send(ev, "格式：bdval <验证码>")
            return
        if submit_bdval(value):
            await bot.send(ev, "验证码已提交")
        elif get_active_session():
            await bot.send(ev, "提交失败，请确认过码会话仍有效")
        else:
            await bot.send(ev, "当前没有等待中的过码会话")
