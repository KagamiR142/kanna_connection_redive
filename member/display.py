from typing import Optional

from hoshino.typing import HoshinoBot

from ..clanbattle.member_identity import resolve_member_display_name
from ..clanbattle.text_util import game_display_name, qq_display_name


async def get_group_nickname(
    bot: HoshinoBot, group_id: int, user_id: int, fallback: str = ""
) -> str:
    try:
        info = await bot.get_group_member_info(group_id=group_id, user_id=user_id)
        return qq_display_name(
            user_id, info.get("card", ""), info.get("nickname", "")
        )
    except Exception:
        return qq_display_name(user_id, fallback)


async def format_actor_label(
    bot: HoshinoBot,
    group_id: int,
    user_id: int,
    account_id: Optional[int] = None,
    viewer_id: Optional[int] = None,
) -> str:
    """兼容旧调用；新逻辑请用 format_queue_actor_label。"""
    return await format_queue_actor_label(
        bot, group_id, user_id, account_id=account_id, viewer_id=viewer_id
    )


async def format_queue_actor_label(
    bot: HoshinoBot,
    group_id: int,
    user_id: int,
    account_id: Optional[int] = None,
    viewer_id: Optional[int] = None,
) -> str:
    """有绑定：仅游戏名（与 pick_member_account / resolve_member_display_name 同源）；无绑定：群昵称。"""
    resolved_viewer = viewer_id
    if account_id:
        from ..database.dal import pcr_sqla

        for row in await pcr_sqla.query_user_accounts(user_id):
            if int(row.account_id or 0) == int(account_id):
                resolved_viewer = row.viewer_id or resolved_viewer
                break

    if resolved_viewer:
        name = await resolve_member_display_name(
            int(resolved_viewer),
            group_id=int(group_id) if group_id else None,
            user_id=int(user_id),
        )
        return game_display_name(name, int(resolved_viewer))

    return await get_group_nickname(bot, group_id, user_id)
