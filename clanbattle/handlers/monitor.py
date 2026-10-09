"""出刀监控启停指令。"""
from __future__ import annotations

from hoshino.typing import CQEvent, HoshinoBot
from loguru import logger

from ...database.dal import Account
from ..command_match import (
    REX_MONITOR,
    REX_MONITOR_1,
    REX_MONITOR_2,
    REX_MONITOR_3,
    strict_rex,
)
from ..decorators import check_monitor_account, require_ops_admin
from ..monitor_runtime_service import start_clan_monitor
from ..permissions import PERM_DENIED, can_stop_monitor
from ..registry import clanbattle_info
from ...util.monitor_binding_service import format_monitor_status_message
from .context import require_group, sender_tag


async def _run_monitor_start(
    bot: HoshinoBot,
    ev: CQEvent,
    account: Account,
    qq_id: int,
    monitor_slot: int,
) -> None:
    group_id = ev.group_id
    ok, msg, _ = await start_clan_monitor(
        group_id=group_id,
        operator_qq=qq_id,
        bot_id=int(ev.self_id),
        account=account,
        monitor_slot=monitor_slot,
        notify=bot,
        ev=ev,
    )
    if ok:
        await bot.send(ev, f"{await sender_tag(bot, ev)} {msg}")


def _register_start_handler(sv, pattern: str, slot: int) -> None:
    @sv.on_rex(strict_rex(pattern))
    @require_ops_admin
    @check_monitor_account(slot)
    async def start_monitor_handler(
        bot: HoshinoBot,
        ev: CQEvent,
        account: Account,
        qq_id: int,
        monitor_slot: int,
    ):
        if not require_group(ev):
            return
        await _run_monitor_start(bot, ev, account, qq_id, monitor_slot)

    start_monitor_handler.__name__ = f"clanbattle_monitor_slot_{slot}_{pattern[:12]}"


def register_monitor_handlers(sv) -> None:
    _register_start_handler(sv, REX_MONITOR_3, 3)
    _register_start_handler(sv, REX_MONITOR_2, 2)
    _register_start_handler(sv, REX_MONITOR_1, 1)
    _register_start_handler(sv, REX_MONITOR, 1)

    @sv.on_rex(strict_rex(r"出刀监控状态"))
    async def monitor_status(bot: HoshinoBot, ev: CQEvent):
        if not require_group(ev):
            return
        group_id = ev.group_id
        clan_info = clanbattle_info.get(group_id)
        msg = await format_monitor_status_message(group_id, clan_info, int(ev.user_id))
        await bot.send(ev, msg)
        logger.info("出刀监控状态已回复 group={} by={}", group_id, ev.user_id)

    @sv.on_rex(strict_rex(r"取消出刀监控"))
    async def delete_monitor(bot: HoshinoBot, ev: CQEvent):
        if not require_group(ev):
            return
        group_id = ev.group_id
        if group_id not in clanbattle_info:
            await bot.send(ev, "出刀监控功能未启用")
            return
        clan_info = clanbattle_info[group_id]
        if can_stop_monitor(ev, clan_info.user_id):
            clan_info.loop_num += 1
            logger.info("监控关闭: group={} by={}", group_id, ev.user_id)
        else:
            await bot.send(ev, PERM_DENIED)
