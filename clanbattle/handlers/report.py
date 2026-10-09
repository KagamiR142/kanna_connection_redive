"""战报 / 催刀 / KPI 查询指令。"""
from __future__ import annotations

import time

from hoshino.typing import CQEvent, HoshinoBot

from ...database.dal import pcr_sqla
from ..base import (
    clanbattle_report,
    cuidao,
    dao_detial,
    day_report,
    get_cbreport,
    get_kpireport,
    get_plyerreport,
)
from ..boss_lap_records_service import (
    clan_monitor_ready,
    resolve_lap_for_boss_lap_records,
)
from ..command_match import (
    REX_BOSS_LAP_RECORDS,
    REX_KNIFE_DETAIL,
    REX_SEASON_REPORT_SLOT,
    REX_TODAY_REPORT_SLOT,
    proxy_rex,
    strict_rex,
)
from ..command_parser import match_exact, parse_account_slot_command, parse_boss_lap_records
from ..detail_reports import (
    format_boss_lap_records,
    format_season_guild_detail,
    format_season_user_detail,
    format_today_guild_detail,
    format_today_user_detail,
)
from ..kpi import kpi_report
from ..registry import clanbattle_info
from ..response_messages import unbound_account_bind_hint
from .context import extract_plain, require_group, send_report_payload, sender_tag


