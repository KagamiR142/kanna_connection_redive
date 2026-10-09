"""状态图展示指纹：用于判断是否需要重绘 PNG（与 build_clan_status 输入对齐）。"""
from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

from ..basedata import NoticeType
from ..database.dal import pcr_sqla
import time

from ..knife_budget.service import knife_budget_service
from ..status_dto import compensation_entry_fingerprint_dict
from .knife_report_builder import guild_today_knife_aggregate
from .queue_display_service import (
    build_challenge_actors,
    build_subscribe_actors,
    queue_actor_fingerprint,
)

if TYPE_CHECKING:
    from hoshino.typing import HoshinoBot

    from .model import ClanBattle


async def compute_status_fingerprint(
    clan_info: "ClanBattle", bot: "HoshinoBot | None" = None
) -> str:
    group_id = clan_info.group_id
    bosses = [
        {
            "order": b.order or i + 1,
            "lap": b.lap_num,
            "hp": b.current_hp,
            "max_hp": b.max_hp,
            "fighter": b.fighter_num,
        }
        for i, b in enumerate(clan_info.boss)
    ]
    queues = []
    for order in range(1, 6):
        state = await pcr_sqla.get_challenge_state(group_id, order)
        if bot:
            sub_actors = await build_subscribe_actors(bot, group_id, order)
            ch_actors = await build_challenge_actors(bot, group_id, order)
            queues.append(
                {
                    "order": order,
                    "enter_signal": state.enter_signal,
                    "subscribe": [queue_actor_fingerprint(a) for a in sub_actors],
                    "challenge": [queue_actor_fingerprint(a) for a in ch_actors],
                }
            )
        else:
            applies = await pcr_sqla.get_notice(
                NoticeType.apply.value, group_id, order
            )
            subs = await pcr_sqla.get_notice(
                NoticeType.subscribe.value, group_id, order
            )
            board_msgs = await pcr_sqla.get_notice(
                NoticeType.board_message.value, group_id, order
            )
            trees = await pcr_sqla.get_notice(
                NoticeType.tree.value, group_id, order
            )
            queues.append(
                {
                    "order": order,
                    "enter_signal": state.enter_signal,
                    "apply": sorted(
                        (n.user_id, n.account_id or 0, n.text or "") for n in applies
                    ),
                    "subscribe": sorted(
                        (n.user_id, n.lap or 0, n.text or "") for n in subs
                    ),
                    "board_message": sorted(
                        (n.user_id, n.text or "") for n in board_msgs
                    ),
                    "tree": sorted((n.user_id,) for n in trees),
                }
            )

    viewer_ids = list(getattr(clan_info, "members", {}).keys())
    name_map = getattr(clan_info, "members", {}) or {}
    if viewer_ids:
        day_agg = await guild_today_knife_aggregate(
            group_id, int(time.time()), clan_info=clan_info
        )
        full_total = day_agg.full_knife_count
        comp_total = day_agg.comp_knife_count
        comp_entries = await knife_budget_service.group_guild_compensation_entries(
            viewer_ids, name_map
        )
    else:
        full_total = 0
        comp_total = 0
        comp_entries = []

    payload = {
        "lap": clan_info.lap_num,
        "rank": int(getattr(clan_info, "rank", 0) or 0),
        "period": str(clan_info.period or ""),
        "bosses": bosses,
        "queues": queues,
        "summary": {
            "full": full_total,
            "comp": comp_total,
            "comp_entries": [
                compensation_entry_fingerprint_dict(e) for e in comp_entries
            ],
        },
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
