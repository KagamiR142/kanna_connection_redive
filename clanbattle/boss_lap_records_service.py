"""出刀记录 · 周目+Boss 明细（QQ 图 / Web 共用）。"""
from __future__ import annotations

import time
from collections import defaultdict
from datetime import timedelta
from typing import Dict, List, Optional, TYPE_CHECKING, Union

from loguru import logger

from ..database.dal import pcr_date, pcr_sqla
from ..database.models import RecordDao
from ..knife_budget.record_report import prepare_records_for_knife_report
from ..knife_budget.knife_state import display_knife_type_for_lap_report, format_knife_time_text
from .account_label import build_viewer_binding_cache, format_viewer_account_label
from .boss_lap_report_dto import (
    BossLapKnifeEntryDTO,
    BossLapRecordsReportDTO,
    BossLapSectionDTO,
)

if TYPE_CHECKING:
    from hoshino.typing import HoshinoBot
    from .model import ClanBattle, Boss


def mirror_boss_lap(clan_info: Optional["ClanBattle"], boss: int) -> int:
    """监控镜像上该槽位周目（含 HP=0 的当前周目，用于默认出刀记录周目）。"""
    if not clan_info or boss < 1 or boss > len(clan_info.boss):
        return 0
    return int(clan_info.boss[boss - 1].lap_num or 0)


def clan_monitor_ready(clan_info: Optional["ClanBattle"]) -> bool:
    return clan_info is not None and bool(getattr(clan_info, "clan_battle_id", None))


def _boss_mirror(clan_info: Optional["ClanBattle"], boss: int) -> Optional["Boss"]:
    if not clan_info or boss < 1 or boss > len(clan_info.boss):
        return None
    return clan_info.boss[boss - 1]


def _instance_max_hp(
    clan_info: Optional["ClanBattle"],
    boss: int,
    lap: int,
    records: List[RecordDao],
) -> int:
    b = _boss_mirror(clan_info, boss)
    if b and int(b.lap_num or 0) == int(lap) and int(b.max_hp or 0) > 0:
        return int(b.max_hp)
    total = sum(int(r.damage or 0) for r in records)
    peak = max((int(r.damage or 0) for r in records), default=0)
    return max(total, peak, 1)


def _hp_after_hit(hp_before: int, damage: int, is_kill: bool) -> int:
    if is_kill:
        return 0
    return max(0, int(hp_before) - int(damage))


def _format_hms(seconds: int) -> str:
    sec = max(0, int(seconds))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _format_yyyymmdd(ts: int) -> str:
    return time.strftime("%Y%m%d", time.localtime(int(ts)))


def _resolve_spawn_ts(
    records: List[RecordDao],
    clan_info: Optional["ClanBattle"],
    boss: int,
    lap: int,
) -> int:
    b = _boss_mirror(clan_info, boss)
    if b and int(b.lap_num or 0) == int(lap):
        spawn = int(getattr(b, "lap_spawn_at", 0) or 0)
        if spawn > 0:
            return spawn
    if records:
        return int(records[0].time or 0)
    return int(time.time())


def _resolve_end_ts(records: List[RecordDao]) -> int:
    if not records:
        return int(time.time())
    last = records[-1]
    return int(last.time or 0)


def _instance_timing_suffix(
    records: List[RecordDao],
    clan_info: Optional["ClanBattle"],
    boss: int,
    lap: int,
) -> str:
    spawn_ts = _resolve_spawn_ts(records, clan_info, boss, lap)
    appear = time.strftime("%H:%M:%S", time.localtime(spawn_ts))
    b = _boss_mirror(clan_info, boss)
    on_mirror = b is not None and int(b.lap_num or 0) == int(lap)
    alive = on_mirror and int(b.current_hp or 0) > 0
    if alive:
        return f"出现 {appear}"
    end_ts = _resolve_end_ts(records)
    survival = max(0, end_ts - spawn_ts)
    return f"出现 {appear} · 存活 {_format_hms(survival)}"


def _hp_percent_label(hp_after: int, max_hp: int) -> str:
    from .base import format_precent

    if max_hp <= 0:
        return ""
    pct = format_precent(max(0, hp_after) / max_hp)
    return f"({pct})"


