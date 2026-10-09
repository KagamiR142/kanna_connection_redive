"""会战日统计大表（05:00 切日，一行一 viewer_id）。"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

import nonebot
from loguru import logger

from ...clanbattle.detail_reports import format_knife_short, record_to_web_row
from ...clanbattle.account_label import format_viewer_account_label, viewer_to_qq
from ...clanbattle.knife_report_builder import (
    _format_used_bucket_key,
    collect_guild_viewer_names,
)
from ...database.dal import pcr_date, pcr_sqla
from ...knife_budget.service import knife_budget_service
from ...member.display import get_group_nickname


async def list_battle_days(group_id: int) -> List[str]:
    days = await pcr_sqla.get_season_day_timestamps(group_id)
    out: List[str] = []
    for ts in days:
        records = await pcr_sqla.get_day_rcords(ts, group_id)
        if records:
            out.append(pcr_date(ts).strftime("%Y-%m-%d"))
    return out


def _parse_pcr_date(date_str: str) -> int:
    try:
        dt = datetime.strptime(date_str.strip(), "%Y-%m-%d")
    except ValueError as e:
        raise ValueError("日期格式须为 YYYY-MM-DD") from e
    return int(pcr_date(int(dt.timestamp())).timestamp())


async def build_daily_stats(group_id: int, date_str: str) -> List[Dict[str, Any]]:
    day_ts = _parse_pcr_date(date_str)
    records = await pcr_sqla.get_day_rcords(day_ts, group_id)
    bot = None
    try:
        bot = nonebot.get_bot()
    except Exception:
        pass

    names = await collect_guild_viewer_names(group_id, day_ts)
    if not records and not names:
        logger.debug("stats/daily 无数据 group={} date={}", group_id, date_str)
        return []

    grouped: Dict[int, list] = defaultdict(list)
    for r in records:
        grouped[int(r.pcrid)].append(r)
    for rows in grouped.values():
        rows.sort(key=lambda x: x.time)

    viewer_ids = sorted(set(names.keys()) | set(grouped.keys()))
    result: List[Dict[str, Any]] = []
    for pcrid in viewer_ids:
        rows = grouped.get(pcrid, [])
        qq_id = await viewer_to_qq(pcrid)
        sl_used = False
        if qq_id:
            sl_used = await pcr_sqla.check_sl(qq_id, group_id)
        knives_short = [format_knife_short(r) for r in rows[:3]]
        while len(knives_short) < 3:
            knives_short.append("")
        knife_structured = [record_to_web_row(r) for r in rows[:3]]
        used_points = await knife_budget_service.get_used_points(pcrid, day_ts)
        account_label = await format_viewer_account_label(
            bot, group_id, pcrid, rows[0].name if rows else names.get(pcrid, "")
        )
        qq_nickname = ""
        if qq_id and bot:
            qq_nickname = await get_group_nickname(bot, group_id, qq_id)
        result.append(
            {
                "sl": sl_used,
                "qq_id": qq_id,
                "qq_nickname": qq_nickname,
                "account_label": account_label,
                "game_name": rows[0].name if rows else names.get(pcrid, ""),
                "viewer_id": pcrid,
                "used_points": used_points,
                "used_points_label": _format_used_bucket_key(used_points),
                "knife_count": used_points,
                "knife1": knives_short[0],
                "knife2": knives_short[1],
                "knife3": knives_short[2],
                "knives": knife_structured,
                "records": [record_to_web_row(r) for r in rows],
            }
        )
    result.sort(
        key=lambda x: (-x["used_points"], x.get("qq_id") is None, x.get("qq_id") or 0)
    )
    return result
