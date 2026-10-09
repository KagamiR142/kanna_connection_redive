"""自动报刀 2 — Service 注册、启动任务与 cron。"""
from __future__ import annotations

import nonebot
from hoshino import Service
from loguru import logger

from ..database.dal import pcr_sqla, RecordDao
from ..util.boss_metadata_service import refresh_clan_boss_metadata
from .handlers import register_handlers
from .rbac_commands import register_role_commands
from .registry import clanbattle_info, clanbattle_pool, notice_update_time
from .user_help import HELP_TEXT as help_text

__all__ = [
    "sv",
    "clanbattle_info",
    "clanbattle_pool",
    "notice_update_time",
]

sv = Service(
    name="自动报刀2",
    visible=True,
    enable_on_default=True,
    help_=help_text,
)

register_role_commands(sv)
register_handlers(sv)


@nonebot.on_startup
async def start_loop_handle():
    clanbattle_pool.init()
    await pcr_sqla.ensure_schema_upgrades()
    try:
        summary = await refresh_clan_boss_metadata("startup")
        if not summary.get("ok"):
            logger.warning("启动时 Boss 元数据刷新未成功: {}", summary.get("reason"))
    except Exception:
        logger.exception("启动时 Boss 元数据刷新异常")


@sv.scheduled_job("cron", hour=5, minute=0)
async def daily_challenge_reset_job():
    from .daily_reset_service import run_daily_challenge_area_reset

    try:
        await run_daily_challenge_area_reset(source="cron_5am")
    except Exception:
        logger.exception("会战日 5:00 挑战区清空失败")


@sv.scheduled_job("cron", hour="1")
async def refresh_boss_info():
    try:
        await refresh_clan_boss_metadata("cron")
    except Exception as e:
        logger.warning("定时 Boss 元数据刷新异常：{}", e)


@nonebot.on_startup
@sv.scheduled_job("cron", hour="8")
async def refresh_record():
    await pcr_sqla.refresh(RecordDao, 30)
