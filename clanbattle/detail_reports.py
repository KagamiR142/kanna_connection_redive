"""出刀明细与战报（PNG；QQ / Web 共用 builder）。"""
from __future__ import annotations

from typing import Dict, List, Optional, Union

from loguru import logger

from ..database.models import RecordDao
from ..knife_budget.knife_state import (
    display_label,
    knife_state_from_record,
)
from .knife_report_builder import (
    _group_records_by_pcrid,
    build_guild_knife_count_report_dto,
    build_user_knife_report_dto,
)
from .knife_report_image import render_report_from_dto
from .boss_lap_records_service import build_boss_lap_records_dto
from .boss_lap_report_image import render_boss_lap_records_png


def record_to_web_row(record: RecordDao) -> dict:
    """Web 个人/统计页共用的出刀行 DTO。"""
    state = knife_state_from_record(record)
    return {
        "time": record.time,
        "lap": record.lap,
        "boss": record.boss,
        "damage": record.damage,
        "knife_type": display_label(state),
        "knife_state": int(state),
        "is_kill": bool(getattr(record, "is_kill", 0)),
        "flag": record.flag,
    }


def format_knife_short(record: RecordDao) -> str:
    dmg = int(record.damage or 0)
    dmg_text = f"{round(dmg / 10000)}w" if dmg >= 10000 else str(dmg)
    return f"{record.lap}-{record.boss} {dmg_text}"


async def format_today_user_detail(
    group_id: int,
    user_id: int,
    *,
    slot_filter: Optional[int] = None,
    bot=None,
) -> Union[bytes, str]:
    dto = await build_user_knife_report_dto(
        group_id,
        user_id,
        mode="today",
        slot_filter=slot_filter,
        bot=bot,
    )
    if isinstance(dto, str):
        return dto
    logger.info(
        "今日战报(名下): group={} user={} sections={}",
        group_id,
        user_id,
        len(dto.sections),
    )
    return render_report_from_dto(dto)


async def format_season_user_detail(
    group_id: int,
    user_id: int,
    *,
    slot_filter: Optional[int] = None,
    bot=None,
) -> Union[bytes, str]:
    dto = await build_user_knife_report_dto(
        group_id,
        user_id,
        mode="season",
        slot_filter=slot_filter,
        bot=bot,
    )
    if isinstance(dto, str):
        return dto
    logger.info(
        "当期战报(名下): group={} user={} sections={}",
        group_id,
        user_id,
        len(dto.sections),
    )
    return render_report_from_dto(dto)


async def format_boss_lap_records(
    group_id: int,
    boss: int,
    bot=None,
    *,
    clan_info=None,
    lap: Optional[int] = None,
    all_laps: bool = False,
    day_token: Optional[str] = None,
) -> Union[bytes, str]:
    dto = await build_boss_lap_records_dto(
        group_id,
        boss,
        lap or 0,
        bot,
        clan_info=clan_info,
        all_laps=all_laps,
        day_token=day_token,
    )
    if isinstance(dto, str):
        return dto
    return render_boss_lap_records_png(dto)


async def format_today_guild_detail(
    group_id: int,
    bot=None,
    *,
    clan_info=None,
    pcrid_qq_map: Optional[Dict[int, str]] = None,
) -> Union[bytes, str]:
    dto = await build_guild_knife_count_report_dto(
        group_id, bot, mode="today", clan_info=clan_info
    )
    if isinstance(dto, str):
        return dto
    logger.info(
        "今日出刀(公会): group={} days={}",
        group_id,
        len(dto.day_sections),
    )
    return render_report_from_dto(dto)


async def format_season_guild_detail(
    group_id: int,
    bot=None,
    *,
    clan_info=None,
    pcrid_qq_map: Optional[Dict[int, str]] = None,
) -> Union[bytes, str]:
    dto = await build_guild_knife_count_report_dto(
        group_id, bot, mode="season", clan_info=clan_info
    )
    if isinstance(dto, str):
        return dto
    logger.info(
        "当期出刀(公会): group={} days={}",
        group_id,
        len(dto.day_sections),
    )
    return render_report_from_dto(dto)