def register_report_handlers(sv) -> None:
    @sv.on_rex(strict_rex(r"今日出刀"))
    async def today_guild_knives(bot: HoshinoBot, ev: CQEvent):
        if not require_group(ev):
            return
        clan_info = clanbattle_info.get(ev.group_id)
        payload = await format_today_guild_detail(
            ev.group_id, bot, clan_info=clan_info
        )
        await send_report_payload(bot, ev, payload)

    @sv.on_rex(strict_rex(r"当期出刀"))
    async def season_guild_knives(bot: HoshinoBot, ev: CQEvent):
        if not require_group(ev):
            return
        clan_info = clanbattle_info.get(ev.group_id)
        payload = await format_season_guild_detail(
            ev.group_id, bot, clan_info=clan_info
        )
        if isinstance(payload, str) and payload == "本期会战目前暂无出刀数据":
            payload = f"{payload} {await sender_tag(bot, ev)}"
        await send_report_payload(bot, ev, payload)

    @sv.on_rex(strict_rex(REX_BOSS_LAP_RECORDS))
    async def boss_lap_records(bot: HoshinoBot, ev: CQEvent):
        if not require_group(ev):
            return
        parsed = parse_boss_lap_records(extract_plain(ev))
        if not parsed:
            await bot.send(
                ev,
                f"{await sender_tag(bot, ev)} 指令格式错误\n"
                "出刀记录格式：出刀记录<boss>[周目N|a[y|t]] 或 出刀记录<boss> <N>\n"
                "例：出刀记录3 / 出刀记录2周目29 / 出刀记录2a / 出刀记录2at",
            )
            return
        clan_info = clanbattle_info.get(ev.group_id)
        if not clan_monitor_ready(clan_info):
            await bot.send(
                ev,
                f"{await sender_tag(bot, ev)} 未开启出刀监控，无法查询出刀记录",
            )
            return
        if parsed.all_laps:
            payload = await format_boss_lap_records(
                ev.group_id,
                parsed.boss,
                bot,
                clan_info=clan_info,
                all_laps=True,
                day_token=parsed.day_token,
            )
        else:
            lap = await resolve_lap_for_boss_lap_records(
                ev.group_id, clan_info, parsed.boss, parsed.lap
            )
            if not lap:
                await bot.send(
                    ev,
                    f"{await sender_tag(bot, ev)} 无法确定周目，请指定周目或等待监控同步",
                )
                return
            payload = await format_boss_lap_records(
                ev.group_id,
                parsed.boss,
                bot,
                clan_info=clan_info,
                lap=lap,
            )
        if isinstance(payload, str):
            await bot.send(ev, f"{payload} {await sender_tag(bot, ev)}")
            return
        await send_report_payload(bot, ev, payload)

    @sv.on_rex(proxy_rex(REX_TODAY_REPORT_SLOT))
    async def today_user_report(bot: HoshinoBot, ev: CQEvent):
        if not require_group(ev):
            return
        from ..command_context import build_context

        ctx = await build_context(bot, ev, command_key="today_report")
        slot_parse = parse_account_slot_command(ctx.plain, "今日战报")
        msg = await format_today_user_detail(
            ev.group_id,
            ctx.target_user_id,
            slot_filter=slot_parse.account_slot if slot_parse else None,
            bot=bot,
        )
        if isinstance(msg, str) and "未绑定" in msg:
            msg = unbound_account_bind_hint(await sender_tag(bot, ev))
        await send_report_payload(bot, ev, msg)

    @sv.on_rex(proxy_rex(REX_SEASON_REPORT_SLOT))
    async def season_user_report(bot: HoshinoBot, ev: CQEvent):
        if not require_group(ev):
            return
        from ..command_context import build_context

        ctx = await build_context(bot, ev, command_key="season_report")
        slot_parse = parse_account_slot_command(ctx.plain, "当期战报")
        msg = await format_season_user_detail(
            ev.group_id,
            ctx.target_user_id,
            slot_filter=slot_parse.account_slot if slot_parse else None,
            bot=bot,
        )
        if isinstance(msg, str):
            if "未绑定" in msg:
                msg = unbound_account_bind_hint(await sender_tag(bot, ev))
            elif msg == "本期会战目前暂无出刀数据":
                msg = f"{msg} {await sender_tag(bot, ev)}"
        await send_report_payload(bot, ev, msg)

    @sv.on_rex(r"^\s*当前战报\s*$")
    async def get_report(bot: HoshinoBot, ev: CQEvent):
        if not require_group(ev):
            return
        if not (data := await pcr_sqla.get_all_records(ev.group_id)):
            await bot.send(ev, "数据库为空，请确保开启出刀监控")
            return
        players, all_damage, all_score = clanbattle_report(
            data, await pcr_sqla.get_max_dao(ev.group_id)
        )
        await bot.send(ev, await get_cbreport(players, all_damage, all_score))

    @sv.on_rex(r"^\s*我的战报(\d+)?\s*$")
    async def my_report(bot: HoshinoBot, ev: CQEvent):
        if not require_group(ev):
            return
        m = match_exact(extract_plain(ev), r"我的战报(\d+)?")
        if not m:
            return
        name = m.group(1) or ""
        data = None
        if name.isdigit():
            data = await pcr_sqla.get_player_records(int(name), 5, ev.group_id)
        if not data and name:
            members = await pcr_sqla.clanbattle_name2pcrid(ev.group_id, name)
            if not members:
                await bot.send(ev, "昵称错误")
                return
            if len(members) != 1:
                await bot.send(
                    ev,
                    "出现重名，请使用id查询，以下是可能id\n"
                    + "\n".join(str(x) for x in members[:3]),
                )
                return
            data = await pcr_sqla.get_player_records(members[0], 5, ev.group_id)
        elif not name:
            acc = await pcr_sqla.query_account(ev.user_id)
            if acc and acc[0].viewer_id:
                data = await pcr_sqla.get_player_records(
                    acc[0].viewer_id, 5, ev.group_id
                )
        if not data:
            await bot.send(ev, "数据库为空，请确保开启出刀监控或使用正确的角色名")
            return
        await bot.send(ev, await get_plyerreport(data))

    @sv.on_rex(proxy_rex(REX_KNIFE_DETAIL))
    async def single_player_report(bot: HoshinoBot, ev: CQEvent):
        if not require_group(ev):
            return
        m = match_exact(extract_plain(ev), REX_KNIFE_DETAIL)
        if not m:
            return
        dao_id = int(m.group(1))
        if info := await pcr_sqla.get_history(dao_id, ev.group_id):
            await bot.send(ev, await dao_detial(info))
        else:
            await bot.send(ev, "请检查你的出刀编号是否正确。")

    @sv.on_rex(r"^\s*催刀\s*$")
    async def nei_gui(bot: HoshinoBot, ev: CQEvent):
        if not require_group(ev):
            return
        members = {}
        if ev.group_id in clanbattle_info:
            members = clanbattle_info[ev.group_id].members
        else:
            await bot.send(ev, "未开启出刀监控,不显示没出刀的人")
        if not (data := await pcr_sqla.get_day_rcords(int(time.time()), ev.group_id)):
            await bot.send(ev, "数据库为空，请确保开启出刀监控")
            return
        await bot.send(ev, cuidao(await day_report(data, members)))

    @sv.on_rex(r"^\s*(?:会战KPI|会战kpi)\s*$")
    async def get_kpi(bot: HoshinoBot, ev: CQEvent):
        if not require_group(ev):
            return
        if not (data := await pcr_sqla.get_all_records(ev.group_id)):
            await bot.send(ev, "数据库为空，请确保开启出刀监控")
            return
        img = await get_kpireport(kpi_report(data, await pcr_sqla.get_kpis(ev.group_id)))
        await bot.send(ev, img)
