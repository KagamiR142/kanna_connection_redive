"""预约 / 留言 / 预约表指令。"""
from __future__ import annotations

from hoshino.typing import CQEvent, HoshinoBot
from loguru import logger

from ...basedata import NoticeType
from ...database.models import NoticeCache
from ..boss_snapshot import get_boss_snap
from ..command_context import build_context
from ..command_match import (
    REX_BOARD_MESSAGE,
    REX_CANCEL_BOARD,
    REX_CANCEL_SUBSCRIBE,
    REX_CLEAR_SUBSCRIBE,
    REX_SUBSCRIBE,
    proxy_rex,
    strict_rex,
)
from ..command_parser import (
    parse_board_message,
    parse_cancel_board_message,
    parse_cancel_subscribe,
    parse_clear_subscribe,
    parse_subscribe,
)
from ..permissions import PERM_DENIED, is_ops_admin
from ..registry import clanbattle_info
from ..reserve_service import (
    delete_all_reserve,
    delete_user_reserve,
    get_user_reserve,
    list_reserve_for_boss,
    reserve_is_board_message,
    upsert_board_message,
    upsert_subscribe,
)
from ..status_cache import notify_display_data_changed
from ..text_util import qq_display_name
from .context import extract_plain, require_group, sender_tag


def register_reserve_handlers(sv) -> None:
    @sv.on_rex(proxy_rex(REX_SUBSCRIBE))
    async def subscribe(bot: HoshinoBot, ev: CQEvent):
        if not require_group(ev):
            return
        ctx = await build_context(bot, ev, command_key="subscribe")
        parsed = parse_subscribe(ctx.plain)
        if not parsed:
            sender = await sender_tag(bot, ev)
            await bot.send(
                ev,
                f"{sender} 指令格式错误\n"
                "预约格式：预约<boss>[周目数][:留言][@user]\n"
                "例：预约1 / 预约2周目15：3e满补 / 预约3周目15：满补@user",
            )
            return
        clan_info = clanbattle_info.get(ev.group_id)
        snap = get_boss_snap(clan_info, parsed.boss)
        if not snap:
            await bot.send(
                ev,
                f"{await sender_tag(bot, ev)} 未开启出刀监控，无法校验预约周目，请先开启监控",
            )
            return
        target_lap = parsed.lap if parsed.lap else snap.lap + 1
        if parsed.lap and parsed.lap <= snap.lap:
            await bot.send(
                ev,
                f"{await sender_tag(bot, ev)} 无法预约该周目\n"
                f"{parsed.boss}王当前为{snap.lap}周目，仅可预约{snap.lap + 1}周目及之后",
            )
            return
        existing = await get_user_reserve(
            ev.group_id, parsed.boss, ctx.target_user_id
        )
        if (
            existing
            and not reserve_is_board_message(existing)
            and existing.lap == target_lap
            and (existing.text or "") == (parsed.remark or "")
        ):
            await bot.send(
                ev,
                f"您已预约此boss，预约记录：{target_lap}周目{parsed.boss}王 {await sender_tag(bot, ev)}",
            )
            return
        await upsert_subscribe(
            NoticeCache(
                group_id=ev.group_id,
                notice_type=NoticeType.subscribe.value,
                user_id=ctx.target_user_id,
                boss=parsed.boss,
                lap=target_lap,
                text=parsed.remark,
            )
        )
        await notify_display_data_changed(ev.group_id, "subscribe")
        logger.info(
            "预约: group={} user={} boss={} lap={}",
            ev.group_id,
            ctx.target_user_id,
            parsed.boss,
            target_lap,
        )
        msg = f"成功预约{target_lap}周目{parsed.boss}王 {await sender_tag(bot, ev)}"
        if parsed.remark:
            msg += f"\n预约留言：{parsed.remark}"
        await bot.send(ev, msg)

    @sv.on_rex(proxy_rex(REX_BOARD_MESSAGE))
    async def board_message(bot: HoshinoBot, ev: CQEvent):
        if not require_group(ev):
            return
        ctx = await build_context(bot, ev, command_key="board_message")
        parsed = parse_board_message(ctx.plain)
        if not parsed:
            await bot.send(
                ev,
                f"{await sender_tag(bot, ev)} 指令格式错误\n"
                "留言格式：留言<boss>：<内容>[@user]\n"
                "例：留言3：今晚别动此王",
            )
            return
        clan_info = clanbattle_info.get(ev.group_id)
        if not get_boss_snap(clan_info, parsed.boss):
            await bot.send(
                ev,
                f"{await sender_tag(bot, ev)} 未开启出刀监控，无法留言，请先开启监控",
            )
            return
        existing = await get_user_reserve(
            ev.group_id, parsed.boss, ctx.target_user_id
        )
        if (
            existing
            and reserve_is_board_message(existing)
            and (existing.text or "") == parsed.remark
        ):
            await bot.send(
                ev,
                f"您已留言：{parsed.boss}王 {await sender_tag(bot, ev)}",
            )
            return
        action = await upsert_board_message(
            NoticeCache(
                group_id=ev.group_id,
                notice_type=NoticeType.board_message.value,
                user_id=ctx.target_user_id,
                boss=parsed.boss,
                lap=0,
                text=parsed.remark,
            )
        )
        await notify_display_data_changed(ev.group_id, "board_message")
        sender = await sender_tag(bot, ev)
        if action == "subscribe_text_updated":
            await bot.send(
                ev,
                f"已更新预约留言：{parsed.boss}王\n留言：{parsed.remark} {sender}",
            )
            return
        await bot.send(
            ev,
            f"成功留言{parsed.boss}王\n留言：{parsed.remark} {sender}",
        )

    @sv.on_rex(r"^\s*预约表\s*$")
    async def formsubscribe(bot: HoshinoBot, ev: CQEvent):
        if not require_group(ev):
            return
        group_id = ev.group_id
        form = ""
        for boss in range(1, 6):
            subscribers = []
            if info := await list_reserve_for_boss(group_id, boss):
                for player in info:
                    member = await bot.get_group_member_info(
                        group_id=ev.group_id, user_id=player.user_id
                    )
                    name = qq_display_name(
                        player.user_id,
                        member.get("card", ""),
                        member.get("nickname", ""),
                    )
                    if reserve_is_board_message(player):
                        msg = f"(留言){name}:{player.text}"
                    else:
                        lap = player.lap or 0
                        msg = f"{lap}周目{boss}王"
                        if player.text:
                            msg = f"{name}:{player.text} {msg}"
                        else:
                            msg = f"{name} {msg}"
                    subscribers.append(msg)
            if subscribers:
                form += f"\n========={boss}王=========\n" + "\n".join(subscribers)
        await bot.send(ev, f"当前预约列表{form}" if form else "预约列表为空")

    @sv.on_rex(proxy_rex(REX_CANCEL_BOARD))
    async def cancel_board_message(bot: HoshinoBot, ev: CQEvent):
        if not require_group(ev):
            return
        ctx = await build_context(bot, ev, command_key="cancel_board_message")
        boss, matched = parse_cancel_board_message(ctx.plain)
        if not matched or boss is None:
            return
        existing = await get_user_reserve(
            ev.group_id, boss, ctx.target_user_id
        )
        if not existing or not reserve_is_board_message(existing):
            await bot.send(
                ev,
                f"未找到可取消的留言记录 {await sender_tag(bot, ev)}",
            )
            return
        await delete_user_reserve(ev.group_id, boss, ctx.target_user_id)
        await notify_display_data_changed(ev.group_id, "cancel_board_message")
        await bot.send(
            ev, f"已取消留言{boss}王 {await sender_tag(bot, ev)}"
        )

    @sv.on_rex(proxy_rex(REX_CANCEL_SUBSCRIBE))
    async def cancel_subscribe(bot: HoshinoBot, ev: CQEvent):
        if not require_group(ev):
            return
        ctx = await build_context(bot, ev, command_key="cancel_subscribe")
        boss, matched = parse_cancel_subscribe(ctx.plain)
        if not matched:
            return
        if boss is None:
            await bot.send(
                ev,
                f"{await sender_tag(bot, ev)} 指令格式错误\n"
                "取消预约格式：取消预约<boss>[@user]\n"
                "例：取消预约1 / 取消预约2@user",
            )
            return
        existing = await get_user_reserve(
            ev.group_id, boss, ctx.target_user_id
        )
        if not existing:
            await bot.send(
                ev,
                f"未找到可取消的预约/留言记录 {await sender_tag(bot, ev)}",
            )
            return
        was_message = reserve_is_board_message(existing)
        lap = existing.lap or 0
        await delete_user_reserve(ev.group_id, boss, ctx.target_user_id)
        await notify_display_data_changed(ev.group_id, "cancel_subscribe")
        sender = await sender_tag(bot, ev)
        if was_message:
            await bot.send(ev, f"已取消留言{boss}王 {sender}")
            return
        await bot.send(ev, f"已取消预约{lap}周目{boss}王 {sender}")

    @sv.on_rex(strict_rex(REX_CLEAR_SUBSCRIBE))
    async def clean_subscribe(bot: HoshinoBot, ev: CQEvent):
        if not require_group(ev):
            return
        if not is_ops_admin(ev):
            await bot.send(ev, f"{PERM_DENIED} {await sender_tag(bot, ev)}")
            return
        boss = parse_clear_subscribe(extract_plain(ev))
        if boss is None:
            await bot.send(
                ev,
                f"{await sender_tag(bot, ev)} 指令格式错误\n"
                "清空预约格式：清空预约<boss>\n"
                "例：清空预约1",
            )
            return
        n = await delete_all_reserve(ev.group_id, boss)
        await notify_display_data_changed(ev.group_id, "clear_subscribe")
        await bot.send(
            ev, f"成功清理{n}条预约/留言记录 {await sender_tag(bot, ev)}"
        )
