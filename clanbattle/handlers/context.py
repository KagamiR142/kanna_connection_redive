"""QQ 指令 handler 共用工具（文案与行为须与拆分前一致）。"""
from __future__ import annotations

from io import BytesIO
from typing import Dict, Optional

from hoshino.util import pic2b64
from hoshino.typing import CQEvent, HoshinoBot, MessageSegment
from PIL import Image

from ...knife_budget.service import knife_budget_service
from ..registry import clanbattle_info
from ..text_util import qq_display_name, sender_placeholder
from ...challenge.service import challenge_service
from ...database.dal import pcr_sqla


def extract_plain(ev: CQEvent) -> str:
    return ev.message.extract_plain_text().strip()


def require_group(ev: CQEvent) -> bool:
    return bool(ev.group_id)


async def sender_tag(bot: HoshinoBot, ev: CQEvent) -> str:
    """蓝图 @sender：始终指消息操作者。"""
    try:
        member = await bot.get_group_member_info(group_id=ev.group_id, user_id=ev.user_id)
        return sender_placeholder(
            ev.user_id, member.get("card", ""), member.get("nickname", "")
        )
    except Exception:
        return sender_placeholder(ev.user_id)


async def send_report_payload(bot: HoshinoBot, ev: CQEvent, payload) -> None:
    """文本错误或 PNG bytes。"""
    if isinstance(payload, str):
        await bot.send(ev, payload)
        return
    img = Image.open(BytesIO(payload))
    await bot.send(ev, MessageSegment.image(pic2b64(img)))


async def build_pcrid_qq_map(bot: HoshinoBot, group_id: int) -> Dict[int, str]:
    """pcrid → QQ 显示名，仅 user_account 已绑定的成员。"""
    from ..member_identity import viewer_to_member_qq

    result: Dict[int, str] = {}
    clan = clanbattle_info.get(group_id)
    if not clan:
        return result
    for vid in clan.members:
        qq_id = await viewer_to_member_qq(vid)
        if not qq_id:
            continue
        try:
            member = await bot.get_group_member_info(group_id=group_id, user_id=qq_id)
            result[vid] = qq_display_name(
                qq_id,
                member.get("card", ""),
                member.get("nickname", ""),
            )
        except Exception:
            result[vid] = qq_display_name(qq_id)
    return result


async def account_has_comp(viewer_id: int) -> bool:
    from ..apply_knife_presentation import account_has_comp_resources

    summary = await knife_budget_service.remaining_summary(viewer_id)
    return account_has_comp_resources(summary)


async def clear_user_applies(
    group_id: int, user_id: int, boss: Optional[int] = None
) -> int:
    return await pcr_sqla.delete_user_applies(group_id, user_id, boss)


async def clear_user_sl_challenge(group_id: int, user_id: int) -> None:
    await pcr_sqla.delete_user_applies(group_id, user_id)
    await pcr_sqla.delete_user_tree_notices(group_id, user_id)
    await challenge_service.on_self_report(group_id)
