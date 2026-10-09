"""会战状态图：读预渲染缓存；禁止在指令路径拉 top。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from .status_cache import (
    get_cached_status_png_bytes,
    is_monitor_active,
    render_status_png_sync_fallback,
    wait_cached_status_png,
)

if TYPE_CHECKING:
    from hoshino.typing import HoshinoBot

    from .model import ClanBattle


async def get_group_status_png(bot: HoshinoBot, clan_info: ClanBattle) -> bytes:
    """QQ【状态】/ Web：优先缓存 PNG。"""
    if not is_monitor_active(clan_info):
        raise RuntimeError("未开启出刀监控")

    png = get_cached_status_png_bytes(clan_info)
    if png:
        logger.debug("状态图命中缓存 group={} version={}", clan_info.group_id, clan_info.status_png_version)
        return png

    png = await wait_cached_status_png(clan_info, timeout=0.8)
    if png:
        return png

    logger.info("状态图缓存未就绪，同步渲染 group={}", clan_info.group_id)
    return await render_status_png_sync_fallback(clan_info, "status_command_fallback")
