"""状态图 PNG 缓存：监控 batch 收尾合并重绘 + QQ/Web 防抖刷新。

日志约定：本模块仅通过 loguru / Web 运维日志（append_ops_log）记录，
**禁止**向 QQ 群发送任何「状态图待渲染 / 已缓存」类调试文案。
"""
from __future__ import annotations

import asyncio
import contextlib
import time
from typing import Dict, Optional, TYPE_CHECKING

from loguru import logger
from nonebot import get_bot

from ..status_image import status_image_to_bytes
from .status_builder import build_clan_status
from .status_fingerprint import compute_status_fingerprint

if TYPE_CHECKING:
    from .model import ClanBattle

_batch_depth: Dict[int, int] = {}
_debounce_handles: Dict[int, asyncio.TimerHandle] = {}
_fp_fail_count: Dict[int, int] = {}
_fp_fail_last_log: Dict[int, float] = {}
STATUS_RENDER_DEBOUNCE_SEC = 0.35
FP_FAIL_LOG_INTERVAL_SEC = 60.0


def _get_lock(clan_info: "ClanBattle") -> asyncio.Lock:
    lock = getattr(clan_info, "_status_render_lock", None)
    if lock is None:
        lock = asyncio.Lock()
        clan_info._status_render_lock = lock
    return lock


def is_monitor_active(clan_info: "ClanBattle") -> bool:
    return bool(clan_info.loop_check)


class status_render_batch(contextlib.AbstractAsyncContextManager):
    """监控单轮：子步骤禁止直接 PIL，退出时 finalize 一次。"""

    def __init__(self, clan_info: "ClanBattle") -> None:
        self.clan_info = clan_info
        self.group_id = clan_info.group_id

    async def __aenter__(self):
        _batch_depth[self.group_id] = _batch_depth.get(self.group_id, 0) + 1
        return self

    async def __aexit__(self, exc_type, exc, tb):
        _batch_depth[self.group_id] = max(0, _batch_depth.get(self.group_id, 1) - 1)
        if _batch_depth.get(self.group_id, 0) == 0:
            await finalize_status_image(self.clan_info, "batch_finalize")
            self.clan_info.status_dirty = False
        return False


def touch_group_display_timestamps(group_id: int) -> None:
    """Web SSE / 面板：与 notice 变更共用的时间戳。"""
    from .registry import notice_update_time

    notice_update_time[group_id] = int(time.time())


async def notify_display_data_changed(
    group_id: int, source: str = "notice"
) -> None:
    """队列/自助上报等：合并防抖重绘，并 bump Web 推送标记。"""
    touch_group_display_timestamps(group_id)
    from .registry import clanbattle_info

    clan_info = clanbattle_info.get(group_id)
    if not clan_info or not is_monitor_active(clan_info):
        return
    if _batch_depth.get(group_id, 0) > 0:
        clan_info.status_dirty = True
        logger.debug(
            "状态图 dirty（batch 内）: group={} source={}", group_id, source
        )
        return
    _schedule_debounced_finalize(clan_info, source)


def _schedule_debounced_finalize(clan_info: "ClanBattle", source: str) -> None:
    group_id = clan_info.group_id
    loop = asyncio.get_running_loop()
    old = _debounce_handles.pop(group_id, None)
    if old and not old.cancelled():
        old.cancel()

    def _fire():
        _debounce_handles.pop(group_id, None)
        asyncio.create_task(finalize_status_image(clan_info, f"debounce:{source}"))

    _debounce_handles[group_id] = loop.call_later(
        STATUS_RENDER_DEBOUNCE_SEC, _fire
    )


async def finalize_status_image(clan_info: "ClanBattle", reason: str) -> None:
    if not is_monitor_active(clan_info):
        return
    try:
        fp = await compute_status_fingerprint(clan_info, get_bot())
    except Exception as e:
        gid = clan_info.group_id
        _fp_fail_count[gid] = _fp_fail_count.get(gid, 0) + 1
        now = time.time()
        if now - _fp_fail_last_log.get(gid, 0) >= FP_FAIL_LOG_INTERVAL_SEC:
            logger.warning(
                "状态指纹计算失败 group={} recent_failures={} err={}",
                gid,
                _fp_fail_count[gid],
                e,
            )
            _fp_fail_last_log[gid] = now
        return

    if fp == getattr(clan_info, "status_content_hash", ""):
        logger.debug(
            "状态图跳过（指纹未变）: group={} reason={}", clan_info.group_id, reason
        )
        return

    clan_info.status_content_hash = fp
    logger.info(
        "状态图待渲染: group={} reason={} version={}",
        clan_info.group_id,
        reason,
        getattr(clan_info, "status_png_version", 0) + 1,
    )
    await _schedule_render_task(clan_info, reason)


async def _schedule_render_task(clan_info: "ClanBattle", reason: str) -> None:
    task = getattr(clan_info, "status_render_task", None)
    if task and not task.done():
        clan_info.status_render_pending = True
        logger.debug("状态图渲染排队: group={} reason={}", clan_info.group_id, reason)
        return
    clan_info.status_render_task = asyncio.create_task(
        _render_status_png_loop(clan_info, reason)
    )


async def _render_status_png_loop(clan_info: "ClanBattle", reason: str) -> None:
    while True:
        clan_info.status_render_pending = False
        try:
            await _render_status_png_once(clan_info, reason)
        except Exception:
            logger.exception("状态图渲染失败 group={}", clan_info.group_id)
        if not clan_info.status_render_pending:
            break
        reason = "pending"
    clan_info.status_render_task = None


async def _render_status_png_once(clan_info: "ClanBattle", reason: str) -> None:
    async with _get_lock(clan_info):
        bot = get_bot()
        dto = await build_clan_status(bot, clan_info)
        png = await asyncio.to_thread(status_image_to_bytes, dto)
        clan_info.status_png = png
        clan_info.status_png_version = getattr(clan_info, "status_png_version", 0) + 1
        clan_info.status_png_at = time.time()
        clan_info.status_image_update_time = int(time.time())
        touch_group_display_timestamps(clan_info.group_id)
        try:
            from ..webui.ops_log import append_ops_log

            append_ops_log(
                "status_image",
                f"状态图 v{clan_info.status_png_version} 已缓存 reason={reason} bytes={len(png)}",
                group_id=clan_info.group_id,
            )
        except Exception:
            logger.debug("状态图运维日志写入跳过 group={}", clan_info.group_id)
        logger.info(
            "状态图已缓存: group={} reason={} version={} bytes={}",
            clan_info.group_id,
            reason,
            clan_info.status_png_version,
            len(png),
        )


def get_cached_status_png_bytes(clan_info: "ClanBattle") -> Optional[bytes]:
    return getattr(clan_info, "status_png", None)


async def wait_cached_status_png(
    clan_info: "ClanBattle", timeout: float = 0.8
) -> Optional[bytes]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        png = get_cached_status_png_bytes(clan_info)
        if png:
            return png
        await asyncio.sleep(0.05)
    return get_cached_status_png_bytes(clan_info)


async def render_status_png_sync_fallback(clan_info: "ClanBattle", reason: str) -> bytes:
    """缓存未就绪时单次同步渲染（仍不拉 top）。"""
    await _render_status_png_once(clan_info, reason)
    png = get_cached_status_png_bytes(clan_info)
    if not png:
        raise RuntimeError("状态图渲染未产生缓存")
    return png
