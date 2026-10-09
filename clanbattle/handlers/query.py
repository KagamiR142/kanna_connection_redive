"""状态 / 合刀 / 查 Boss 指令。"""
from __future__ import annotations

import re

from hoshino.typing import CQEvent, HoshinoBot, MessageSegment
from loguru import logger

from ..boss_query_service import get_boss_query_png
from ..command_match import REX_QUERY_BOSS, proxy_rex, strict_rex
from ..merge_knife_parser import MergeKnifeCompSecondsRangeError, parse_merge_knife
from ..merge_knife_service import (
    MERGE_KNIFE_COMP_SECONDS_RANGE_HELP,
    MERGE_KNIFE_FORMAT_HELP,
    build_merge_knife_reply,
)
from ..registry import clanbattle_info
from .context import extract_plain, require_group, send_report_payload, sender_tag


def register_query_handlers(sv) -> None:
    @sv.on_rex(strict_rex(r"状态"))
    async def daostate(bot: HoshinoBot, ev: CQEvent):
        if not require_group(ev):
            return
        group_id = ev.group_id
        if group_id not in clanbattle_info or not clanbattle_info[group_id].loop_check:
            await bot.send(ev, "未查询到本群当前进度，请开启出刀监控")
            return
        clan_info = clanbattle_info[group_id]
        try:
            from io import BytesIO

            from hoshino.util import pic2b64
            from PIL import Image

            from ..status_service import get_group_status_png

            png = await get_group_status_png(bot, clan_info)
            img = Image.open(BytesIO(png))
            await bot.send(ev, MessageSegment.image(pic2b64(img)))
            logger.info("状态图已发送 group={} bytes={}", group_id, len(png))
        except Exception as e:
            logger.warning("状态图失败，回退文本: group={} err={}", group_id, e)
            await bot.send(ev, clan_info.general_boss())

    @sv.on_rex(proxy_rex(r"(?:合刀|cal).+"))
    async def merge_knife_cmd(bot: HoshinoBot, ev: CQEvent):
        if not require_group(ev):
            return
        plain = ev.message.extract_plain_text().strip()
        sender = await sender_tag(bot, ev)
        try:
            parsed = parse_merge_knife(plain)
        except MergeKnifeCompSecondsRangeError:
            logger.debug("合刀: group={} 秒数越界 plain={}", ev.group_id, plain)
            await bot.send(
                ev,
                f"{sender} 指令格式错误\n{MERGE_KNIFE_COMP_SECONDS_RANGE_HELP}",
            )
            return
        if not parsed:
            await bot.send(ev, f"{sender} 指令格式错误\n{MERGE_KNIFE_FORMAT_HELP}")
            return
        logger.debug("合刀: group={} mode={}", ev.group_id, type(parsed).__name__)
        await bot.send(ev, build_merge_knife_reply(parsed))

    @sv.on_rex(strict_rex(REX_QUERY_BOSS))
    async def boss_query(bot: HoshinoBot, ev: CQEvent):
        if not require_group(ev):
            return
        body = extract_plain(ev)
        m = re.search(r"查\s*([1-5])", body)
        if not m:
            return
        order = int(m.group(1))
        clan_info = clanbattle_info.get(ev.group_id)
        try:
            png = await get_boss_query_png(bot, ev.group_id, order, clan_info)
        except Exception:
            logger.exception("查{} 渲染失败 group={}", order, ev.group_id)
            await bot.send(ev, f"查{order} 状态图生成失败 {await sender_tag(bot, ev)}")
            return
        await send_report_payload(bot, ev, png)
