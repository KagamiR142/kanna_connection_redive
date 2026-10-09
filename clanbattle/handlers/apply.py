"""申请出刀 / SL / 挂树 / 掉刀 / 查树 / 清空出刀点数。"""
from __future__ import annotations

import time
from typing import Optional

from hoshino.typing import CQEvent, HoshinoBot
from loguru import logger

from ...basedata import NoticeType
from ...database.dal import pcr_sqla
from ...database.models import NoticeCache, SLDao
from ...knife_budget.service import knife_budget_service
from ...challenge.service import challenge_service
from ..boss_snapshot import get_boss_snap, format_apply_boss_status_line
from ..command_context import build_context
from ..command_match import (
    REX_APPLY,
    REX_CANCEL_APPLY,
    REX_CLEAR_POINTS,
    REX_DROP_KNIFE,
    REX_DROP_KNIFE_B,
    REX_SL,
    REX_SL_QUERY,
    REX_TREE,
    proxy_rex,
    strict_rex,
)
from ..command_parser import (
    parse_account_slot_command,
    parse_apply,
    parse_cancel_apply,
    parse_cancel_tree,
    parse_sl_query_command,
    parse_tree,
)
from ..registry import clanbattle_info
from ..response_builder import build_apply_success_message
from ..response_messages import (
    apply_format_error,
    tree_format_error,
    unbound_account,
)
from ..status_cache import notify_display_data_changed
from ..account_label import format_member_account_tag
from ..text_util import game_display_name, qq_display_name, strip_trailing_cq_at
from ..base import format_time
from .context import (
    account_has_comp,
    clear_user_applies,
    clear_user_sl_challenge,
    require_group,
    sender_tag,
)


async def _handle_apply(bot: HoshinoBot, ev: CQEvent) -> None:
    if not require_group(ev):
        return
    ctx = await build_context(bot, ev, command_key="apply")
    parsed = parse_apply(ctx.plain)
    if not parsed:
        await bot.send(ev, apply_format_error(await sender_tag(bot, ev)))
        return
    from ..account_service import (
        BoundAccount,
        list_member_bound_accounts,
        pick_account,
        user_all_knife_points_exhausted,
    )

    sender = await sender_tag(bot, ev)
    gid = int(ev.group_id)
    bound = await list_member_bound_accounts(ctx.target_user_id, group_id=gid)
    if await user_all_knife_points_exhausted(ctx.target_user_id):
        await bot.send(ev, f"{sender} 您今日已出完三刀，祝您拥有美好的一天")
        return

    acc: Optional[BoundAccount] = None
    if parsed.account_slot:
        if not bound:
            await bot.send(ev, unbound_account(sender))
            return
        acc = await pick_account(
            ctx.target_user_id, parsed.account_slot, group_id=gid
        )
        if acc is None:
            await bot.send(
                ev,
                f"未找到账号编号 {parsed.account_slot}，请检查绑定 {sender}",
            )
            return
        summary = await knife_budget_service.remaining_summary(acc.viewer_id)
        if float(summary.get("points") or 0) <= 0:
            await bot.send(
                ev, f"{sender} 您今日已出完三刀，祝您拥有美好的一天"
            )
            return
    elif bound:
        acc = await pick_account(ctx.target_user_id, None, group_id=gid)
        if acc is not None:
            summary = await knife_budget_service.remaining_summary(acc.viewer_id)
            if float(summary.get("points") or 0) <= 0:
                await bot.send(
                    ev, f"{sender} 您今日已出完三刀，祝您拥有美好的一天"
                )
                return
    if acc:
        declared_comp = parsed.is_comp and await account_has_comp(acc.viewer_id)
        if parsed.is_comp and not declared_comp:
            remark = parsed.remark.replace("[补偿]", "") if parsed.remark else ""
        else:
            remark = parsed.remark
        if await pcr_sqla.has_any_apply_for_viewer(
            ev.group_id, acc.viewer_id
        ):
            await bot.send(
                ev,
                f"该账号已有进行中的申请，请先取消或使用其他账号 {sender}",
            )
            return
        viewer_id = acc.viewer_id
        account_id = acc.account_id
    else:
        if parsed.is_comp or parsed.account_slot:
            await bot.send(
                ev,
                f"未绑定游戏账号，无法使用补偿标记或账号编号 {sender}",
            )
            return
        remark = parsed.remark
        if await pcr_sqla.has_any_apply_for_user(
            ev.group_id, ctx.target_user_id
        ):
            await bot.send(
                ev,
                f"该账号已有进行中的申请，请先取消或使用其他账号 {sender}",
            )
            return
        viewer_id = None
        account_id = None
        declared_comp = False
        acc = None
    await pcr_sqla.add_notice(
        NoticeCache(
            group_id=ev.group_id,
            notice_type=NoticeType.apply.value,
            user_id=ctx.target_user_id,
            boss=parsed.boss,
            text=remark,
            viewer_id=viewer_id,
            account_id=account_id,
        )
    )
    await notify_display_data_changed(ev.group_id, "apply")
    sl_used = False
    if acc:
        sl_used = await pcr_sqla.check_sl_viewer(acc.viewer_id, ev.group_id)
    else:
        sl_used = await pcr_sqla.check_sl(ctx.target_user_id, ev.group_id)
    clan_info = clanbattle_info.get(ev.group_id)
    msg = await build_apply_success_message(
        bot,
        ev.group_id,
        parsed.boss,
        operator_id=ctx.operator_id,
        target_user_id=ctx.target_user_id,
        viewer_id=acc.viewer_id if acc else None,
        account_slot=acc.slot if acc else None,
        account_name=acc.name if acc else None,
        declared_comp=declared_comp,
        clan_info=clan_info,
        sl_used=sl_used,
    )
    logger.info(
        "申请: group={} boss={} viewer={} user={} bound={}",
        ev.group_id,
        parsed.boss,
        viewer_id,
        ctx.target_user_id,
        bool(acc),
    )
    await bot.send(ev, msg)


