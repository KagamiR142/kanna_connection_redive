"""会战 Web/QQ 统一角色（超级管理员 = admin_qq；管理员 ≤5；与群管/SUPERUSERS 无关）。"""
from __future__ import annotations

import time
from enum import Enum
from typing import List, Set

from fastapi import HTTPException, status
from loguru import logger

from .clanbattle_setting import get_clanbattle_settings
from .database.dal import pcr_sqla

MAX_DELEGATED_ADMINS = 5
_delegated_cache: Set[int] = set()


class KcrRole(str, Enum):
    user = "user"
    admin = "admin"
    super_admin = "super_admin"


def super_admin_qq() -> int:
    return int(get_clanbattle_settings().admin_qq or 0)


def is_super_admin(qq_id: int) -> bool:
    s = super_admin_qq()
    return s > 0 and int(qq_id) == s


def is_delegated_admin(qq_id: int) -> bool:
    return int(qq_id) in _delegated_cache


def is_admin_plus(qq_id: int) -> bool:
    return is_super_admin(qq_id) or is_delegated_admin(qq_id)


async def resolve_role(qq_id: int) -> KcrRole:
    qq_id = int(qq_id)
    if is_super_admin(qq_id):
        return KcrRole.super_admin
    if is_delegated_admin(qq_id):
        return KcrRole.admin
    return KcrRole.user


async def refresh_delegated_cache() -> None:
    global _delegated_cache
    rows = await pcr_sqla.list_kcr_delegated_admin_qqs()
    _delegated_cache = {int(x) for x in rows}
    logger.debug("RBAC 委派管理员缓存已刷新: count={}", len(_delegated_cache))


async def migrate_legacy_admin_qqs() -> None:
    """一次性：将 setting 中废弃的 admin_qqs 迁入数据库（不含超级管理员本人）。"""
    cfg = get_clanbattle_settings()
    super_qq = super_admin_qq()
    if not cfg.admin_qqs:
        return
    existing = await pcr_sqla.list_kcr_delegated_admin_qqs()
    if existing:
        return
    for raw in cfg.admin_qqs:
        qq = int(raw)
        if qq <= 0 or qq == super_qq:
            continue
        try:
            await appoint_delegated_admin(qq, appointed_by=super_qq, skip_super_check=True)
        except ValueError as e:
            logger.warning("迁移 admin_qqs 跳过 qq={}: {}", qq, e)
    logger.info("已从 admin_qqs 迁移委派管理员 {} 人", len(_delegated_cache))


async def bootstrap_rbac() -> None:
    await migrate_legacy_admin_qqs()
    await refresh_delegated_cache()


async def appoint_delegated_admin(
    qq_id: int,
    *,
    appointed_by: int,
    skip_super_check: bool = False,
) -> None:
    qq_id = int(qq_id)
    if not skip_super_check and not is_super_admin(appointed_by):
        raise PermissionError("仅超级管理员可任命管理员")
    if is_super_admin(qq_id):
        raise ValueError("不能将超级管理员加入委派列表")
    if qq_id in _delegated_cache:
        raise ValueError("该 QQ 已是管理员")
    count = await pcr_sqla.count_kcr_delegated_admins()
    if count >= MAX_DELEGATED_ADMINS:
        raise ValueError(f"管理员已达上限 {MAX_DELEGATED_ADMINS} 人")
    await pcr_sqla.add_kcr_delegated_admin(
        qq_id, appointed_by=int(appointed_by), appointed_at=int(time.time())
    )
    _delegated_cache.add(qq_id)
    logger.info("任命管理员: qq={} by={}", qq_id, appointed_by)


async def revoke_delegated_admin(qq_id: int, *, revoked_by: int) -> None:
    if not is_super_admin(revoked_by):
        raise PermissionError("仅超级管理员可撤销管理员")
    qq_id = int(qq_id)
    if not await pcr_sqla.remove_kcr_delegated_admin(qq_id):
        raise ValueError("该 QQ 不在管理员列表中")
    _delegated_cache.discard(qq_id)
    logger.info("撤销管理员: qq={} by={}", qq_id, revoked_by)


async def list_delegated_admins() -> List[dict]:
    return await pcr_sqla.list_kcr_delegated_admin_rows()


def require_admin_plus_http(qq_id: int) -> None:
    if not is_admin_plus(qq_id):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "需要会战管理员权限（超级管理员或已任命的管理员）",
        )


def require_super_admin_http(qq_id: int) -> None:
    if not is_super_admin(qq_id):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "需要超级管理员权限（setting_clanbattle.admin_qq）",
        )
