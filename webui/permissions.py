"""Web 端群内权限与访问控制（从 util.py 抽取，行为不变）。"""
from __future__ import annotations

import time
from typing import Dict, Optional, Tuple

from fastapi import Depends, HTTPException, status

from ..basedata import GroupPriority
from ..database.dal import pcr_sqla
from ..database.models import ClanBattleMember, CookieCache
from ..rbac import is_admin_plus, require_admin_plus_http
from .session import call_in_main_loop, verify_cookie

# 群内角色缓存 {(group_id, user_id): (role, 过期时间)}
_GROUP_ROLE_CACHE: Dict[Tuple[int, int], Tuple[str, float]] = {}
_GROUP_ROLE_TTL = 600
_GROUP_ROLE_FAIL_TTL = 60
_GROUP_ROLE_CACHE_MAX = 4096
_OWNER_ROLES = ("owner", "admin", "administrator")


def is_bot_owner(user_id: int) -> bool:
    """是否是 bot 主人（hoshino.config.SUPERUSERS 里的 QQ）"""
    try:
        from hoshino import config

        superusers = getattr(config, "SUPERUSERS", None) or []
        return int(user_id) in {int(q) for q in superusers}
    except Exception:
        return False


async def fetch_group_role(group_id: int, user_id: int) -> str:
    """查询某人在某群里的角色：'owner' / 'admin' / 'member'；查不到返回空串。"""
    from nonebot import logger

    now = time.time()
    key = (int(group_id), int(user_id))
    if cached := _GROUP_ROLE_CACHE.get(key):
        role, expire = cached
        if now < expire:
            return role

    role = ""
    try:
        import nonebot

        bot = nonebot.get_bot()
        info = await call_in_main_loop(
            bot.call_action(
                "get_group_member_info", group_id=int(group_id), user_id=int(user_id)
            )
        )
        role = str((info or {}).get("role") or "")
    except Exception as e:
        logger.warning(f"查询群成员角色失败 group={group_id} user={user_id}: {e}")

    if role in _OWNER_ROLES or role == "member":
        expire = now + _GROUP_ROLE_TTL
    else:
        role = ""
        expire = now + _GROUP_ROLE_FAIL_TTL

    if len(_GROUP_ROLE_CACHE) >= _GROUP_ROLE_CACHE_MAX:
        _GROUP_ROLE_CACHE.clear()
    _GROUP_ROLE_CACHE[key] = (role, expire)
    return role


async def is_group_manager_in(group_id: int, user_id: int) -> bool:
    """某人是不是这个群的群主 / 群管（用于自动发现「我管理的群」）"""
    return await fetch_group_role(group_id, user_id) in _OWNER_ROLES


async def get_member_row(user_id: int, group_id: int) -> Optional[ClanBattleMember]:
    """取该用户在该群的成员绑定记录（没发过【绑定本群公会】则返回 None）"""
    for member in await pcr_sqla.get_member_group(int(user_id)):
        if int(member.group_id) == int(group_id):
            return member
    return None


async def effective_group_priority(user_id: int, group_id: int) -> int:
    """算出某人在某个群里的实际权限等级（basedata.GroupPriority）"""
    user_id, group_id = int(user_id), int(group_id)
    if is_bot_owner(user_id):
        return GroupPriority.bot_owner.value

    level = GroupPriority.member.value
    if web_user := await pcr_sqla.web_query_user(str(user_id)):
        level = max(level, int(getattr(web_user, "priority", 0) or 0))
    if (member := await get_member_row(user_id, group_id)) is not None:
        level = max(level, int(getattr(member, "priority", 0) or 0))
    if await fetch_group_role(group_id, user_id) in _OWNER_ROLES:
        level = max(level, GroupPriority.group_admin.value)
    return min(level, GroupPriority.bot_owner.value)


async def ensure_group_access(user_id: int, group_id: int) -> None:
    """校验登录用户能否访问指定群的数据。"""
    user_id, group_id = int(user_id), int(group_id)
    if is_bot_owner(user_id):
        return
    if await get_member_row(user_id, group_id) is not None:
        return
    if await fetch_group_role(group_id, user_id) in _OWNER_ROLES:
        return
    raise HTTPException(
        status.HTTP_403_FORBIDDEN,
        "您不是该群成员，无权访问该群数据（请先在群里发送【绑定本群公会】）",
    )


async def require_group_priority(
    user_id: int, group_id: int, need: int, action: str
) -> int:
    """要求某人在某群里至少有 need 级权限，不够就 403；返回实际等级"""
    level = await effective_group_priority(user_id, group_id)
    if level < need:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"权限不足：{action}需要 {need} 级权限，您当前 {level} 级。"
            "群主 / 群管理会自动获得 2 级，其他情况请让 bot 主人用【网页权限】授权。",
        )
    return level


async def verify_group_access(
    group_id: int, token: CookieCache = Depends(verify_cookie)
) -> CookieCache:
    """带群归属校验的登录态依赖：/{group_id}/... 系列路由用它替代 verify_cookie。"""
    await ensure_group_access(int(token.user_id), group_id)
    return token


async def is_web_ops_admin(user_id: int, group_id: int = 0) -> bool:
    """Web 端「管理员及以上」（与群管 / bot 主人无关，见 rbac）。"""
    return is_admin_plus(int(user_id))


async def require_web_ops_admin(user_id: int, group_id: int = 0) -> None:
    require_admin_plus_http(int(user_id))
