"""队列项 Web DTO  enrichment（面板 / SSE 共用）。"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import nonebot
from hoshino.typing import HoshinoBot

from ...database.models import NoticeCache
from ...member.display import format_actor_label, get_group_nickname


def _is_compensation(text: str) -> bool:
    t = (text or "").strip()
    return t in ("b", "B", "补偿")


async def enrich_notice_row(
    bot: HoshinoBot,
    group_id: int,
    row: NoticeCache,
    *,
    now: Optional[int] = None,
) -> Dict[str, Any]:
    now = now if now is not None else int(time.time())
    data = row.dict()
    uid = int(row.user_id)
    data["qq_nickname"] = await get_group_nickname(bot, group_id, uid)
    data["display_label"] = await format_actor_label(
        bot,
        group_id,
        uid,
        account_id=row.account_id,
        viewer_id=row.viewer_id,
    )
    data["is_compensation"] = _is_compensation(row.text or "")
    if row.time:
        data["hang_seconds"] = max(0, now - int(row.time))
    else:
        data["hang_seconds"] = 0
    return data


async def enrich_notice_list(
    group_id: int, rows: List[NoticeCache]
) -> List[Dict[str, Any]]:
    if not rows:
        return []
    bot = nonebot.get_bot()
    now = int(time.time())
    out: List[Dict[str, Any]] = []
    for row in rows:
        out.append(await enrich_notice_row(bot, group_id, row, now=now))
    return out
