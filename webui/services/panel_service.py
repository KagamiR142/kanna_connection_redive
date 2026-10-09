"""会战面板 DTO（复用 status_builder，避免 api 层重复拼装）。"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import nonebot
from loguru import logger

from ...basedata import NoticeType
from ...clanbattle import clanbattle_info
from ...clanbattle.status_builder import build_clan_status
from ...database.dal import pcr_sqla
from ...util.auto_boss import clan_boss_info
from .notice_enrich_service import enrich_notice_list


async def build_panel_payload(group_id: int) -> Dict[str, Any]:
    boss_meta = clan_boss_info.boss_info
    payload: Dict[str, Any] = {
        "group_id": group_id,
        "clan_name": "",
        "stage": "",
        "rank": 0,
        "state": "关闭",
        "day_num": await pcr_sqla.get_clan_day(group_id),
        "bosses": [],
        "queues": {},
    }
    clan_info = clanbattle_info.get(group_id)
    now = int(time.time())
    if clan_info:
        payload["clan_name"] = clan_info.clan_name
        payload["stage"] = f"{clan_info.period}面{clan_info.lap_num}周目"
        payload["rank"] = clan_info.rank
        if clan_info.loop_check:
            payload["state"] = "开启" + (
                "(高占用)" if now - clan_info.loop_check > 30 else ""
            )
        max_lap = max((b.lap_num for b in clan_info.boss), default=0)
        status_dto = None
        try:
            bot = nonebot.get_bot()
            status_dto = await build_clan_status(bot, clan_info)
        except Exception as e:
            logger.warning("build_clan_status 失败 group={}: {}", group_id, e)

        bosses_out: List[Dict[str, Any]] = []
        for i, boss in enumerate(clan_info.boss):
            order = i + 1
            challenge_labels: List[str] = []
            unknown_labels: List[str] = []
            if status_dto and i < len(status_dto.bosses):
                bdto = status_dto.bosses[i]
                for actor in bdto.challenge:
                    if actor.is_unknown:
                        unknown_labels.append(actor.label)
                    else:
                        challenge_labels.append(actor.label)
            bosses_out.append(
                {
                    "order": order,
                    "name": boss_meta[i].name if i < len(boss_meta) else f"Boss{order}",
                    "id": boss_meta[i].boss_id if i < len(boss_meta) else 0,
                    "lap": boss.lap_num,
                    "current_hp": boss.current_hp,
                    "max_hp": boss.max_hp,
                    "fighter": boss.fighter_num,
                    "is_behind": boss.lap_num < max_lap if max_lap else False,
                    "challenge": challenge_labels,
                    "unknown": unknown_labels,
                }
            )
        for boss in bosses_out:
            o = boss["order"]
            boss["subscribe"] = await pcr_sqla.count_reserve_for_boss(
                group_id, o
            )
            boss["apply"] = len(
                await pcr_sqla.get_notice(NoticeType.apply.value, group_id, o)
            )
            boss["tree"] = len(
                await pcr_sqla.get_notice(NoticeType.tree.value, group_id, o)
            )
        payload["bosses"] = bosses_out
        try:
            from ..util import build_day_damage_rank

            rows, _, _ = build_day_damage_rank(
                await pcr_sqla.get_day_rcords(int(time.time()), group_id),
                limit=10,
            )
            payload["top_damage"] = rows
        except Exception as e:
            logger.debug("面板 Top 伤害跳过 group={}: {}", group_id, e)
            payload["top_damage"] = []

    for boss in range(1, 6):
        from ...clanbattle.reserve_service import list_reserve_for_boss

        sub = await list_reserve_for_boss(group_id, boss)
        app = await pcr_sqla.get_notice(NoticeType.apply.value, group_id, boss)
        tree = await pcr_sqla.get_notice(NoticeType.tree.value, group_id, boss)
        payload["queues"][str(boss)] = {
            "subscribe": await enrich_notice_list(group_id, sub),
            "apply": await enrich_notice_list(group_id, app),
            "tree": await enrich_notice_list(group_id, tree),
        }
    payload["refresh_cd_sec"] = 3
    return payload