async def _handle_drop(bot: HoshinoBot, ev: CQEvent, *, is_comp: bool) -> None:
    if not require_group(ev):
        return
    ctx = await build_context(
        bot, ev, command_key="drop_comp" if is_comp else "drop"
    )
    cmd = "掉刀b" if is_comp else "掉刀"
    slot_parse = parse_account_slot_command(ctx.plain, cmd)
    if not slot_parse or not ctx.account:
        await bot.send(ev, unbound_account(await sender_tag(bot, ev)))
        return
    from ..account_service import pick_account

    acc = await pick_account(
        ctx.target_user_id, slot_parse.account_slot, group_id=int(ev.group_id)
    ) or ctx.account
    drop_boss = None
    for boss in range(1, 6):
        if await pcr_sqla.has_apply_for_viewer(ev.group_id, boss, acc.viewer_id):
            drop_boss = boss
            break
    if drop_boss:
        await pcr_sqla.delete_apply_by_viewer(ev.group_id, drop_boss, acc.viewer_id)
    else:
        await clear_user_applies(ev.group_id, ctx.target_user_id)
    await challenge_service.on_self_report(ev.group_id, drop_boss)
    await knife_budget_service.record_drop(acc.viewer_id, is_comp=is_comp)
    await notify_display_data_changed(ev.group_id, "drop")
    sender = await sender_tag(bot, ev)
    points = "0.5" if is_comp else "1.0"
    logger.info("掉刀: group={} viewer={} comp={}", ev.group_id, acc.viewer_id, is_comp)
    await bot.send(
        ev,
        f"{format_member_account_tag(acc.slot, acc.name, acc.viewer_id)}\n掉刀已记录，已扣除{points}点出刀点数 {sender}",
    )


