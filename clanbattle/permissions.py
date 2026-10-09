"""会战指令权限（蓝图统一文案；角色判定见 rbac）。"""
from __future__ import annotations

from hoshino.typing import CQEvent

from ..rbac import is_admin_plus, is_super_admin

PERM_DENIED = "您的权限不足，请联系管理员"


def is_senior_admin(ev: CQEvent) -> bool:
    """超级管理员：仅 setting_clanbattle.admin_qq。"""
    return is_super_admin(ev.user_id)


def is_ops_admin(ev: CQEvent) -> bool:
    """管理员及以上（不含群管 / Hoshino SUPERUSERS）。"""
    return is_admin_plus(ev.user_id)


def can_stop_monitor(ev: CQEvent, monitor_user_id: int) -> bool:
    """仅管理员及以上可关闭监控（监控发起者本人不可单独关闭）。"""
    return is_admin_plus(ev.user_id)


def is_user_in_admin_qqs(user_id: int) -> bool:
    """兼容旧名：会战管理员及以上。"""
    return is_admin_plus(int(user_id))
