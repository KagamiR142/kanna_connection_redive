from __future__ import annotations

import time
from typing import TYPE_CHECKING, List, Optional

from hoshino.typing import HoshinoBot

from ..basedata import NoticeType
from ..database.dal import pcr_sqla
from ..knife_budget.service import knife_budget_service
from .knife_report_builder import guild_today_knife_aggregate
from .queue_display_service import build_challenge_actors, build_subscribe_actors
from ..util.auto_boss import clan_boss_info
from ..util.boss_assets import ensure_boss_icon
from ..status_dto import (

    BossStatusDTO,
    ClanStatusDTO,
    QueueActor,
    StatusSummaryDTO,
)

if TYPE_CHECKING:
    from .model import ClanBattle

__all__ = [
    "QueueActor",
    "BossStatusDTO",
    "StatusSummaryDTO",
    "ClanStatusDTO",
    "build_clan_status",
    "build_boss_status_dto",
]


async def build_clan_status(
    bot: HoshinoBot, clan_info: ClanBattle
) -> ClanStatusDTO:
    group_id = clan_info.group_id
    max_lap = max((boss.lap_num for boss in clan_info.boss), default=clan_info.lap_num)
    bosses: List[BossStatusDTO] = []

    for boss in clan_info.boss:
        order = boss.order or len(bosses) + 1
        try:
            boss_meta = clan_boss_info.boss_info[order - 1]
            name = boss_meta.name
            unit_id = boss_meta.boss_id
        except (IndexError, AttributeError):
            name = f"Boss{order}"
            unit_id = 0

        if unit_id:
            await ensure_boss_icon(unit_id)

        subscribe = await build_subscribe_actors(bot, group_id, order)
        challenge = await build_challenge_actors(bot, group_id, order)

        bosses.append(
            BossStatusDTO(
                order=order,
                name=name,
                unit_id=unit_id,
                lap=boss.lap_num,
                current_hp=boss.current_hp or 0,
                max_hp=boss.max_hp or 0,
                is_behind=boss.lap_num < max_lap if boss.lap_num else False,
                subscribe=subscribe,
                challenge=challenge,
            )
        )

    viewer_ids = list(getattr(clan_info, "members", {}).keys())
    name_map = getattr(clan_info, "members", {}) or {}
    day_agg = await guild_today_knife_aggregate(
        group_id, int(time.time()), clan_info=clan_info
    )
    comp_entries = await knife_budget_service.group_guild_compensation_entries(
        viewer_ids, name_map
    )

    summary = StatusSummaryDTO(
        full_knives=day_agg.full_knife_count,
        comp_knives=day_agg.comp_knife_count,
        phase=str(clan_info.period or "B"),
        guild_rank=int(getattr(clan_info, "rank", 0) or 0),
        compensation=comp_entries,
    )
    return ClanStatusDTO(summary=summary, bosses=bosses)


async def build_boss_status_dto(
    bot: HoshinoBot,
    group_id: int,
    order: int,
    clan_info: Optional["ClanBattle"] = None,
) -> BossStatusDTO:
    """单 Boss 状态（查x）；有监控镜像时带 HP/周目。"""
    if clan_info and 1 <= order <= len(clan_info.boss):
        boss_snap = clan_info.boss[order - 1]
        max_lap = max(
            (b.lap_num for b in clan_info.boss), default=clan_info.lap_num
        )
        lap = boss_snap.lap_num
        current_hp = boss_snap.current_hp or 0
        max_hp = boss_snap.max_hp or 0
        is_behind = lap < max_lap if lap else False
    else:
        lap = 0
        current_hp = 0
        max_hp = int(clan_boss_info.get_boss_max(1, order) or 1)
        is_behind = False

    try:
        boss_meta = clan_boss_info.boss_info[order - 1]
        name = boss_meta.name
        unit_id = boss_meta.boss_id
    except (IndexError, AttributeError):
        name = f"Boss{order}"
        unit_id = 0

    if unit_id:
        await ensure_boss_icon(unit_id)

    subscribe = await build_subscribe_actors(bot, group_id, order)
    challenge = await build_challenge_actors(bot, group_id, order)
    return BossStatusDTO(
        order=order,
        name=name,
        unit_id=unit_id,
        lap=lap,
        current_hp=current_hp,
        max_hp=max_hp,
        is_behind=is_behind,
        subscribe=subscribe,
        challenge=challenge,
    )
