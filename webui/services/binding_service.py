"""Web 端 user_account 绑定（自助 + Admin 代绑；复用 account_service）。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from loguru import logger

from ...clanbattle.account_service import list_bound_accounts
from ...clanbattle.member_identity import compact_user_binding_sort_orders
from ...clanbattle.sl_sync import mirror_qq_sl_to_viewer
from ...clanbattle.text_util import game_display_name
from ...database.dal import pcr_sqla
from ...database.models import UserAccount
from .clan_accounts_service import fetch_clan_member_options


async def _clan_viewer_name_map(group_id: Optional[int]) -> Dict[int, str]:
    if group_id is None:
        return {}
    try:
        out: Dict[int, str] = {}
        for m in await fetch_clan_member_options(int(group_id)):
            n = str(m.get("name") or "").strip()
            if n:
                out[int(m["viewer_id"])] = n
        return out
    except ValueError:
        return {}


def _overlay_clan_name(
    viewer_id: int, resolved: str, name_map: Dict[int, str]
) -> str:
    vid = int(viewer_id)
    fallback = game_display_name("", vid)
    if resolved != fallback:
        return resolved
    return name_map.get(vid) or resolved


async def get_binding_view(
    user_id: int, *, group_id: Optional[int] = None
) -> Dict[str, Any]:
    name_map = await _clan_viewer_name_map(group_id)
    accounts = await list_bound_accounts(user_id, group_id=group_id)
    if not accounts:
        return {"viewer_id": None, "name": None, "slot": None, "bindings": []}
    bindings = []
    for a in accounts:
        bindings.append(
            {
                "slot": a.slot,
                "viewer_id": a.viewer_id,
                "name": _overlay_clan_name(a.viewer_id, a.name, name_map),
            }
        )
    acc0 = bindings[0]
    return {
        "viewer_id": acc0["viewer_id"],
        "name": acc0["name"],
        "slot": acc0["slot"],
        "bindings": bindings,
    }


async def _resolve_account_id(user_id: int, viewer_id: int) -> int:
    legacy = await pcr_sqla.query_account(user_id) or []
    for acc in legacy:
        if acc.viewer_id == viewer_id and acc.id:
            return int(acc.id)
    rows = await pcr_sqla.query_user_accounts(user_id)
    for row in rows:
        if int(row.viewer_id) == int(viewer_id) and row.account_id:
            return int(row.account_id)
    return 0


async def _validate_viewer_in_clan(viewer_id: int, group_id: Optional[int]) -> None:
    if group_id is None:
        return
    from .clan_accounts_service import fetch_clan_member_options

    members = await fetch_clan_member_options(int(group_id))
    allowed = {int(m["viewer_id"]) for m in members}
    if int(viewer_id) not in allowed:
        raise ValueError("该角色不在当前公会成员列表中，请确认监控已开启后重试")


async def set_primary_binding(
    user_id: int, viewer_id: int, group_id: Optional[int] = None
) -> None:
    """单槽位绑定（V1 兼容：清空后只保留一条）。"""
    await _validate_viewer_in_clan(viewer_id, group_id)
    account_id = await _resolve_account_id(user_id, viewer_id)
    rows = await pcr_sqla.query_user_accounts(user_id)
    for row in rows:
        await pcr_sqla.delete_user_account_binding(row.id)
    await pcr_sqla.add_user_account(
        UserAccount(
            user_id=user_id,
            account_id=account_id,
            viewer_id=viewer_id,
            alias="",
            sort_order=0,
            is_active=True,
        )
    )
    logger.info("Web 绑定(单槽): user_id={} viewer_id={}", user_id, viewer_id)
    if group_id:
        await mirror_qq_sl_to_viewer(user_id, viewer_id, int(group_id))


async def upsert_binding_slot(
    user_id: int,
    viewer_id: int,
    *,
    group_id: Optional[int] = None,
    sort_order: Optional[int] = None,
) -> None:
    """多账号：新增或更新一条 user_account（不删除其它槽）。"""
    await _validate_viewer_in_clan(viewer_id, group_id)
    account_id = await _resolve_account_id(user_id, viewer_id)
    rows = await pcr_sqla.query_user_accounts(user_id)
    for row in rows:
        if int(row.viewer_id) == int(viewer_id):
            if sort_order is not None:
                row.account_id = account_id
                row.sort_order = int(sort_order)
                await pcr_sqla.add_user_account(row)
                logger.info(
                    "Web 绑定(更新): user_id={} viewer_id={}", user_id, viewer_id
                )
                if group_id:
                    await mirror_qq_sl_to_viewer(user_id, viewer_id, int(group_id))
                return
            raise ValueError("此用户已有该 UID 绑定记录")
    order = sort_order if sort_order is not None else len(rows)
    await pcr_sqla.add_user_account(
        UserAccount(
            user_id=user_id,
            account_id=account_id,
            viewer_id=viewer_id,
            alias="",
            sort_order=int(order),
            is_active=True,
        )
    )
    logger.info("Web 绑定(新增槽): user_id={} viewer_id={}", user_id, viewer_id)
    if group_id:
        await mirror_qq_sl_to_viewer(user_id, viewer_id, int(group_id))


async def binding_pair_exists(user_id: int, viewer_id: int) -> bool:
    for row in await pcr_sqla.query_user_accounts(user_id):
        if int(row.viewer_id or 0) == int(viewer_id):
            return True
    return False


async def admin_set_binding(
    target_user_id: int,
    viewer_id: int,
    *,
    group_id: Optional[int] = None,
    actor_user_id: int = 0,
    multi: bool = False,
) -> str:
    """Admin 代绑：禁止 QQ 指令代绑，仅 Web Admin 调用。返回 ok / skipped。"""
    if multi and await binding_pair_exists(target_user_id, viewer_id):
        logger.debug(
            "Admin 代绑跳过(已存在): target={} viewer={}",
            target_user_id,
            viewer_id,
        )
        return "skipped"
    if multi:
        await upsert_binding_slot(
            target_user_id, viewer_id, group_id=group_id
        )
    else:
        await set_primary_binding(target_user_id, viewer_id, group_id=group_id)
    logger.info(
        "Admin 代绑: target={} viewer={} by={}",
        target_user_id,
        viewer_id,
        actor_user_id,
    )
    return "ok"


async def admin_remove_binding(binding_id: int, *, actor_user_id: int = 0) -> None:
    row = await pcr_sqla.get_user_account_by_id(binding_id)
    await pcr_sqla.delete_user_account_binding(binding_id)
    if row:
        await compact_user_binding_sort_orders(int(row.user_id))
    logger.info("Admin 解绑: binding_id={} by={}", binding_id, actor_user_id)


async def remove_user_binding_slot(user_id: int, viewer_id: int) -> None:
    rows = await pcr_sqla.query_user_accounts(user_id)
    for row in rows:
        if int(row.viewer_id) == int(viewer_id):
            await pcr_sqla.delete_user_account_binding(int(row.id))
            await compact_user_binding_sort_orders(user_id)
            logger.info("Web 解绑槽: user_id={} viewer_id={}", user_id, viewer_id)
            return
    raise ValueError("未找到该 viewer_id 的绑定")


async def reorder_user_bindings(user_id: int, viewer_ids: List[int]) -> None:
    """按 viewer_ids 顺序重写 sort_order（QQ 账号N 与 Web 排序共用）。"""
    rows = await pcr_sqla.query_user_accounts(user_id)
    by_vid = {int(r.viewer_id): r for r in rows if r.viewer_id}
    missing = [int(v) for v in viewer_ids if int(v) not in by_vid]
    if missing:
        raise ValueError(f"排序包含未绑定 UID: {missing}")
    for idx, vid in enumerate(viewer_ids):
        row = by_vid[int(vid)]
        row.sort_order = idx
        await pcr_sqla.add_user_account(row)
    logger.info("Web 绑定排序: user_id={} order={}", user_id, viewer_ids)
