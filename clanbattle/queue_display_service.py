"""预约/挑战队列展示（状态图、查x、文本响应共用）。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple, TYPE_CHECKING

from hoshino.typing import HoshinoBot
from loguru import logger

from ..basedata import NoticeType
from ..challenge.service import challenge_service
from ..database.dal import pcr_sqla
from ..knife_budget.service import knife_budget_service
from ..member.display import get_group_nickname
from .account_label import (
    PrimaryBinding,
    build_viewer_binding_cache,
    format_viewer_account_label,
    is_multi_account_binding,
)
from .apply_knife_presentation import (
    ApplyKnifePresentation,
    account_has_comp_resources,
    infer_queue_knife_presentation,
)
from .apply_notice_utils import APPLY_COMP_MARK, apply_declared_comp_for_viewer
from .member_identity import resolve_member_display_name
from ..status_dto import QueueActor

if TYPE_CHECKING:
    from ..database.models import NoticeCache

# (group, boss, viewer, explicit_comp) -> (budget_fingerprint, presentation)
_apply_pres_cache: Dict[Tuple[int, int, int, bool], Tuple[Any, ApplyKnifePresentation]] = {}


def _strip_comp_mark(text: str) -> str:
    if text and text.startswith(APPLY_COMP_MARK):
        return text[len(APPLY_COMP_MARK) :]
    return text or ""


async def _tree_user_ids(group_id: int, boss: int) -> Set[int]:
    rows = await pcr_sqla.get_notice(NoticeType.tree.value, group_id, boss)
    return {int(n.user_id) for n in rows}


async def _apply_presentation_for_notice(
    row: "NoticeCache", *, explicit_remark_comp: bool
) -> ApplyKnifePresentation:
    if not row.viewer_id:
        return ApplyKnifePresentation(
            kind="full", mark_comp_in_queue=explicit_remark_comp
        )
    vid = int(row.viewer_id)
    gid = int(row.group_id)
    boss = int(row.boss)
    cache_key = (gid, boss, vid, bool(explicit_remark_comp))
    summary = await knife_budget_service.remaining_summary(vid)
    budget_fp = (
        int(summary.get("full", 0) or 0),
        int(summary.get("comp", 0) or 0),
        int(summary.get("comp_seconds", 0) or 0),
        tuple(summary.get("comp_seconds_list") or ()),
    )
    cached = _apply_pres_cache.get(cache_key)
    if cached and cached[0] == budget_fp:
        return cached[1]
    if explicit_remark_comp:
        declared = account_has_comp_resources(summary)
    else:
        declared = await apply_declared_comp_for_viewer(gid, boss, vid)
    pres = infer_queue_knife_presentation(
        summary,
        declared_comp=declared,
        log_context=f"viewer={vid} group={gid} boss={boss}",
    )
    _apply_pres_cache[cache_key] = (budget_fp, pres)
    if len(_apply_pres_cache) > 512:
        _apply_pres_cache.clear()
    return pres


async def _comp_seconds_for(viewer_id: Optional[int]) -> int:
    if not viewer_id:
        return 0
    summary = await knife_budget_service.remaining_summary(int(viewer_id))
    return int(summary.get("comp_seconds") or 0)


async def _resolve_queue_image_label(
    bot: HoshinoBot,
    group_id: int,
    *,
    user_id: int,
    viewer_id: Optional[int],
    binding_cache: Dict[int, Optional[PrimaryBinding]],
) -> tuple[str, bool]:
    """状态图 / 查x 队列胶囊：与战报共用 format_viewer_account_label。"""
    uid = int(user_id)
    if viewer_id:
        vid = int(viewer_id)
        gname = await resolve_member_display_name(
            vid, group_id=group_id, user_id=uid
        )
        label = await format_viewer_account_label(
            bot,
            group_id,
            vid,
            gname,
            binding_cache=binding_cache,
        )
        binding = binding_cache.get(vid)
        return label, is_multi_account_binding(binding)
    nick = await get_group_nickname(bot, group_id, uid)
    return nick, False


async def build_subscribe_actors(
    bot: HoshinoBot,
    group_id: int,
    boss: int,
) -> List[QueueActor]:
    from .reserve_service import list_reserve_for_boss, reserve_is_board_message

    rows = await list_reserve_for_boss(group_id, boss)
    viewer_ids = {int(r.viewer_id) for r in rows if r.viewer_id}
    binding_cache = await build_viewer_binding_cache(bot, group_id, viewer_ids)
    actors: List[QueueActor] = []
    for row in rows:
        label, full_row = await _resolve_queue_image_label(
            bot,
            group_id,
            user_id=int(row.user_id),
            viewer_id=int(row.viewer_id) if row.viewer_id else None,
            binding_cache=binding_cache,
        )
        actors.append(
            QueueActor(
                label=label,
                message=row.text or None,
                is_board_message=reserve_is_board_message(row),
                full_row=full_row,
            )
        )
    return actors


async def build_challenge_actors(
    bot: HoshinoBot,
    group_id: int,
    boss: int,
    *,
    exclude_user_ids: Optional[Set[int]] = None,
) -> List[QueueActor]:
    apply_rows = await pcr_sqla.get_notice(NoticeType.apply.value, group_id, boss)
    if exclude_user_ids:
        apply_rows = [
            r
            for r in apply_rows
            if int(r.user_id) not in exclude_user_ids
        ]
    tree_users = await _tree_user_ids(group_id, boss)
    viewer_ids = {int(r.viewer_id) for r in apply_rows if r.viewer_id}
    binding_cache = await build_viewer_binding_cache(bot, group_id, viewer_ids)
    actors: List[QueueActor] = []
    for row in apply_rows:
        explicit_comp = bool(row.text and row.text.startswith(APPLY_COMP_MARK))
        presentation = await _apply_presentation_for_notice(
            row, explicit_remark_comp=explicit_comp
        )
        is_comp = presentation.mark_comp_in_queue
        label, full_row = await _resolve_queue_image_label(
            bot,
            group_id,
            user_id=int(row.user_id),
            viewer_id=int(row.viewer_id) if row.viewer_id else None,
            binding_cache=binding_cache,
        )
        remark = _strip_comp_mark(row.text or "")
        actors.append(
            QueueActor(
                label=label,
                message=remark or None,
                is_comp=is_comp,
                comp_seconds=await _comp_seconds_for(row.viewer_id)
                if is_comp
                else 0,
                is_tree=row.user_id in tree_users,
                full_row=full_row,
            )
        )
    unknown_n = await challenge_service.unknown_count(group_id, boss)
    for i in range(unknown_n):
        actors.append(QueueActor(label=f"未知玩家{i + 1}", is_unknown=True))
    logger.debug(
        "queue_display: group={} boss={} apply={} unknown={}",
        group_id,
        boss,
        len(apply_rows),
        unknown_n,
    )
    return actors


def _sort_challenger_actors(actors: List[QueueActor]) -> List[QueueActor]:
    unknown: List[QueueActor] = []
    normal: List[QueueActor] = []
    comp_only: List[QueueActor] = []
    tree: List[QueueActor] = []
    for actor in actors:
        if actor.is_unknown:
            unknown.append(actor)
        elif actor.is_tree:
            tree.append(actor)
        elif actor.is_comp:
            comp_only.append(actor)
        else:
            normal.append(actor)
    return unknown + normal + comp_only + tree


def _format_challenger_line(actor: QueueActor) -> str:
    if actor.is_unknown:
        return actor.label
    if actor.is_tree:
        return f"(挂树){actor.label}"
    if actor.is_comp:
        sec = int(actor.comp_seconds or 0)
        if sec > 0:
            return f"(补偿){actor.label}-{sec}s"
        return f"(补偿){actor.label}"
    if actor.message:
        return f"{actor.label}：{actor.message}"
    return actor.label


def _exclude_settler_user_ids(settler_user_id: int) -> Optional[Set[int]]:
    uid = int(settler_user_id or 0)
    return {uid} if uid else None


async def build_challenger_text_lines(
    bot: HoshinoBot,
    group_id: int,
    boss: int,
    *,
    exclude_user_ids: Optional[Set[int]] = None,
) -> List[str]:
    """申请成功/报刀推送/进本上升沿用的挑战者文本行（每账号一行）。"""
    actors = _sort_challenger_actors(
        await build_challenge_actors(
            bot,
            group_id,
            boss,
            exclude_user_ids=exclude_user_ids,
        )
    )
    return [_format_challenger_line(a) for a in actors]


async def build_damage_push_challenger_lines(
    bot: HoshinoBot,
    group_id: int,
    boss: int,
    *,
    settler_user_id: int,
) -> List[str]:
    """
    报刀推送挑战者区唯一入口：结算前申请队列，人数含未知；
    击杀/非击杀均排除当前出刀者 QQ（与 on_settlement 是否清空无关）。
    """
    return await build_challenger_text_lines(
        bot,
        group_id,
        boss,
        exclude_user_ids=_exclude_settler_user_ids(settler_user_id),
    )


async def collect_damage_push_at_qq_ids(
    group_id: int,
    boss: int,
    *,
    settler_user_id: int,
) -> List[int]:
    """报刀合刀 @ 名单：已知申请者 QQ，排除当前出刀者。"""
    exclude = _exclude_settler_user_ids(settler_user_id) or set()
    rows = await pcr_sqla.get_notice(NoticeType.apply.value, group_id, boss)
    out: List[int] = []
    for row in rows:
        uid = int(row.user_id)
        if uid in exclude:
            continue
        out.append(uid)
    return sorted(set(out))


async def build_fighter_enter_message(
    bot: HoshinoBot,
    group_id: int,
    boss: int,
    enter_signal: int,
) -> str:
    """上升沿群通知：y=enter_signal；z=下列表行数（申请+未知等）。"""
    lines = await build_challenger_text_lines(bot, group_id, boss)
    y = max(0, int(enter_signal or 0))
    z = len(lines)
    header = f"{boss}王当前有{y}人出刀，申请队列中有{z}人："
    if not lines:
        return header
    return "\n".join([header, *lines])


def queue_actor_fingerprint(actor: QueueActor) -> Dict[str, object]:
    return {
        "label": actor.label,
        "message": actor.message or "",
        "is_unknown": actor.is_unknown,
        "is_comp": actor.is_comp,
        "is_tree": actor.is_tree,
        "is_board_message": actor.is_board_message,
        "comp_seconds": actor.comp_seconds if actor.is_comp else 0,
        "full_row": actor.full_row,
    }
