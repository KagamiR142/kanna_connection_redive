"""管理员指令：清空申请 / 肃正协议 / 修正出刀 / KPI 调整。"""
from __future__ import annotations

from typing import List, Optional

from hoshino.typing import CQEvent, HoshinoBot
from loguru import logger

from ...basedata import NoticeType
from ...challenge.service import challenge_service
from ...database.dal import pcr_sqla, RecordDao
from ...database.models import ClanBattleKPI
from ...util.decorator import check_priv_adimin
from ..command_match import REX_CLEAR_APPLY, REX_CLEAR_UNKNOWN_APPLY, strict_rex
from ..command_parser import match_exact, parse_clear_apply, parse_clear_unknown_apply
from ..permissions import PERM_DENIED, is_ops_admin, is_senior_admin
from ..registry import _seraphim_pending
from ..status_cache import notify_display_data_changed
from .context import extract_plain, require_group, sender_tag


def format_admin_clear_apply_message(
    apply_n: int, tree_n: int, sender: str, *, boss: Optional[int] = None
) -> str:
    if apply_n + tree_n <= 0:
        if boss is not None:
            return f"{sender} 指定的boss没有申请出刀记录"
        return f"{sender} 本群没有申请出刀记录"
    parts: List[str] = []
    if apply_n:
        parts.append(f"{apply_n}条申请")
    if tree_n:
        parts.append(f"{tree_n}条挂树")
    return f"成功清理{'、'.join(parts)}记录 {sender}"


async def clear_apply_and_tree(
    group_id: int, boss: Optional[int] = None
) -> tuple[int, int]:
    apply_n = await pcr_sqla.count_notice(
        NoticeType.apply.value, group_id, boss
    )
    tree_n = await pcr_sqla.count_notice(
        NoticeType.tree.value, group_id, boss
    )
    if boss is not None:
        await pcr_sqla.delete_notice(NoticeType.apply.value, group_id, boss)
        await pcr_sqla.delete_notice(NoticeType.tree.value, group_id, boss)
    else:
        await pcr_sqla.delete_notice(NoticeType.apply.value, group_id)
        await pcr_sqla.delete_notice(NoticeType.tree.value, group_id)
    return apply_n, tree_n


