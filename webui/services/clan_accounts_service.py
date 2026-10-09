"""公会成员列表（监控账号代查 clan_info，带短缓存）。"""
from __future__ import annotations

import time
from typing import Any, Dict, List

from loguru import logger

from ...clanbattle import clanbattle_info
from ...clanbattle.text_util import locale_sort_key
from ..util import call_in_main_loop

_CACHE: Dict[int, tuple[float, List[Dict[str, Any]]]] = {}
_TTL = 600


async def fetch_clan_member_options(group_id: int) -> List[Dict[str, Any]]:
    now = time.time()
    if group_id in _CACHE and now - _CACHE[group_id][0] < _TTL:
        return _CACHE[group_id][1]

    clan_info = clanbattle_info.get(group_id)
    if not clan_info or not getattr(clan_info, "loop_check", 0):
        raise ValueError("未开启出刀监控，无法拉取公会成员列表")

    async def _fetch():
        client = clan_info.client
        resp = await client.clan_info(clan_info.clan_id)
        members = []
        for m in resp.clan.members or []:
            members.append(
                {
                    "viewer_id": m.viewer_id,
                    "name": m.name,
                    "level": getattr(m, "level", 0),
                }
            )
        return members

    try:
        members = await call_in_main_loop(_fetch())
    except Exception as e:
        logger.warning("clan_info 失败 group={}: {}", group_id, e)
        raise
    members.sort(
        key=lambda m: (locale_sort_key(str(m.get("name") or "")), int(m["viewer_id"]))
    )
    _CACHE[group_id] = (now, members)
    return members