async def resolve_all_laps_query_day(
    group_id: int,
    boss: int,
    day_token: Optional[str],
) -> tuple[int, str, List[RecordDao]]:
    """
    a 模式查询日：y=昨天，t=今天，省略=昨天（会战首日默认今天）。
    昨天无数据时回退到今天。
    """
    today = pcr_date(int(time.time()))
    yesterday = today - timedelta(days=1)
    season_days = await pcr_sqla.get_season_day_timestamps(group_id)
    first_day = len(season_days) <= 1
    token = (day_token or "").lower()

    if token == "t":
        candidates: List[tuple] = [(today, "今日")]
    elif token == "y":
        candidates = [(yesterday, "昨日"), (today, "今日")]
    else:
        candidates = (
            [(today, "今日")]
            if first_day
            else [(yesterday, "昨日"), (today, "今日")]
        )

    for idx, (target, label) in enumerate(candidates):
        day_ts = int(target.timestamp())
        raw = await pcr_sqla.get_boss_records_for_day(group_id, boss, day_ts)
        records = prepare_records_for_knife_report(raw)
        if records or idx == len(candidates) - 1:
            if idx > 0 and label == "今日":
                logger.info(
                    "出刀记录 a 模式: 回退今日 group={} boss={} token={}",
                    group_id,
                    boss,
                    token or "default",
                )
            logger.debug(
                "出刀记录 a 模式: group={} boss={} day={} knives={}",
                group_id,
                boss,
                label,
                len(records),
            )
            return day_ts, label, records
    day_ts = int(today.timestamp())
    return day_ts, "今日", []


async def _build_knife_entries(
    records: List[RecordDao],
    *,
    group_id: int,
    boss: int,
    lap: int,
    bot: Optional["HoshinoBot"],
    clan_info: Optional["ClanBattle"],
    binding_cache: Dict[int, object],
    query_day_ts: int = 0,
) -> tuple[List[BossLapKnifeEntryDTO], int]:
    max_hp = _instance_max_hp(clan_info, boss, lap, records)
    hp_cursor = max_hp
    entries: List[BossLapKnifeEntryDTO] = []
    for rec in records:
        dmg = int(rec.damage or 0)
        is_kill = bool(int(rec.is_kill or 0))
        hp_before = hp_cursor
        hp_after = _hp_after_hit(hp_before, dmg, is_kill)
        label = await format_viewer_account_label(
            bot,
            group_id,
            int(rec.pcrid or 0),
            str(rec.name or ""),
            binding_cache=binding_cache,
        )
        time_text = format_knife_time_text(
            int(rec.time or 0),
            query_day_ts=query_day_ts,
        )
        entries.append(
            BossLapKnifeEntryDTO(
                actor_label=label,
                time_text=time_text,
                damage=dmg,
                knife_type=display_knife_type_for_lap_report(rec),
                hp_before=hp_before,
                hp_after=hp_after,
                hp_after_percent=_hp_percent_label(hp_after, max_hp),
            )
        )
        hp_cursor = hp_after
        if is_kill:
            hp_cursor = 0
    return entries, max_hp


