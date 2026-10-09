"""查[1-5] 单 Boss PNG。"""
from __future__ import annotations

import io
from typing import TYPE_CHECKING

from loguru import logger

from ..status_image import render_boss_query_image
from .status_builder import build_boss_status_dto

if TYPE_CHECKING:
    from hoshino.typing import HoshinoBot

    from .model import ClanBattle


async def get_boss_query_png(
    bot: HoshinoBot,
    group_id: int,
    boss_order: int,
    clan_info: "ClanBattle | None" = None,
) -> bytes:
    boss = await build_boss_status_dto(
        bot, group_id, boss_order, clan_info=clan_info
    )
    img = render_boss_query_image(boss)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    logger.info(
        "查{} PNG: group={} name={} lap={} hp={}/{}",
        boss_order,
        group_id,
        boss.name,
        boss.lap,
        boss.current_hp,
        boss.max_hp,
    )
    return buf.getvalue()