def register_admin_handlers(sv) -> None:
    @sv.on_rex(strict_rex(REX_CLEAR_APPLY))
    async def clear_apply(bot: HoshinoBot, ev: CQEvent):
        if not require_group(ev):
            return
        if not is_ops_admin(ev):
            await bot.send(ev, PERM_DENIED)
            return
        boss, all_bosses, matched = parse_clear_apply(
            ev.message.extract_plain_text().strip()
        )
        if not matched:
            await bot.send(
                ev,
                f"{await sender_tag(bot, ev)} 指令格式错误\n"
                "清空申请格式：清空申请<boss> 或 清空申请a\n"
                "例：清空申请1 / 清空申请a",
            )
            return
        target_boss = None if all_bosses else boss
        apply_n, tree_n = await clear_apply_and_tree(ev.group_id, target_boss)
        if apply_n + tree_n > 0:
            await notify_display_data_changed(ev.group_id, "clear_apply")
        sender = await sender_tag(bot, ev)
        await bot.send(
            ev,
            format_admin_clear_apply_message(
                apply_n, tree_n, sender, boss=target_boss
            ),
        )

    @sv.on_rex(strict_rex(REX_CLEAR_UNKNOWN_APPLY))
    async def clear_unknown_apply(bot: HoshinoBot, ev: CQEvent):
        if not require_group(ev):
            return
        if not is_ops_admin(ev):
            await bot.send(ev, PERM_DENIED)
            return
        boss, all_bosses, matched = parse_clear_unknown_apply(
            ev.message.extract_plain_text().strip()
        )
        if not matched:
            await bot.send(
                ev,
                f"{await sender_tag(bot, ev)} 指令格式错误\n"
                "清空未知申请格式：清空未知申请<boss> 或 清空未知申请a\n"
                "例：清空未知申请2 / 清空未知申请a",
            )
            return
        target_boss = None if all_bosses else boss
        cleared = await challenge_service.clear_unknown_slots(
            ev.group_id, target_boss
        )
        if cleared > 0:
            await notify_display_data_changed(ev.group_id, "clear_unknown")
        sender = await sender_tag(bot, ev)
        if cleared <= 0:
            if target_boss is not None:
                await bot.send(
                    ev, f"{sender} 指定的boss没有未知玩家的挑战记录"
                )
            else:
                await bot.send(
                    ev, f"{sender} 本群没有未知玩家的挑战记录"
                )
        else:
            await bot.send(
                ev, f"成功清理{cleared}个未知玩家挑战记录 {sender}"
            )

    @sv.on_rex(strict_rex(r"启用肃正协议"))
    async def kill_all(bot: HoshinoBot, ev: CQEvent):
        if not require_group(ev):
            return
        if not is_senior_admin(ev):
            await bot.send(ev, PERM_DENIED)
            return
        gid = ev.group_id
        if _seraphim_pending.get(gid) != ev.user_id:
            _seraphim_pending[gid] = ev.user_id
            await bot.send(
                ev,
                "【警告】肃正协议将清空本群全部出刀数据，请再次发送【启用肃正协议】确认执行",
            )
            return
        _seraphim_pending.pop(gid, None)
        await pcr_sqla.refresh(RecordDao, -1, ev.group_id)
        logger.warning("肃正协议执行: group={} by={}", gid, ev.user_id)
        await bot.send(
            ev,
            "[WARNING]肃正协议将清理一切事物（不分敌我），期间出现任何报错均为正常现象，事后请重新开启出刀监控",
        )

    @sv.on_rex(r"^\s*修正出刀(\d+)(完整刀|尾刀|补偿)\s*$")
    async def correct_dao(bot: HoshinoBot, ev: CQEvent):
        if not require_group(ev):
            return
        m = match_exact(extract_plain(ev), r"修正出刀(\d+)(完整刀|尾刀|补偿)")
        if not m:
            return
        dao = m.group(2)
        if await pcr_sqla.correct_dao(
            int(m.group(1)),
            0 if dao == "完整刀" else 1 if dao == "尾刀" else 0.5,
            ev.group_id,
        ):
            await bot.send(ev, "修改成功")
        else:
            await bot.send(ev, "请检查你输入了正确的出刀编号")

    @sv.on_rex(r"^\s*kpi调整(\d+)([+-]?\d+)\s*$")
    @check_priv_adimin(False)
    async def correct_kpi(bot: HoshinoBot, ev: CQEvent, qq_id: int):
        if not require_group(ev):
            return
        m = match_exact(extract_plain(ev), r"kpi调整(\d+)([+-]?\d+)")
        if not m:
            return
        try:
            await pcr_sqla.add_kpi_special(
                ClanBattleKPI(
                    group_id=ev.group_id,
                    pcrid=int(m.group(1)),
                    bouns=int(m.group(2)),
                )
            )
            await bot.send(ev, "设置成功")
        except Exception:
            await bot.send(ev, "设置失败，一定是你输入了奇怪的东西，爬爬")

    @sv.on_rex(r"^\s*(?:清空kpi|清空KPI)\s*$")
    async def clean_kpi(bot: HoshinoBot, ev: CQEvent):
        if not require_group(ev):
            return
        await pcr_sqla.delete_kpi(ev.group_id)
        await bot.send(ev, "清空成功")

    @sv.on_rex(r"^\s*(?:删除kpi|删除KPI)(\d+)\s*$")
    async def del_kpi(bot: HoshinoBot, ev: CQEvent):
        if not require_group(ev):
            return
        m = match_exact(extract_plain(ev), r"(?:删除kpi|删除KPI)(\d+)")
        if not m:
            return
        await pcr_sqla.delete_kpi(ev.group_id, int(m.group(1)))
        await bot.send(ev, "删除成功")