def register_apply_handlers(sv) -> None:
    @sv.on_rex(proxy_rex(REX_SL))
    async def addsl(bot: HoshinoBot, ev: CQEvent):
        if not require_group(ev):
            return
        ctx = await build_context(bot, ev, command_key="sl")
        slot_parse = parse_account_slot_command(ctx.plain, r"(?:sl|SL|Sl)")
        if not slot_parse:
            return
        sender = await sender_tag(bot, ev)
        acc = ctx.account
        if slot_parse.account_slot and acc:
            from ..account_service import pick_account

            picked = await pick_account(
                ctx.target_user_id, slot_parse.account_slot, group_id=int(ev.group_id)
            )
            if picked:
                acc = picked
        if acc:
            header = format_member_account_tag(acc.slot, acc.name, acc.viewer_id)
            if await pcr_sqla.check_sl_viewer(acc.viewer_id, ev.group_id):
                await bot.send(ev, f"{header}\n今天已经SL过了 {sender}")
                return
            if await pcr_sqla.add_sl_viewer(ev.group_id, acc.viewer_id):
                await clear_user_sl_challenge(ev.group_id, ctx.target_user_id)
                await notify_display_data_changed(ev.group_id, "sl")
                logger.info("SL: group={} viewer={}", ev.group_id, acc.viewer_id)
                await bot.send(
                    ev,
                    f"{header}\nSL已记录，已清除申请出刀与挂树记录 {sender}",
                )
            else:
                await bot.send(ev, f"{header}\n今天已经SL过了 {sender}")
            return
        if await pcr_sqla.check_sl(ctx.target_user_id, ev.group_id):
            await bot.send(ev, f"今天已经SL过了 {sender}")
            return
        if await pcr_sqla.add_sl(
            SLDao(group_id=ev.group_id, user_id=ctx.target_user_id, time=int(time.time()))
        ):
            await clear_user_sl_challenge(ev.group_id, ctx.target_user_id)
            await notify_display_data_changed(ev.group_id, "sl")
            logger.info("SL(无绑): group={} user={}", ev.group_id, ctx.target_user_id)
            await bot.send(ev, f"SL已记录，已清除申请出刀与挂树记录 {sender}")
        else:
            await bot.send(ev, f"今天已经SL过了 {sender}")

    @sv.on_rex(proxy_rex(REX_SL_QUERY))
    async def issl(bot: HoshinoBot, ev: CQEvent):
        if not require_group(ev):
            return
        ctx = await build_context(bot, ev, command_key="sl_query")
        slot_parse = parse_sl_query_command(ctx.plain)
        if not slot_parse:
            return
        sender = await sender_tag(bot, ev)
        acc = ctx.account
        if slot_parse.account_slot and acc:
            from ..account_service import pick_account

            picked = await pick_account(
                ctx.target_user_id, slot_parse.account_slot, group_id=int(ev.group_id)
            )
            if picked:
                acc = picked
        if acc:
            header = format_member_account_tag(acc.slot, acc.name, acc.viewer_id)
            if await pcr_sqla.check_sl_viewer(acc.viewer_id, ev.group_id):
                await bot.send(ev, f"{header}\n今天已经SL过了 {sender}")
            else:
                await bot.send(ev, f"{header}\n今天还没有使用过SL {sender}")
            return
        if await pcr_sqla.check_sl(ctx.target_user_id, ev.group_id):
            await bot.send(ev, f"今天已经SL过了 {sender}")
        else:
            await bot.send(ev, f"今天还没有使用过SL {sender}")

    @sv.on_rex(proxy_rex(REX_APPLY))
    async def apply(bot: HoshinoBot, ev: CQEvent):
        await _handle_apply(bot, ev)

    @sv.on_rex(proxy_rex(REX_CANCEL_APPLY))
    async def cancel_apply(bot: HoshinoBot, ev: CQEvent):
        if not require_group(ev):
            return
        ctx = await build_context(bot, ev, command_key="cancel_apply")
        parsed = parse_cancel_apply(ctx.plain)
        if parsed is None:
            return
        n = await clear_user_applies(ev.group_id, ctx.target_user_id, parsed.boss)
        await notify_display_data_changed(ev.group_id, "cancel_apply")
        sender = await sender_tag(bot, ev)
        if n <= 0:
            await bot.send(ev, f"未找到可取消的申请出刀记录 {sender}")
        else:
            await bot.send(ev, f"已取消申请出刀记录 {sender}")

    @sv.on_rex(proxy_rex(r"取消挂树"))
    async def cancel_tree(bot: HoshinoBot, ev: CQEvent):
        if not require_group(ev):
            return
        ctx = await build_context(bot, ev, command_key="cancel_tree")
        if not parse_cancel_tree(ctx.plain):
            return
        from ..account_service import list_bound_accounts

        accounts = await list_bound_accounts(
            ctx.target_user_id, group_id=int(ev.group_id)
        )
        viewer_ids = [a.viewer_id for a in accounts if a.viewer_id]
        sender = await sender_tag(bot, ev)
        tree_row = await pcr_sqla.find_user_tree_notice(
            ev.group_id, ctx.target_user_id, viewer_ids=viewer_ids
        )
        if not tree_row:
            logger.info(
                "取消挂树: group={} user={} 无挂树记录",
                ev.group_id,
                ctx.target_user_id,
            )
            await bot.send(ev, f"未找到挂树记录 {sender}")
            return
        n = await pcr_sqla.delete_user_tree_notices(ev.group_id, ctx.target_user_id)
        await notify_display_data_changed(ev.group_id, "cancel_tree")
        logger.info(
            "取消挂树: group={} user={} boss={} deleted={}",
            ev.group_id,
            ctx.target_user_id,
            tree_row.boss,
            n,
        )
        await bot.send(ev, f"已取消挂树 {sender}")

    @sv.on_rex(proxy_rex(REX_TREE))
    async def tree_apply(bot: HoshinoBot, ev: CQEvent):
        if not require_group(ev):
            return
        ctx = await build_context(bot, ev, command_key="tree")
        parsed = parse_tree(ctx.plain)
        sender = await sender_tag(bot, ev)
        if not parsed:
            logger.debug("挂树: group={} user={} 解析失败 plain={}", ev.group_id, ctx.target_user_id, ctx.plain)
            await bot.send(ev, tree_format_error(sender))
            return
        from ..account_service import list_bound_accounts

        accounts = await list_bound_accounts(
            ctx.target_user_id, group_id=int(ev.group_id)
        )
        viewer_ids = [a.viewer_id for a in accounts if a.viewer_id]
        boss = parsed.boss
        if boss is None:
            apply_row = await pcr_sqla.find_user_active_apply(
                ev.group_id, ctx.target_user_id, viewer_ids=viewer_ids
            )
            if not apply_row or not apply_row.boss:
                logger.info(
                    "挂树: group={} user={} 无进行中申请",
                    ev.group_id,
                    ctx.target_user_id,
                )
                await bot.send(ev, f"您没有申请出刀记录，请先申请出刀 {sender}")
                return
            boss = int(apply_row.boss)
            logger.debug(
                "挂树: group={} user={} 从申请推断 boss={}",
                ev.group_id,
                ctx.target_user_id,
                boss,
            )
        has_apply = await pcr_sqla.has_apply_for_user(
            ev.group_id, boss, ctx.target_user_id
        )
        if not has_apply:
            for a in accounts:
                if await pcr_sqla.has_apply_for_viewer(
                    ev.group_id, boss, a.viewer_id
                ):
                    has_apply = True
                    break
        if not has_apply:
            logger.info(
                "挂树: group={} user={} boss={} 无该王申请",
                ev.group_id,
                ctx.target_user_id,
                boss,
            )
            await bot.send(ev, f"您没有申请出刀记录，请先申请出刀 {sender}")
            return
        if await pcr_sqla.has_tree_for_user(
            ev.group_id, ctx.target_user_id, boss, viewer_ids=viewer_ids
        ):
            logger.info(
                "挂树: group={} user={} boss={} 已挂树",
                ev.group_id,
                ctx.target_user_id,
                boss,
            )
            await bot.send(ev, f"您已经挂树了 {sender}")
            return
        acc = ctx.account
        viewer_id = acc.viewer_id if acc else None
        account_id = acc.account_id if acc else None
        await pcr_sqla.add_notice(
            NoticeCache(
                group_id=ev.group_id,
                notice_type=NoticeType.tree.value,
                user_id=ctx.target_user_id,
                boss=boss,
                text=parsed.remark,
                viewer_id=viewer_id,
                account_id=account_id,
            )
        )
        await notify_display_data_changed(ev.group_id, "tree")
        clan_info = clanbattle_info.get(ev.group_id)
        snap = get_boss_snap(clan_info, boss)

        sl_warn = ""
        if acc and await pcr_sqla.check_sl_viewer(acc.viewer_id, ev.group_id):
            sl_warn = "：警告！您今日已使用SL，祝您好运"
        elif not acc and await pcr_sqla.check_sl(ctx.target_user_id, ev.group_id):
            sl_warn = "：警告！您今日已使用SL，祝您好运"
        msg = f"{sender}挂树了"
        if parsed.remark:
            msg += f"：{parsed.remark}"
        if acc and len(accounts) > 1:
            msg += f"\n使用{format_member_account_tag(acc.slot, acc.name, acc.viewer_id)}{sl_warn}"
        elif acc and sl_warn:
            msg += f"\n{sl_warn}"
        elif sl_warn:
            msg += f"\n{sl_warn}"
        if snap:
            msg += f"\n当前{boss}王状态：{format_apply_boss_status_line(snap)}"
        logger.info(
            "挂树: group={} boss={} user={} bound={} remark={}",
            ev.group_id,
            boss,
            ctx.target_user_id,
            bool(acc),
            bool(parsed.remark),
        )
        await bot.send(ev, msg)

    @sv.on_rex(proxy_rex(REX_DROP_KNIFE))
    async def drop_knife(bot: HoshinoBot, ev: CQEvent):
        await _handle_drop(bot, ev, is_comp=False)

    @sv.on_rex(proxy_rex(REX_DROP_KNIFE_B))
    async def drop_comp_knife(bot: HoshinoBot, ev: CQEvent):
        await _handle_drop(bot, ev, is_comp=True)

    @sv.on_rex(strict_rex(REX_CLEAR_POINTS))
    async def clear_knife_budget(bot: HoshinoBot, ev: CQEvent):
        if not require_group(ev):
            return
        plain, _ = strip_trailing_cq_at(ev.message)
        slot_parse = parse_account_slot_command(plain, "清空出刀点数")
        if not slot_parse:
            return
        from ..account_service import pick_account

        acc = await pick_account(
            ev.user_id, slot_parse.account_slot, group_id=int(ev.group_id)
        )
        if not acc:
            await bot.send(ev, unbound_account(await sender_tag(bot, ev)))
            return
        await knife_budget_service.reset_budget(acc.viewer_id)
        logger.info("清空出刀点数: group={} viewer={}", ev.group_id, acc.viewer_id)
        await bot.send(
            ev,
            f"{format_member_account_tag(acc.slot, acc.name, acc.viewer_id)}\n"
            f"今日出刀点数已清空（视为3刀已用尽），可切换下一账号 {await sender_tag(bot, ev)}",
        )

    @sv.on_rex(r"^\s*查树\s*$")
    async def checktree(bot: HoshinoBot, ev: CQEvent):
        if not require_group(ev):
            return
        reply = ""
        for boss in range(1, 6):
            if info := await pcr_sqla.get_notice(NoticeType.tree.value, ev.group_id, boss):
                reply += f"{boss}王树上目前有{len(info)}人\n"
                for idx, player in enumerate(info):
                    player_info = await bot.get_group_member_info(
                        group_id=ev.group_id, user_id=player.user_id
                    )
                    name = qq_display_name(
                        player.user_id,
                        player_info.get("card", ""),
                        player_info.get("nickname", ""),
                    )
                    reply += f"->{idx+1}：{name} {player.text} 已过去{format_time(time.time() - player.time)}\n"
        await bot.send(ev, reply or "目前树上空空如也")
