"""QQ 群成员（ClanBattleMember）与 OneBot 群信息 — Web / 群指令共用。"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from loguru import logger

from ...database.dal import pcr_sqla
from ...database.models import ClanBattleMember
from ..util import call_in_main_loop
from ...clanbattle.text_util import locale_sort_key

if TYPE_CHECKING:
    from hoshino.typing import HoshinoBot

_GROUP_NAME_CACHE: Dict[int, tuple[float, str]] = {}
_QQ_MEMBERS_CACHE: Dict[int, tuple[float, List[Dict[str, Any]]]] = {}
_TTL = 600
_PLACEHOLDER_NAMES = frozenset({"环奈连结", ""})


def format_group_fallback(group_id: int) -> str:
    return f"公会 {int(group_id)}"


async def onebot_group_name_on_bot(bot: "HoshinoBot", group_id: int) -> str:
    """主循环内调用：OneBot get_group_info。"""
    gid = int(group_id)
    try:
        info = await bot.call_action("get_group_info", group_id=gid)
        name = str((info or {}).get("group_name") or "").strip()
        if name:
            _GROUP_NAME_CACHE[gid] = (time.time(), name)
            return name
    except Exception as e:
        logger.warning("get_group_info 失败 group={}: {}", gid, e)
    return ""


async def resolve_group_display_name(
    group_id: int,
    stored_name: Optional[str] = None,
    *,
    bot: Optional["HoshinoBot"] = None,
) -> str:
    """真实群名片；失败时用 stored（非占位）或 `公会 {id}`。"""
    gid = int(group_id)
    if stored_name and stored_name not in _PLACEHOLDER_NAMES:
        return stored_name
    now = time.time()
    if gid in _GROUP_NAME_CACHE and now - _GROUP_NAME_CACHE[gid][0] < _TTL:
        return _GROUP_NAME_CACHE[gid][1]
    name = ""
    if bot is not None:
        name = await onebot_group_name_on_bot(bot, gid)
    else:

        async def _run() -> str:
            import nonebot

            b = nonebot.get_bot()
            return await onebot_group_name_on_bot(b, gid)

        try:
            name = await call_in_main_loop(_run())
        except Exception as e:
            logger.warning("Web 拉群名失败 group={}: {}", gid, e)
            name = ""
    if name:
        return name
    if stored_name and stored_name not in _PLACEHOLDER_NAMES:
        return stored_name
    return format_group_fallback(gid)


def invalidate_qq_members_cache(group_id: int) -> None:
    _QQ_MEMBERS_CACHE.pop(int(group_id), None)


async def list_admin_binding_groups() -> List[Dict[str, Any]]:
    """Admin 工作台可选运维群：本群成员绑定 + 当前监控群。"""
    from ...clanbattle.registry import clanbattle_info

    seen: Dict[int, str] = {}
    for m in await pcr_sqla.get_bound_groups():
        gid = int(m.group_id)
        gname = str(m.group_name or "").strip()
        if gid not in seen or (gname and gname not in _PLACEHOLDER_NAMES):
            seen[gid] = gname
    for gid, info in clanbattle_info.items():
        igid = int(gid)
        if igid not in seen:
            seen[igid] = str(getattr(info, "clan_name", "") or "")
    out: List[Dict[str, Any]] = []
    for gid, gname in seen.items():
        display = (
            gname
            if gname and gname not in _PLACEHOLDER_NAMES
            else format_group_fallback(gid)
        )
        out.append({"group_id": gid, "group_name": display})
    out.sort(key=lambda x: (locale_sort_key(x["group_name"]), x["group_id"]))
    logger.debug("Admin 绑定群列表: count={}", len(out))
    return out


async def bind_user_to_clan_group(
    group_id: int,
    user_id: int,
    *,
    bot: Optional["HoshinoBot"] = None,
    priority: int = 0,
) -> str:
    """写入 ClanBattleMember；不要求 user_account / Account。"""
    gid, uid = int(group_id), int(user_id)
    display = await resolve_group_display_name(gid, bot=bot)
    await pcr_sqla.add_member(
        ClanBattleMember(
            group_id=gid,
            user_id=uid,
            group_name=display,
            priority=int(priority or 0),
        )
    )
    logger.info(
        "绑定本群公会: group={} user={} group_name={}",
        gid,
        uid,
        display,
    )
    invalidate_qq_members_cache(gid)
    try:
        await fetch_qq_group_members(gid)
        logger.debug("绑定本群公会后预拉 QQ 成员: group={}", gid)
    except Exception as e:
        logger.warning("绑定本群公会后预拉成员失败 group={}: {}", gid, e)
    return display


async def unbind_user_from_clan_group(group_id: int, user_id: int) -> None:
    gid, uid = int(group_id), int(user_id)
    await pcr_sqla.delete_member(gid, uid)
    logger.info("删除本群公会绑定: group={} user={}", gid, uid)


def _normalize_qq_member(raw: Dict[str, Any]) -> Dict[str, Any]:
    uid = int(raw.get("user_id") or raw.get("userid") or 0)
    card = str(raw.get("card") or "").strip()
    nick = str(raw.get("nickname") or raw.get("nick") or "").strip()
    label = card or nick or str(uid)
    return {
        "user_id": uid,
        "nickname": nick,
        "card": card,
        "display_name": label,
    }


async def fetch_qq_group_members(group_id: int) -> List[Dict[str, Any]]:
    """OneBot 群成员列表（Web 管理端）；短缓存。"""
    gid = int(group_id)
    now = time.time()
    if gid in _QQ_MEMBERS_CACHE and now - _QQ_MEMBERS_CACHE[gid][0] < _TTL:
        return _QQ_MEMBERS_CACHE[gid][1]

    async def _run() -> List[Dict[str, Any]]:
        import nonebot

        bot = nonebot.get_bot()
        resp = await bot.call_action("get_group_member_list", group_id=gid)
        if isinstance(resp, list):
            rows = resp
        elif isinstance(resp, dict):
            rows = resp.get("data") or resp.get("members") or []
        else:
            rows = []
        out = [_normalize_qq_member(r) for r in rows if r]
        out = [m for m in out if m["user_id"] > 0]
        out.sort(
            key=lambda m: (locale_sort_key(m["display_name"]), m["user_id"])
        )
        return out

    members = await call_in_main_loop(_run())
    _QQ_MEMBERS_CACHE[gid] = (now, members)
    logger.debug("QQ 群成员列表: group={} count={}", gid, len(members))
    return members
