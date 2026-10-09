"""合刀线阈值采集、会战换期与提醒判定。"""
from __future__ import annotations

import statistics
import time
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from loguru import logger

from ...database.dal import pcr_sqla
from ...knife_budget.knife_state import KnifeDisplayState
from ...util.clan_phase import is_d_phase
from .constants import (
    DEFAULT_MERGE_LINE,
    MERGE_LINE_MULTIPLIER,
    MIN_SAMPLE_DAMAGE,
    SAMPLE_SIZE,
)
from .hp_format import format_hp_e


def _compute_threshold(damages: Sequence[int]) -> int:
    if not damages:
        return DEFAULT_MERGE_LINE
    med = float(statistics.median(damages))
    mean = float(statistics.mean(damages))
    raw = ((med + mean) / 2.0) * MERGE_LINE_MULTIPLIER
    return int(round(raw))


async def _season_anchor(group_id: int) -> int:
    days = await pcr_sqla.get_season_day_timestamps(group_id)
    return int(days[0]) if days else 0


async def ensure_season(group_id: int) -> None:
    anchor = await _season_anchor(group_id)
    settings = await pcr_sqla.get_merge_line_settings(group_id)
    if int(settings.season_anchor or 0) == anchor:
        return
    logger.info(
        "合刀线换期清空: group={} old_anchor={} new_anchor={}",
        group_id,
        settings.season_anchor,
        anchor,
    )
    await pcr_sqla.clear_merge_line_for_group(group_id)
    settings.season_anchor = anchor
    await pcr_sqla.save_merge_line_settings(settings)


async def is_reminder_enabled(group_id: int) -> bool:
    settings = await pcr_sqla.get_merge_line_settings(group_id)
    return bool(settings.reminder_enabled)


async def set_reminder_enabled(group_id: int, enabled: bool) -> None:
    settings = await pcr_sqla.get_merge_line_settings(group_id)
    settings.reminder_enabled = bool(enabled)
    await pcr_sqla.save_merge_line_settings(settings)
    logger.info("合刀线提醒开关: group={} enabled={}", group_id, enabled)


async def get_threshold(group_id: int, boss: int) -> int:
    await ensure_season(group_id)
    row = await pcr_sqla.get_merge_line_boss(group_id, boss)
    return int(row.threshold or DEFAULT_MERGE_LINE)


async def on_full_knife_settled(
    group_id: int,
    boss: int,
    damage: int,
    *,
    battle_log_id: int,
    record_time: int,
) -> None:
    if int(damage) < MIN_SAMPLE_DAMAGE:
        return
    if not (1 <= int(boss) <= 5):
        return
    await ensure_season(group_id)
    boss_row = await pcr_sqla.get_merge_line_boss(group_id, boss)
    if boss_row.frozen:
        return
    await pcr_sqla.add_merge_line_pending(
        group_id,
        boss,
        int(damage),
        battle_log_id=int(battle_log_id),
        record_time=int(record_time),
    )
    pending = await pcr_sqla.list_merge_line_pending(
        group_id, boss, limit=SAMPLE_SIZE
    )
    if len(pending) < SAMPLE_SIZE:
        logger.debug(
            "合刀线样本累积: group={} boss={} count={}/{}",
            group_id,
            boss,
            len(pending),
            SAMPLE_SIZE,
        )
        return
    samples = [(p.damage, p.battle_log_id, p.record_time) for p in pending]
    threshold = _compute_threshold([s[0] for s in samples])
    await pcr_sqla.replace_merge_line_frozen(group_id, boss, samples)
    await pcr_sqla.delete_merge_line_pending(group_id, boss)
    boss_row.threshold = threshold
    boss_row.frozen = True
    boss_row.computed_at = int(time.time())
    await pcr_sqla.save_merge_line_boss(boss_row)
    logger.info(
        "合刀线锁定: group={} boss={} line={} ({}) samples={}",
        group_id,
        boss,
        threshold,
        format_hp_e(threshold),
        SAMPLE_SIZE,
    )


async def admin_recompute_merge_line(group_id: int, boss: int) -> Tuple[bool, str]:
    if not (1 <= int(boss) <= 5):
        return False, "boss 序号应为 1–5"
    await ensure_season(group_id)
    anchor = await _season_anchor(group_id)
    records = await pcr_sqla.list_season_full_knife_for_merge_line(
        group_id,
        boss,
        anchor,
        min_damage=MIN_SAMPLE_DAMAGE,
        knife_state_full=int(KnifeDisplayState.FULL),
        limit=SAMPLE_SIZE,
    )
    if len(records) < SAMPLE_SIZE:
        return False, f"有效整刀不足{SAMPLE_SIZE}条（需伤害≥1.5e）"
    samples = [
        (int(r.damage), int(r.battle_log_id or 0), int(r.time or 0))
        for r in reversed(records)
    ]
    threshold = _compute_threshold([s[0] for s in samples])
    await pcr_sqla.replace_merge_line_frozen(group_id, boss, samples)
    await pcr_sqla.delete_merge_line_pending(group_id, boss)
    boss_row = await pcr_sqla.get_merge_line_boss(group_id, boss)
    boss_row.threshold = threshold
    boss_row.frozen = True
    boss_row.computed_at = int(time.time())
    await pcr_sqla.save_merge_line_boss(boss_row)
    logger.info(
        "合刀线管理员重算: group={} boss={} line={} ({})",
        group_id,
        boss,
        threshold,
        format_hp_e(threshold),
    )
    return True, f"{boss}王合刀线已更新为 {format_hp_e(threshold)}"


async def admin_recompute_all_merge_lines(group_id: int) -> Tuple[bool, str]:
    parts: List[str] = []
    ok_all = True
    for boss in range(1, 6):
        ok, msg = await admin_recompute_merge_line(group_id, boss)
        if not ok:
            ok_all = False
        parts.append(msg)
    return ok_all, "\n".join(parts)


@dataclass(frozen=True)
class MergeLinePushExtras:
    prefix: str = ""
    suffix: str = ""


async def build_merge_line_push_extras(
    group_id: int,
    boss: int,
    *,
    lap: int,
    post_hp: int,
    is_kill: bool,
    challenger_count: int,
    at_qq_ids: Sequence[int],
) -> MergeLinePushExtras:
    if not await is_reminder_enabled(group_id):
        return MergeLinePushExtras()
    if not is_d_phase(lap):
        return MergeLinePushExtras()
    threshold = await get_threshold(group_id, boss)
    trigger = is_kill or int(post_hp) < int(threshold)
    if not trigger:
        return MergeLinePushExtras()
    n = int(challenger_count)
    hp_e = "0.0e" if is_kill else format_hp_e(int(post_hp))
    prefix = f"[合刀提醒{boss}-余{hp_e}-{n}人]"
    threshold_line = f"合刀线：{format_hp_e(threshold)}"
    if at_qq_ids:
        at_line = " ".join(
            f"[CQ:at,qq={int(q)}]" for q in sorted(set(at_qq_ids))
        )
        suffix = f"{at_line}\n{threshold_line}"
    else:
        suffix = threshold_line
    logger.info(
        "合刀线提醒: group={} boss={} kill={} hp={} line={} n={} at={}",
        group_id,
        boss,
        is_kill,
        post_hp,
        threshold,
        n,
        len(at_qq_ids),
    )
    return MergeLinePushExtras(prefix=prefix, suffix=suffix)
