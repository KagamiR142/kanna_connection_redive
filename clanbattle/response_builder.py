"""蓝图响应拼装（申请成功、挑战者列表、报刀推送）。"""
from __future__ import annotations

from typing import Dict, List, Optional, TYPE_CHECKING

from hoshino.typing import HoshinoBot
from loguru import logger

from ..challenge.service import challenge_service
from ..knife_budget.service import knife_budget_service
from .account_label import format_member_account_tag
from .account_service import list_member_bound_accounts
from .actor_display import format_damage_push_headline
from .challenging_count_text import format_challenging_count_line
from .queue_display_service import (
    build_damage_push_challenger_lines,
    collect_damage_push_at_qq_ids,
)
from .boss_snapshot import (
    format_apply_boss_status_line,
    format_boss_status_line,
    get_boss_snap,
)
from .damage_push_batch import DamagePushBlock
from .knife_type_text import build_knife_type_sentence
from .text_util import game_display_name, sender_placeholder

if TYPE_CHECKING:
    from .model import ClanBattle

async def build_challenger_lines(
    bot: HoshinoBot,
    group_id: int,
    boss: int,
    *,
    clan_info: Optional["ClanBattle"] = None,
) -> List[str]:
    from .queue_display_service import build_challenger_text_lines

    return await build_challenger_text_lines(bot, group_id, boss)


async def build_apply_success_message(
    bot: HoshinoBot,
    group_id: int,
    boss: int,
    *,
    operator_id: int,
    target_user_id: int,
    viewer_id: Optional[int] = None,
    account_slot: Optional[int] = None,
    account_name: Optional[str] = None,
    declared_comp: bool = False,
    clan_info: Optional["ClanBattle"] = None,
    sl_used: bool = False,
) -> str:
    snap = get_boss_snap(clan_info, boss)
    status_line = (
        f"当前{boss}王状态：{format_apply_boss_status_line(snap)}"
        if snap
        else f"当前{boss}王状态：未开启监控"
    )
    try:
        member = await bot.get_group_member_info(
            group_id=group_id, user_id=operator_id
        )
        sender = sender_placeholder(
            operator_id, member.get("card", ""), member.get("nickname", "")
        )
    except Exception:
        sender = sender_placeholder(operator_id)
    sl_warn = "：警告！您今日已使用SL，祝您好运" if sl_used else ""
    if viewer_id and account_slot is not None and account_name is not None:
        summary = await knife_budget_service.remaining_summary(viewer_id)
        knife_line = build_knife_type_sentence(summary, declared_comp=declared_comp)
        bound = await list_member_bound_accounts(target_user_id, group_id=group_id)
        account_suffix = ""
        if len(bound) > 1:
            account_suffix = (
                f"，使用{format_member_account_tag(account_slot, account_name, viewer_id)}"
            )
        user_line = f"{sender} {knife_line}{account_suffix}{sl_warn}"
    else:
        user_line = f"{sender} 未绑定账号{sl_warn}"
    challengers = await build_challenger_lines(
        bot, group_id, boss, clan_info=clan_info
    )
    state = await challenge_service.get_state(group_id, boss)
    enter_signal = int(state.enter_signal or 0)
    lines = [
        f"申请成功，{status_line}",
        "申请人：",
        user_line,
        format_challenging_count_line(len(challengers), enter_signal),
        *challengers,
    ]
    logger.debug(
        "apply_success: group={} boss={} viewer={} challengers={}",
        group_id,
        boss,
        viewer_id,
        len(challengers),
    )
    return "\n".join(lines)


async def build_damage_push_block(
    bot: HoshinoBot,
    group_id: int,
    boss: int,
    *,
    create_time: int,
    viewer_id: int,
    user_id: int,
    game_name: str,
    lap: int,
    damage: int,
    knife_sentence: str,
    clan_info: Optional["ClanBattle"] = None,
    is_kill: bool = False,
    settler_user_id: int = 0,
) -> DamagePushBlock:
    headline, bound = await format_damage_push_headline(
        bot,
        group_id,
        viewer_id=viewer_id,
        game_name=game_name,
        lap=lap,
        boss=boss,
        damage=damage,
        knife_sentence=knife_sentence,
    )
    snap = get_boss_snap(clan_info, boss)
    status_line = (
        f"当前{boss}王状态：{format_boss_status_line(snap)}"
        if snap
        else f"当前{boss}王状态：未知"
    )
    challengers = await build_damage_push_challenger_lines(
        bot,
        group_id,
        boss,
        settler_user_id=int(settler_user_id or 0),
    )
    post_hp = int(snap.current_hp or 0) if snap else 0
    from .merge_line.service import build_merge_line_push_extras

    at_ids = await collect_damage_push_at_qq_ids(
        group_id,
        boss,
        settler_user_id=int(settler_user_id or 0),
    )
    extras = await build_merge_line_push_extras(
        group_id,
        boss,
        lap=int(lap or 0),
        post_hp=post_hp,
        is_kill=bool(is_kill),
        challenger_count=len(challengers),
        at_qq_ids=at_ids,
    )
    logger.debug(
        "damage_push: group={} boss={} viewer={} qq_bound={} merge_prefix={}",
        group_id,
        boss,
        viewer_id,
        bound,
        bool(extras.prefix),
    )
    state = await challenge_service.get_state(group_id, boss)
    raw_signal = int(state.enter_signal or 0)
    if is_kill:
        in_boss_signal = 0
    else:
        in_boss_signal = max(0, raw_signal - 1)
    return DamagePushBlock(
        boss_order=int(boss),
        create_time=int(create_time or 0),
        headline=headline,
        status_line=status_line,
        challenger_count=len(challengers),
        challenger_lines=challengers,
        boss_enter_signal=in_boss_signal,
        merge_line_prefix=extras.prefix,
        merge_line_suffix=extras.suffix,
    )


async def build_damage_push_message(
    bot: HoshinoBot,
    group_id: int,
    boss: int,
    *,
    viewer_id: int,
    user_id: int,
    game_name: str,
    lap: int,
    damage: int,
    knife_sentence: str,
    clan_info: Optional["ClanBattle"] = None,
    create_time: int = 0,
) -> str:
    block = await build_damage_push_block(
        bot,
        group_id,
        boss,
        create_time=create_time,
        viewer_id=viewer_id,
        user_id=user_id,
        game_name=game_name,
        lap=lap,
        damage=damage,
        knife_sentence=knife_sentence,
        clan_info=clan_info,
    )
    from .damage_push_batch import merge_damage_push_blocks

    return merge_damage_push_blocks([block])


async def resolve_qq_for_viewer(
    group_id: int, viewer_id: int, members: Dict[int, str]
) -> Optional[int]:
    from .actor_display import resolve_qq_user_for_viewer

    return await resolve_qq_user_for_viewer(viewer_id)
