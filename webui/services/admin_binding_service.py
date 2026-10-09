"""管理运维：QQ↔UID 聚合列表与批量代绑。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from loguru import logger

from ...clanbattle.member_identity import (
    compact_user_binding_sort_orders,
    display_slot,
    locale_sort_key,
    resolve_member_display_name,
)
from ...database.dal import pcr_sqla
from .binding_service import admin_remove_binding, admin_set_binding
from .clan_accounts_service import fetch_clan_member_options
from .guild_membership_service import fetch_qq_group_members


async def list_bindings_grouped(
    group_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    rows = await pcr_sqla.list_user_account_bindings()
    viewer_names: Dict[int, str] = {}
    qq_filter: Optional[set[int]] = None
    qq_labels: Dict[int, str] = {}
    if group_id is not None:
        gid = int(group_id)
        qq_members = await fetch_qq_group_members(gid)
        qq_filter = {int(m["user_id"]) for m in qq_members}
        qq_labels = {int(m["user_id"]): m["display_name"] for m in qq_members}
        try:
            for m in await fetch_clan_member_options(gid):
                viewer_names[int(m["viewer_id"])] = str(m.get("name") or "")
        except ValueError:
            logger.warning("聚合绑定列表时 clan-accounts 不可用 group={}", gid)

    by_user: Dict[int, List[Dict[str, Any]]] = {}
    for row in rows:
        uid = int(row.user_id)
        if qq_filter is not None and uid not in qq_filter:
            continue
        vid = int(row.viewer_id or 0)
        name = viewer_names.get(vid)
        if not name:
            name = await resolve_member_display_name(
                vid, group_id=group_id, user_id=uid
            )
        slot = display_slot(row.sort_order)
        by_user.setdefault(uid, []).append(
            {
                "id": int(row.id or 0),
                "viewer_id": vid,
                "name": name,
                "slot": slot,
                "sort_order": int(row.sort_order or 0),
                "account_id": int(row.account_id or 0),
            }
        )

    result: List[Dict[str, Any]] = []
    for user_id, bindings in sorted(by_user.items(), key=lambda x: x[0]):
        bindings.sort(key=lambda b: (b["sort_order"], b["viewer_id"]))
        result.append(
            {
                "user_id": user_id,
                "qq_display_name": qq_labels.get(user_id) or str(user_id),
                "bindings": bindings,
            }
        )
    result.sort(
        key=lambda g: locale_sort_key(str(g.get("qq_display_name") or ""))
    )
    return result


async def list_binding_index() -> Dict[str, List[int]]:
    """Admin 灰显：已有绑定的 QQ / UID 集合。"""
    rows = await pcr_sqla.list_user_account_bindings()
    qq_ids: set[int] = set()
    viewer_ids: set[int] = set()
    for row in rows:
        qq_ids.add(int(row.user_id))
        if row.viewer_id:
            viewer_ids.add(int(row.viewer_id))
    return {
        "bound_user_ids": sorted(qq_ids),
        "bound_viewer_ids": sorted(viewer_ids),
    }


async def admin_batch_bind(
    user_ids: List[int],
    viewer_ids: List[int],
    *,
    group_id: Optional[int],
    actor_user_id: int,
) -> Dict[str, Any]:
    ok = 0
    skipped = 0
    failed: List[Dict[str, Any]] = []
    touched_users: set[int] = set()
    for u in user_ids:
        for v in viewer_ids:
            try:
                status = await admin_set_binding(
                    int(u),
                    int(v),
                    group_id=group_id,
                    actor_user_id=actor_user_id,
                    multi=True,
                )
                if status == "skipped":
                    skipped += 1
                else:
                    ok += 1
                    touched_users.add(int(u))
            except ValueError as e:
                failed.append(
                    {"user_id": int(u), "viewer_id": int(v), "error": str(e)}
                )
            except Exception as e:
                logger.exception(
                    "批量代绑异常 user={} viewer={}", u, v
                )
                failed.append(
                    {"user_id": int(u), "viewer_id": int(v), "error": str(e)}
                )
    for uid in touched_users:
        await compact_user_binding_sort_orders(uid)
    logger.info(
        "批量代绑: group={} pairs_ok={} failed={} by={}",
        group_id,
        ok,
        len(failed),
        actor_user_id,
    )
    return {"ok": ok, "skipped": skipped, "failed": failed}
