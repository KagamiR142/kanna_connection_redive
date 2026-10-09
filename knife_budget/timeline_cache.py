"""timeline_report 短时缓存：battle_log 写入，damage_history 读取（带退避重试）。"""
from __future__ import annotations

import asyncio
import time
from typing import Awaitable, Callable, Dict, Optional, Tuple

from loguru import logger

from .classifier import TimelineInfo

_Key = Tuple[int, int, int]
_cache: Dict[_Key, TimelineInfo] = {}

_BattleCtxKey = Tuple[int, int, int, int]
_battle_ctx: Dict[_BattleCtxKey, Tuple[int, int, TimelineInfo]] = {}

RETRY_DELAYS_SEC = (0.25, 0.5, 1.0)
RETRY_DELAYS_KILL_EXTRA_SEC = (2.0,)
BATTLE_CTX_MAX_AGE_SEC = 300


def put_timeline(
    group_id: int,
    viewer_id: int,
    log_id: int,
    timeline: TimelineInfo,
) -> None:
    gid, vid, lid = int(group_id), int(viewer_id), int(log_id)
    if gid <= 0 or vid <= 0 or lid <= 0:
        return
    _cache[(gid, vid, lid)] = timeline
    logger.debug(
        "timeline_cache.put: group={} viewer={} log_id={} srt={} bt={}",
        gid,
        vid,
        lid,
        timeline.start_remain_time,
        timeline.battle_time,
    )


def put_timeline_battle_context(
    group_id: int,
    viewer_id: int,
    lap: int,
    boss_order: int,
    record_time: int,
    battle_log_id: int,
    timeline: TimelineInfo,
) -> None:
    """battle_log 与 damage_history 的 log_id 不一致时，按周目+王+时间关联。"""
    gid, vid = int(group_id), int(viewer_id)
    lap_i, boss_i = int(lap or 0), int(boss_order or 0)
    if gid <= 0 or vid <= 0 or lap_i <= 0 or not (1 <= boss_i <= 5):
        return
    key = (gid, vid, lap_i, boss_i)
    rt = int(record_time or int(time.time()))
    bid = int(battle_log_id or 0)
    _battle_ctx[key] = (rt, bid, timeline)
    if bid > 0:
        put_timeline(gid, vid, bid, timeline)
    logger.debug(
        "timeline_cache.put_battle_ctx: group={} viewer={} lap={} boss={} "
        "battle_log_id={} record_time={} bt={} srt={}",
        gid,
        vid,
        lap_i,
        boss_i,
        bid,
        rt,
        timeline.battle_time,
        timeline.start_remain_time,
    )


def get_timeline_by_battle_context(
    group_id: int,
    viewer_id: int,
    lap: int,
    boss_order: int,
    settlement_time: int,
    *,
    max_age_sec: int = BATTLE_CTX_MAX_AGE_SEC,
) -> Optional[TimelineInfo]:
    gid, vid = int(group_id), int(viewer_id)
    lap_i, boss_i = int(lap or 0), int(boss_order or 0)
    if gid <= 0 or vid <= 0 or lap_i <= 0 or not (1 <= boss_i <= 5):
        return None
    entry = _battle_ctx.get((gid, vid, lap_i, boss_i))
    if not entry:
        return None
    record_time, battle_log_id, timeline = entry
    st = int(settlement_time or 0)
    if st > 0 and abs(st - int(record_time)) > int(max_age_sec):
        return None
    logger.info(
        "timeline_cache hit battle_ctx: group={} viewer={} lap={} boss={} "
        "settle_time={} battle_log_id={} bt={}",
        gid,
        vid,
        lap_i,
        boss_i,
        st,
        battle_log_id,
        timeline.battle_time,
    )
    return timeline


def get_timeline(
    group_id: int,
    viewer_id: int,
    log_id: int,
) -> Optional[TimelineInfo]:
    gid, vid, lid = int(group_id), int(viewer_id), int(log_id)
    if gid <= 0 or vid <= 0 or lid <= 0:
        return None
    return _cache.get((gid, vid, lid))


async def resolve_timeline_for_settlement(
    group_id: int,
    viewer_id: int,
    log_id: int,
    fetcher: Callable[[int, int], Awaitable[Optional[TimelineInfo]]],
    *,
    record_remain_time: Optional[int] = None,
    record_battle_time: Optional[int] = None,
    lap: int = 0,
    boss_order: int = 0,
    settlement_time: int = 0,
    is_kill: bool = False,
) -> Optional[TimelineInfo]:
    """
    结算读 timeline：log_id 缓存 → 退避拉 API → battle_ctx → RecordDao 兜底。
    fetcher(viewer_id, log_id) 由调用方注入（避免耦合 client）。
    """
    cached = get_timeline(group_id, viewer_id, log_id)
    if cached is not None:
        logger.debug(
            "timeline_cache hit: group={} viewer={} log_id={} srt={}",
            group_id,
            viewer_id,
            log_id,
            cached.start_remain_time,
        )
        return cached

    last_err: Optional[Exception] = None
    delays = list(RETRY_DELAYS_SEC)
    if is_kill:
        delays.extend(RETRY_DELAYS_KILL_EXTRA_SEC)
    for delay in delays:
        try:
            tl = await fetcher(int(viewer_id), int(log_id))
            if tl is not None:
                put_timeline(group_id, viewer_id, log_id, tl)
                return tl
        except Exception as e:
            last_err = e
        await asyncio.sleep(delay)

    ctx_tl = get_timeline_by_battle_context(
        group_id,
        viewer_id,
        lap,
        boss_order,
        settlement_time,
    )
    if ctx_tl is not None:
        put_timeline(group_id, viewer_id, log_id, ctx_tl)
        return ctx_tl

    srt = int(record_remain_time or 0)
    if srt > 0:
        bt = int(record_battle_time or 0)
        tl = TimelineInfo(battle_time=bt, start_remain_time=srt)
        put_timeline(group_id, viewer_id, log_id, tl)
        logger.info(
            "timeline_cache fallback remain_time: group={} viewer={} log_id={} srt={} bt={}",
            group_id,
            viewer_id,
            log_id,
            srt,
            bt,
        )
        return tl

    logger.debug(
        "timeline_cache miss: group={} viewer={} log_id={} lap={} boss={} err={}",
        group_id,
        viewer_id,
        log_id,
        lap,
        boss_order,
        last_err,
    )
    return None


__all__ = [
    "get_timeline",
    "get_timeline_by_battle_context",
    "put_timeline",
    "put_timeline_battle_context",
    "resolve_timeline_for_settlement",
]
