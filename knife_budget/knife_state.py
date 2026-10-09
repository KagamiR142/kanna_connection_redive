"""出刀四态：整刀 / 击杀 / 补偿 / 补偿击杀（全模块共用）。"""
from __future__ import annotations

from enum import IntEnum
from typing import Optional, Union

from ..database.models import RecordDao


class KnifeDisplayState(IntEnum):
    FULL = 0  # 整刀
    KILL = 1  # 击杀（整刀击杀，产生补偿）
    COMP = 2  # 补偿
    COMP_KILL = 3  # 补偿击杀


DISPLAY_LABELS = {
    KnifeDisplayState.FULL: "整刀",
    KnifeDisplayState.KILL: "击杀",
    KnifeDisplayState.COMP: "补偿",
    KnifeDisplayState.COMP_KILL: "补偿击杀",
}


def display_label(state: Union[KnifeDisplayState, int, None]) -> str:
    if state is None:
        return "整刀"
    try:
        return DISPLAY_LABELS[KnifeDisplayState(int(state))]
    except (KeyError, ValueError):
        return "整刀"


def _estimate_kill_comp_seconds(record: RecordDao) -> int:
    from .kill_comp import KillCompKind, resolve_kill_comp_seconds

    dmg = int(record.damage or 0)
    if dmg <= 0 or not int(record.is_kill or 0):
        return 0
    bt = int(record.battle_time or 0)
    res = resolve_kill_comp_seconds(
        dmg,
        dmg,
        is_kill=True,
        battle_time=bt if bt > 0 else None,
        viewer_id=int(record.pcrid or 0),
        context="report",
    )
    if res.seconds and res.kind in (KillCompKind.MERGE, KillCompKind.CLEANUP):
        return int(res.seconds)
    return 0


def display_knife_type_for_lap_report(record: RecordDao) -> str:
    """周目 Boss 出刀记录：补偿带秒数，击杀带获得秒数。"""
    state = knife_state_from_record(record)
    if state in (KnifeDisplayState.KILL, KnifeDisplayState.COMP_KILL):
        return display_label_for_record(record)
    if state == KnifeDisplayState.COMP:
        srt = int(record.remain_time or 0)
        if srt > 0:
            return f"补偿({srt}s)"
        return "补偿"
    return display_label(state)


def display_label_for_record(record: RecordDao) -> str:
    state = knife_state_from_record(record)
    base = display_label(state)
    if state not in (KnifeDisplayState.KILL, KnifeDisplayState.COMP_KILL):
        return base
    if not int(record.is_kill or 0):
        return base
    sec = int(getattr(record, "kill_comp_seconds", 0) or 0)
    if sec <= 0:
        sec = _estimate_kill_comp_seconds(record)
    if sec <= 0:
        return base
    if state == KnifeDisplayState.COMP_KILL:
        return f"补偿击杀({sec}s)"
    return f"击杀({sec}s)"


def record_flag_for_state(state: KnifeDisplayState) -> float:
    """RecordDao.flag：整刀/击杀=0，补偿/补偿击杀=0.5。"""
    if state in (KnifeDisplayState.COMP, KnifeDisplayState.COMP_KILL):
        return 0.5
    return 0.0


def record_is_kill_for_state(state: KnifeDisplayState) -> int:
    return int(state in (KnifeDisplayState.KILL, KnifeDisplayState.COMP_KILL))


def knife_state_from_record(record: RecordDao) -> KnifeDisplayState:
    raw = getattr(record, "knife_state", None)
    if raw is not None and int(raw) in DISPLAY_LABELS:
        return KnifeDisplayState(int(raw))
    # 旧数据回退
    if record.is_kill:
        return (
            KnifeDisplayState.COMP_KILL
            if record.flag and record.flag >= 0.5
            else KnifeDisplayState.KILL
        )
    if record.flag and record.flag >= 0.5:
        return KnifeDisplayState.COMP
    return KnifeDisplayState.FULL


def point_weight_for_state(state: KnifeDisplayState) -> float:
    if state == KnifeDisplayState.FULL:
        return 1.0
    return 0.5


def aggregate_day_knife_counts(records: list) -> tuple[float, int, int]:
    """(已用点数合计, 整刀刀数, 补偿刀数) — 按四态统计记录条数。"""
    used = 0.0
    full_n = 0
    comp_n = 0
    for r in records:
        state = knife_state_from_record(r)
        used += point_weight_for_state(state)
        if state in (KnifeDisplayState.FULL, KnifeDisplayState.KILL):
            full_n += 1
        elif state in (KnifeDisplayState.COMP, KnifeDisplayState.COMP_KILL):
            comp_n += 1
    return used, full_n, comp_n


def format_knife_time_text(
    record_ts: int,
    *,
    query_day_ts: int = 0,
) -> str:
    import time

    from ..database.dal import pcr_date

    ts_str = time.strftime("%H:%M:%S", time.localtime(int(record_ts)))
    if query_day_ts > 0 and pcr_date(record_ts) < pcr_date(query_day_ts):
        return f"(昨){ts_str}"
    return ts_str


def format_record_line(record: RecordDao, *, query_day_ts: int = 0) -> str:
    from ..clanbattle.report_image import REPORT_COL_SEP

    ts = format_knife_time_text(int(record.time or 0), query_day_ts=query_day_ts)
    return (
        f"  {ts}{REPORT_COL_SEP}{record.lap}-{record.boss}{REPORT_COL_SEP}"
        f"{record.damage}{REPORT_COL_SEP}{display_label_for_record(record)}"
    )
