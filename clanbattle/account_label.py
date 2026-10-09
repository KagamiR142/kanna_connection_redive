"""战报/状态图等场景共用的账号展示名。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional, TYPE_CHECKING

from loguru import logger

from ..member.display import get_group_nickname
from ..util.display.names import display_name_sort_key, game_display_name
from .account_service import list_bound_accounts, viewer_to_slot
from .member_identity import is_monitor_viewer
from ..database.dal import pcr_sqla

if TYPE_CHECKING:
    from hoshino.typing import HoshinoBot


@dataclass(frozen=True)
class PrimaryBinding:
    user_id: int
    nickname: str
    slot: Optional[int]
    n_accounts: int


async def viewer_to_qq(viewer_id: int) -> Optional[int]:
    """成员 QQ；不含监控 Account（Phase J）。"""
    binding = await resolve_primary_binding(None, 0, int(viewer_id))
    return binding.user_id if binding else None


async def resolve_primary_binding(
    bot: Optional["HoshinoBot"],
    group_id: int,
    viewer_id: int,
) -> Optional[PrimaryBinding]:
    """
    同一 viewer 被多个 QQ 绑定时，按群昵称拼音/字母序取第一个用户。
    无绑定时返回 None。
    """
    rows = await pcr_sqla.query_accounts_by_viewer(int(viewer_id))
    if not rows:
        return None
    candidates: list[tuple[str, int, str]] = []
    for row in rows:
        uid = int(row.user_id)
        if bot and group_id:
            nick = await get_group_nickname(bot, group_id, uid)
        else:
            nick = f"QQ{uid}"
        candidates.append((display_name_sort_key(nick), uid, nick))
    candidates.sort(key=lambda item: (item[0], item[1]))
    _, user_id, nickname = candidates[0]
    if len(candidates) > 1:
        logger.debug(
            "viewer 多用户绑定: viewer={} picked_user={} nick={} candidates={}",
            viewer_id,
            user_id,
            nickname,
            [c[1] for c in candidates],
        )
    accounts = await list_bound_accounts(user_id)
    slot = await viewer_to_slot(user_id, int(viewer_id))
    slot_out = slot if slot > 0 else None
    return PrimaryBinding(
        user_id=user_id,
        nickname=nickname,
        slot=slot_out,
        n_accounts=len(accounts),
    )


async def build_viewer_binding_cache(
    bot: Optional["HoshinoBot"],
    group_id: int,
    viewer_ids: Iterable[int],
) -> Dict[int, Optional[PrimaryBinding]]:
    cache: Dict[int, Optional[PrimaryBinding]] = {}
    for vid in viewer_ids:
        iv = int(vid)
        if iv not in cache:
            cache[iv] = await resolve_primary_binding(bot, group_id, iv)
    return cache


def binding_from_cache(
    binding_cache: Optional[Dict[int, Optional[PrimaryBinding]]],
    viewer_id: int,
) -> Optional[PrimaryBinding]:
    if not binding_cache:
        return None
    return binding_cache.get(int(viewer_id))


def is_multi_account_binding(binding: Optional[PrimaryBinding]) -> bool:
    return binding is not None and binding.n_accounts > 1


async def format_viewer_account_label(
    bot: Optional["HoshinoBot"],
    group_id: int,
    viewer_id: int,
    game_name: str,
    *,
    binding_cache: Optional[Dict[int, Optional[PrimaryBinding]]] = None,
    user_account_counts: Optional[Dict[int, int]] = None,
) -> str:
    """
    未绑定：游戏名。
    监控 viewer：游戏名（监控）。
    已绑定单账号：群昵称。
    已绑定多账号：群昵称-编号-游戏名。
    """
    _ = user_account_counts  # legacy kwarg; ignored
    gname = game_display_name(game_name, viewer_id)
    if await is_monitor_viewer(viewer_id):
        return f"{gname}（监控）"

    binding = binding_from_cache(binding_cache, viewer_id)
    if binding is None and bot and group_id:
        binding = await resolve_primary_binding(bot, group_id, viewer_id)
    if binding is None:
        return gname

    if binding.n_accounts <= 1:
        return binding.nickname

    slot_part = binding.slot if binding.slot is not None else "?"
    return f"{binding.nickname}-{slot_part}-{gname}"


async def build_user_account_count_cache(user_ids: set[int]) -> Dict[int, int]:
    """legacy：QQ → 绑定账号数（新代码请用 build_viewer_binding_cache）。"""
    cache: Dict[int, int] = {}
    for uid in user_ids:
        if uid and uid not in cache:
            cache[uid] = len(await list_bound_accounts(uid))
    return cache


def format_member_account_tag(
    slot: int,
    game_name: str,
    viewer_id: Optional[int] = None,
) -> str:
    """成员绑定展示：`{编号}-{游戏名}`（无「账号」前缀）。"""
    return f"{int(slot)}-{game_display_name(game_name, viewer_id)}"


async def format_user_report_section_heading(
    bot: Optional["HoshinoBot"],
    group_id: int,
    viewer_id: int,
    game_name: str,
    *,
    binding_cache: Optional[Dict[int, Optional[PrimaryBinding]]] = None,
) -> str:
    binding = binding_from_cache(binding_cache, viewer_id)
    if binding is None and bot and group_id:
        binding = await resolve_primary_binding(bot, group_id, viewer_id)
    if binding is not None and binding.n_accounts > 1 and binding.slot is not None:
        return f"{format_member_account_tag(binding.slot, game_name, viewer_id)}："
    label = await format_viewer_account_label(
        bot,
        group_id,
        viewer_id,
        game_name,
        binding_cache=binding_cache,
    )
    return f"{label}："


def format_user_report_account_heading(
    game_name: str,
    slot: int,
    *,
    multi_account_user: bool,
) -> str:
    """legacy 同步接口；新代码请用 format_user_report_section_heading。"""
    if multi_account_user:
        return f"{int(slot)}-{game_name}："
    return f"{game_name}："
