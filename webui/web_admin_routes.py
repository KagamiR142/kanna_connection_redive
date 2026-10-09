"""Web 管理运维 API（Cookie + 会战 RBAC）。"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from ..clanbattle import clanbattle_info
from ..database.dal import pcr_sqla
from ..database.models import CookieCache
from ..rbac import (
    appoint_delegated_admin,
    is_super_admin,
    list_delegated_admins,
    require_admin_plus_http,
    require_super_admin_http,
    revoke_delegated_admin,
)
from .ops_log import append_ops_log, list_ops_logs
from .services.binding_service import admin_remove_binding, admin_set_binding
from .services.admin_binding_service import (
    admin_batch_bind,
    list_binding_index,
    list_bindings_grouped,
)
from .services.guild_membership_service import (
    fetch_qq_group_members,
    list_admin_binding_groups,
)
from .util import verify_cookie

router = APIRouter(prefix="/admin/web")


async def require_kcr_admin(
    token: CookieCache = Depends(verify_cookie),
) -> CookieCache:
    require_admin_plus_http(int(token.user_id))
    return token


async def require_kcr_super(
    token: CookieCache = Depends(verify_cookie),
) -> CookieCache:
    require_super_admin_http(int(token.user_id))
    return token


@router.get("/monitor")
async def web_admin_monitor(_: CookieCache = Depends(require_kcr_admin)):
    result = []
    for gid, info in clanbattle_info.items():
        result.append(
            {
                "group_id": gid,
                "clan_name": info.clan_name,
                "monitor_user_id": info.user_id,
                "loop_num": info.loop_num,
                "active": bool(info.loop_check),
                "lap_num": info.lap_num,
                "period": info.period,
                "rank": info.rank,
            }
        )
    return result


@router.get("/binding-groups")
async def web_admin_binding_groups(
    _: CookieCache = Depends(require_kcr_admin),
):
    return await list_admin_binding_groups()


@router.get("/bindings")
async def web_admin_bindings(
    group_id: Optional[int] = Query(None),
    _: CookieCache = Depends(require_kcr_admin),
):
    return await list_bindings_grouped(group_id)


@router.get("/bindings/index")
async def web_admin_bindings_index(
    _: CookieCache = Depends(require_kcr_admin),
):
    return await list_binding_index()


@router.get("/groups/{group_id}/qq-members")
async def web_admin_qq_members(
    group_id: int,
    _: CookieCache = Depends(require_kcr_admin),
):
    try:
        return await fetch_qq_group_members(int(group_id))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e)) from e


class AdminBatchBindingForm(BaseModel):
    user_ids: List[int]
    viewer_ids: List[int]
    group_id: Optional[int] = None


@router.post("/bindings/batch")
async def web_admin_batch_bindings(
    form: AdminBatchBindingForm,
    token: CookieCache = Depends(require_kcr_admin),
):
    if not form.user_ids or not form.viewer_ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请选择至少一个 QQ 与一个 UID")
    result = await admin_batch_bind(
        form.user_ids,
        form.viewer_ids,
        group_id=form.group_id,
        actor_user_id=int(token.user_id),
    )
    append_ops_log(
        "binding",
        f"批量代绑 ok={result['ok']} fail={len(result['failed'])} group={form.group_id}",
        user_id=int(token.user_id),
        group_id=form.group_id,
    )
    return result


class AdminBindingForm(BaseModel):
    user_id: int
    viewer_id: int
    group_id: Optional[int] = None
    multi: bool = False


@router.put("/bindings")
async def web_admin_put_binding(
    form: AdminBindingForm,
    token: CookieCache = Depends(require_kcr_admin),
):
    try:
        await admin_set_binding(
            int(form.user_id),
            int(form.viewer_id),
            group_id=form.group_id,
            actor_user_id=int(token.user_id),
            multi=form.multi,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    append_ops_log(
        "binding",
        f"代绑 QQ={form.user_id} viewer={form.viewer_id}",
        user_id=int(token.user_id),
        group_id=form.group_id,
    )
    return {"ok": True}


@router.delete("/bindings/{binding_id}")
async def web_admin_delete_binding(
    binding_id: int,
    token: CookieCache = Depends(require_kcr_admin),
):
    await admin_remove_binding(binding_id, actor_user_id=int(token.user_id))
    append_ops_log(
        "binding",
        f"删除绑定 id={binding_id}",
        user_id=int(token.user_id),
    )
    return {"ok": True}


@router.get("/logs")
async def web_admin_logs(
    group_id: Optional[int] = Query(None),
    _: CookieCache = Depends(require_kcr_admin),
):
    return list_ops_logs(group_id)


@router.get("/admins")
async def web_admin_list_delegated(_: CookieCache = Depends(require_kcr_super)):
    return await list_delegated_admins()


class AppointAdminForm(BaseModel):
    qq_id: int


@router.post("/admins")
async def web_admin_appoint(
    form: AppointAdminForm,
    token: CookieCache = Depends(require_kcr_super),
):
    try:
        await appoint_delegated_admin(
            int(form.qq_id), appointed_by=int(token.user_id)
        )
    except (ValueError, PermissionError) as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    append_ops_log(
        "rbac",
        f"任命管理员 {form.qq_id}",
        user_id=int(token.user_id),
    )
    return {"ok": True}


@router.delete("/admins/{qq_id}")
async def web_admin_revoke(
    qq_id: int,
    token: CookieCache = Depends(require_kcr_super),
):
    try:
        await revoke_delegated_admin(int(qq_id), revoked_by=int(token.user_id))
    except (ValueError, PermissionError) as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    append_ops_log(
        "rbac",
        f"撤销管理员 {qq_id}",
        user_id=int(token.user_id),
    )
    return {"ok": True}


@router.get("/me/role")
async def web_admin_my_role(token: CookieCache = Depends(verify_cookie)):
    from ..rbac import is_admin_plus, resolve_role

    uid = int(token.user_id)
    role = await resolve_role(uid)
    return {
        "role": role.value,
        "is_super_admin": is_super_admin(uid),
        "is_admin": is_admin_plus(uid),
    }
