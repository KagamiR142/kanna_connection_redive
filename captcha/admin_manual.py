"""管理员私聊过码：验证链接仅发给配置中的 admin_qq。"""
from __future__ import annotations

import asyncio
import contextlib

import httpx
from loguru import logger

from ..clanbattle_setting import get_clanbattle_settings
from .session import cancel_active_session, create_session, get_active_session, submit_validate

try:
    from ...multicq_send import private_send
except ImportError:
    from nonebot import get_bot

    async def private_send(qq_id: int, message: str) -> None:
        bot = get_bot()
        await bot.send_private_msg(user_id=int(qq_id), message=message)


async def _listener(user_id: str, session_id: str) -> str:
    url = f"https://captcha.ellye.cn/api/block?userid={user_id}"
    while True:
        session = get_active_session()
        if not session or session.session_id != session_id:
            raise RuntimeError("过码会话已取消")
        if session.cancelled:
            raise RuntimeError("过码会话已取消")
        async with httpx.AsyncClient() as client:
            with contextlib.suppress(httpx.TimeoutException):
                response = await client.get(url, timeout=28)
                if response.status_code == 200:
                    res = response.json()
                    return res["validate"]
                logger.warning(f"手动过码轮询异常: {response.text}")
        await asyncio.sleep(2)


async def admin_manual_captcha(
    challenge: str,
    gt: str,
    user_id: str,
    account_label: str,
    context: str = "",
) -> dict:
    settings = get_clanbattle_settings()
    admin_qq = settings.admin_qq
    wait_sec = settings.captcha_wait_sec

    url = (
        f"https://captcha.ellye.cn/?captcha_type=1&challenge={challenge}"
        f"&gt={gt}&userid={user_id}&gs=1"
    )
    session = create_session(challenge, gt, user_id, account_label, context)

    hint = (
        f"[会战过码] 账号 {account_label}"
        + (f" ({context})" if context else "")
        + f"\n请在 {wait_sec} 秒内完成验证。"
    )
    if settings.captcha_fallback_bdval:
        hint += '\n若页面异常，完成验证后也可私聊发送：bdval <验证码>'

    await private_send(admin_qq, hint)
    await private_send(admin_qq, url)

    listener_task = asyncio.create_task(_listener(user_id, session.session_id))
    wait_task = asyncio.create_task(session.done.wait())

    done, pending = await asyncio.wait(
        {listener_task, wait_task},
        timeout=wait_sec,
        return_when=asyncio.FIRST_COMPLETED,
    )
    for task in pending:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    if session.cancelled:
        raise RuntimeError("过码已取消")

    if session.validate:
        return {
            "challenge": challenge,
            "gt_user_id": user_id,
            "validate": session.validate,
        }

    if listener_task in done and not listener_task.cancelled():
        validate = listener_task.result()
        return {"challenge": challenge, "gt_user_id": user_id, "validate": validate}

    await private_send(admin_qq, "手动过码超时，可私聊发送「重试过码」重新触发登录。")
    raise RuntimeError("手动过码获取结果超时")


def submit_bdval(validate: str) -> bool:
    return submit_validate(validate)


def cancel_active_captcha() -> bool:
    return cancel_active_session() is not None
