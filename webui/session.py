"""Web 会话与主循环桥接（uvicorn 线程 ↔ nonebot 主循环）。"""
from __future__ import annotations

import asyncio
import time

from fastapi import Cookie, HTTPException, status

from ..database.dal import pcr_sqla
from ..database.models import CookieCache

main_event_loop: asyncio.AbstractEventLoop = None


async def call_in_main_loop(coro, timeout: float = 90):
    """把涉及游戏 client / OneBot API 的协程投递回 nonebot 主循环执行"""
    if main_event_loop is None or main_event_loop.is_closed():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "机器人主循环尚未就绪，请稍后再试"
        )
    future = asyncio.run_coroutine_threadsafe(coro, main_event_loop)
    try:
        return await asyncio.wrap_future(future)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"游戏接口调用失败：{e}")


async def verify_cookie(token: str = Cookie(None)) -> CookieCache:
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "请先登录")
    if cookie := await pcr_sqla.web_query_cookie(token):
        if time.time() - cookie.time < 3600 * 7 * 24:
            return cookie
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "登录过期")