async def build_boss_lap_records_dto(
    group_id: int,
    boss: int,
    lap: int,
    bot: Optional["HoshinoBot"] = None,
    *,
    clan_info: Optional["ClanBattle"] = None,
    all_laps: bool = False,
    day_token: Optional[str] = None,
) -> Union[BossLapRecordsReportDTO, str]:
    if boss < 1 or boss > 5:
        return "Boss 编号须为 1–5"

    if all_laps:
        return await _build_all_laps_dto(
            group_id,
            boss,
            bot,
            clan_info=clan_info,
            day_token=day_token,
        )

    if lap <= 0:
        return "周目无效，请先开启出刀监控"
    raw = await pcr_sqla.get_boss_lap_records(group_id, lap, boss)
    records = prepare_records_for_knife_report(raw)
    spawn_ts = _resolve_spawn_ts(records, clan_info, boss, lap)
    date_tag = _format_yyyymmdd(spawn_ts if records else int(time.time()))
    title = f"出刀记录 · {lap}周目{boss}王 · {date_tag}"
    if not records:
        return BossLapRecordsReportDTO(
            title=title,
            subtitle="共 0 刀",
            empty_text="该周目该 Boss 暂无出刀记录",
        )
    viewer_ids = {int(r.pcrid or 0) for r in records if r.pcrid}
    binding_cache = await build_viewer_binding_cache(bot, group_id, viewer_ids)
    max_hp = _instance_max_hp(clan_info, boss, lap, records)
    timing = _instance_timing_suffix(records, clan_info, boss, lap)
    subtitle = f"共 {len(records)} 刀 · 初始血量 {max_hp} · {timing}"
    entries, _ = await _build_knife_entries(
        records,
        group_id=group_id,
        boss=boss,
        lap=lap,
        bot=bot,
        clan_info=clan_info,
        binding_cache=binding_cache,
    )

    logger.info(
        "出刀记录: group={} lap={} boss={} knives={} max_hp={} date={}",
        group_id,
        lap,
        boss,
        len(entries),
        max_hp,
        date_tag,
    )
    return BossLapRecordsReportDTO(
        title=title,
        subtitle=subtitle,
        entries=entries,
        max_hp=max_hp,
    )


async def _build_all_laps_dto(
    group_id: int,
    boss: int,
    bot: Optional["HoshinoBot"],
    *,
    clan_info: Optional["ClanBattle"],
    day_token: Optional[str],
) -> BossLapRecordsReportDTO:
    day_ts, day_label, records = await resolve_all_laps_query_day(
        group_id, boss, day_token
    )
    date_tag = _format_yyyymmdd(day_ts)
    title = f"出刀记录 · {boss}王 · {day_label} · {date_tag}"
    if not records:
        return BossLapRecordsReportDTO(
            title=title,
            subtitle="共 0 刀",
            empty_text="该日该 Boss 暂无出刀记录",
            query_day_ts=day_ts,
        )

    by_lap: Dict[int, List[RecordDao]] = defaultdict(list)
    for rec in records:
        by_lap[int(rec.lap or 0)].append(rec)

    viewer_ids = {int(r.pcrid or 0) for r in records if r.pcrid}
    binding_cache = await build_viewer_binding_cache(bot, group_id, viewer_ids)
    sections: List[BossLapSectionDTO] = []
    total_knives = 0

    for lap in sorted(by_lap.keys()):
        lap_records = by_lap[lap]
        max_hp = _instance_max_hp(clan_info, boss, lap, lap_records)
        timing = _instance_timing_suffix(lap_records, clan_info, boss, lap)
        lap_sub = f"共 {len(lap_records)} 刀 · 初始血量 {max_hp} · {timing}"
        entries, _ = await _build_knife_entries(
            lap_records,
            group_id=group_id,
            boss=boss,
            lap=lap,
            bot=bot,
            clan_info=clan_info,
            binding_cache=binding_cache,
            query_day_ts=day_ts,
        )
        sections.append(BossLapSectionDTO(lap=lap, subtitle=lap_sub, entries=entries))
        total_knives += len(entries)

    logger.info(
        "出刀记录 a: group={} boss={} day={} laps={} knives={}",
        group_id,
        boss,
        day_label,
        len(sections),
        total_knives,
    )
    return BossLapRecordsReportDTO(
        title=title,
        subtitle=f"共 {total_knives} 刀 · 跨 {len(sections)} 个周目",
        sections=sections,
        query_day_ts=day_ts,
    )


async def resolve_lap_for_boss_lap_records(
    group_id: int,
    clan_info: Optional["ClanBattle"],
    boss: int,
    lap: Optional[int],
) -> Optional[int]:
    """
    省略周目时取监控镜像槽位周目（含 HP=0 的已死当前周目），
    不回退到上一有刀周目。
    """
    if lap is not None and lap > 0:
        return int(lap)
    mirror = mirror_boss_lap(clan_info, boss)
    if mirror > 0:
        return mirror
    all_recs = await pcr_sqla.get_all_records(group_id)
    laps = [
        int(r.lap or 0)
        for r in all_recs
        if int(r.boss or 0) == boss and int(r.lap or 0) > 0
    ]
    return max(laps) if laps else None
