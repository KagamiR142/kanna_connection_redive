"""成员身份管道：user_account 与监控 Account 解耦（Phase J 单入口）。"""
from __future__ import annotations

import time
from typing import List, Optional, Sequence, Set

from loguru import logger

from ..database.dal import pcr_sqla
from ..database.models import RecordDao
from .text_util import game_display_name, locale_sort_key

_monitor_viewer_ids: Optional[Set[int]] = None
_monitor_viewer_ts: float = 0.0
_MONITOR_TTL = 60.0


def display_slot(sort_order: int) -> int:
    """展示/指令槽位编号：sort_order 从 0 起，对外从 1 起。"""
    return int(sort_order or 0) + 1


async def compact_user_binding_sort_orders(user_id: int) -> None:
    rows = await pcr_sqla.query_user_accounts(user_id)
    if not rows:
        return
    changed = False
    for idx, row in enumerate(rows):
        if int(row.sort_order or 0) != idx:
            row.sort_order = idx
            await pcr_sqla.add_user_account(row)
            changed = True
    if changed:
        logger.info(
            "绑定槽位压紧: user_id={} slots={}",
            user_id,
            [display_slot(r.sort_order) for r in rows],
        )


async def _refresh_monitor_viewer_ids() -> Set[int]:
    global _monitor_viewer_ids, _monitor_viewer_ts
    now = time.time()
    if _monitor_viewer_ids is not None and now - _monitor_viewer_ts < _MONITOR_TTL:
        return _monitor_viewer_ids
    ids: Set[int] = set()
    for acc in await pcr_sqla.list_accounts():
        if acc.viewer_id:
            ids.add(int(acc.viewer_id))
    _monitor_viewer_ids = ids
    _monitor_viewer_ts = now
    logger.debug("监控 viewer 缓存刷新: count={}", len(ids))
    return ids


async def is_monitor_viewer(viewer_id: int) -> bool:
    return int(viewer_id) in await _refresh_monitor_viewer_ids()


async def viewer_to_member_qq(viewer_id: int) -> Optional[int]:
    """仅 user_account；多用户绑同一 viewer 时取最小 user_id（展示以 resolve_primary_binding 为准）。"""
    users = sorted(
        {int(r.user_id) for r in await pcr_sqla.query_accounts_by_viewer(viewer_id) if r.user_id}
    )
    return users[0] if users else None


async def resolve_member_display_name(
    viewer_id: int,
    *,
    group_id: Optional[int] = None,
    user_id: Optional[int] = None,
) -> str:
    """成员游戏名：alias → 公会 members → RecordDao.name → UID 占位。"""
    vid = int(viewer_id)
    if user_id is not None:
        for row in await pcr_sqla.query_user_accounts(user_id):
            if int(row.viewer_id or 0) == vid:
                alias = str(row.alias or "").strip()
                if alias:
                    return alias
                break
    if group_id is not None:
        gid = int(group_id)
        try:
            from ..webui.services.clan_accounts_service import fetch_clan_member_options

            for m in await fetch_clan_member_options(gid):
                if int(m["viewer_id"]) == vid:
                    name = str(m.get("name") or "").strip()
                    if name:
                        return name
        except ValueError:
            pass
        except Exception as e:
            logger.debug(
                "resolve_member_display_name 公会列表不可用 viewer={} group={} err={}",
                vid,
                gid,
                e,
            )
        db_name = await pcr_sqla.get_latest_record_name(vid, gid)
        if db_name:
            return db_name
    mon_name = await pcr_sqla.get_monitor_account_name_by_viewer(vid)
    if mon_name:
        return mon_name
    any_name = await pcr_sqla.get_latest_record_name_any_group(vid)
    if any_name:
        return any_name
    return game_display_name("", vid)


def dedupe_record_daos(records: Sequence[RecordDao]) -> List[RecordDao]:
    """读侧按 (group_id, battle_log_id) 去重，保留最早 time 的一条。"""
    seen: Set[tuple] = set()
    out: List[RecordDao] = []
    dropped = 0
    for rec in sorted(records, key=lambda r: (r.time, r.id or 0)):
        log_id = int(rec.battle_log_id or 0)
        if log_id <= 0:
            out.append(rec)
            continue
        key = (int(rec.group_id or 0), log_id)
        if key in seen:
            dropped += 1
            continue
        seen.add(key)
        out.append(rec)
    if dropped:
        logger.debug("出刀记录读侧去重: dropped={} kept={}", dropped, len(out))
    return out


__all__ = [
    "compact_user_binding_sort_orders",
    "dedupe_record_daos",
    "display_slot",
    "is_monitor_viewer",
    "locale_sort_key",
    "resolve_member_display_name",
    "viewer_to_member_qq",
]
