"""结算/报刀展示行：QQ 绑定与仅游戏名降级（全模块复用）。"""
from __future__ import annotations

from typing import Optional, Tuple

from hoshino.typing import HoshinoBot

from .account_label import resolve_primary_binding
from .account_service import viewer_to_slot
from .member_identity import is_monitor_viewer, viewer_to_member_qq
from .text_util import game_display_name, qq_display_name


async def resolve_qq_user_for_viewer(viewer_id: int) -> Optional[int]:
    return await viewer_to_member_qq(viewer_id)


async def format_damage_push_headline(
    bot: HoshinoBot,
    group_id: int,
    *,
    viewer_id: int,
    game_name: str,
    lap: int,
    boss: int,
    damage: int,
    knife_sentence: str,
) -> Tuple[str, bool]:
    """返回 (首行文案, 是否有 QQ 成员绑定)。"""
    name_display = game_display_name(game_name or "角色", viewer_id)
    user_id = await viewer_to_member_qq(viewer_id)
    dmg_part = f"对{lap}周目{boss}王造成了{damage}点伤害"
    if not user_id:
        suffix = "，" + knife_sentence if knife_sentence else ""
        if await is_monitor_viewer(viewer_id):
            line = f"{name_display}（监控）{dmg_part}{suffix}。"
        elif knife_sentence:
            line = f"{name_display}{dmg_part}，{knife_sentence}。"
        else:
            line = f"{name_display}{dmg_part}。"
        return line, False
    slot = await viewer_to_slot(user_id, viewer_id)
    try:
        member = await bot.get_group_member_info(group_id=group_id, user_id=user_id)
        user_display = qq_display_name(
            user_id, member.get("card", ""), member.get("nickname", "")
        )
    except Exception:
        user_display = qq_display_name(user_id)
    binding = await resolve_primary_binding(bot, group_id, viewer_id)
    if binding and binding.n_accounts > 1 and slot:
        who = f"{user_display}-{slot}-{name_display}"
    else:
        who = user_display
    line = (
        f"{who}对{lap}周目{boss}王造成了{damage}点伤害，"
        f"{knife_sentence}。"
    )
    return line, True
