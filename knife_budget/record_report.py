"""战报读侧：去重、合并整刀+击杀重复行（仅展示，不改库）。"""
from __future__ import annotations

from typing import List, Sequence, Set, Tuple

from loguru import logger

from ..database.models import RecordDao
from .knife_state import KnifeDisplayState, knife_state_from_record

_STATE_REPORT_RANK = {
    KnifeDisplayState.KILL: 40,
    KnifeDisplayState.COMP_KILL: 40,
    KnifeDisplayState.COMP: 20,
    KnifeDisplayState.FULL: 10,
}


def _record_report_rank(rec: RecordDao) -> int:
    state = knife_state_from_record(rec)
    base = _STATE_REPORT_RANK.get(state, 0)
    settled = int(getattr(rec, "knife_settled_at", 0) or 0)
    return base + (5 if settled > 0 else 0)


def _record_sort_key(rec: RecordDao) -> tuple[int, int]:
    return (int(rec.time or 0), int(getattr(rec, "id", None) or 0))


def dedupe_records_for_report(records: Sequence[RecordDao]) -> List[RecordDao]:
    """按 battle_log_id 去重，保留四态更权威的一条（击杀优于整刀）。"""
    no_log: List[RecordDao] = []
    best: dict[Tuple[int, int], RecordDao] = {}
    dropped = 0
    for rec in records:
        log_id = int(rec.battle_log_id or 0)
        if log_id <= 0:
            no_log.append(rec)
            continue
        key = (int(rec.group_id or 0), log_id)
        prev = best.get(key)
        if prev is None:
            best[key] = rec
            continue
        if _record_report_rank(rec) > _record_report_rank(prev):
            best[key] = rec
            dropped += 1
        elif _record_report_rank(rec) == _record_report_rank(prev):
            if int(rec.time or 0) >= int(prev.time or 0):
                best[key] = rec
                dropped += 1
            else:
                dropped += 1
        else:
            dropped += 1
    out = sorted(best.values(), key=_record_sort_key)
    out.extend(sorted(no_log, key=_record_sort_key))
    if dropped:
        logger.debug(
            "战报读侧去重: dropped={} kept={}", dropped, len(out)
        )
    return out


def _knife_moment_key(rec: RecordDao) -> tuple[int, int, int, int, int]:
    """同一刀物理结算：账号 + 周目 + 王 + 伤害 + 结束时间。"""
    return (
        int(rec.pcrid or 0),
        int(rec.lap or 0),
        int(rec.boss or 0),
        int(rec.damage or 0),
        int(rec.time or 0),
    )


def dedupe_same_knife_moment(records: Sequence[RecordDao]) -> List[RecordDao]:
    """
    合并 battle_log_id 不同但时间/周目/伤害相同的重复行（常见：战报 log 整刀 + 结算补偿）。
    保留四态更权威的一条（已结算 > 补偿 > 整刀 > …）。
    """
    best: dict[tuple[int, int, int, int, int], RecordDao] = {}
    dropped = 0
    for rec in records:
        key = _knife_moment_key(rec)
        prev = best.get(key)
        if prev is None:
            best[key] = rec
            continue
        if _record_report_rank(rec) > _record_report_rank(prev):
            best[key] = rec
        dropped += 1
    out = sorted(best.values(), key=_record_sort_key)
    if dropped:
        logger.debug(
            "战报同刀去重: dropped={} kept={}", dropped, len(out)
        )
    return out


_REPORT_SHADOW_SEC = 300


def _knife_shadow_key(rec: RecordDao) -> tuple[int, int, int]:
    return (int(rec.pcrid or 0), int(rec.lap or 0), int(rec.boss or 0))


def _full_shadowed_by_kill(full: RecordDao, kills: Sequence[RecordDao]) -> bool:
    """战报 log 整刀 + damage_history 结算击杀常为不同 battle_log_id，伤害也可能不一致。"""
    fk = _knife_shadow_key(full)
    ft = int(full.time or 0)
    for k in kills:
        if _knife_shadow_key(k) != fk:
            continue
        if abs(ft - int(k.time or 0)) > _REPORT_SHADOW_SEC:
            continue
        return True
    return False


def filter_redundant_full_knife_rows(records: Sequence[RecordDao]) -> List[RecordDao]:
    """
    去掉与击杀重复的「整刀」行（同账号/周目/boss/伤害且时间接近）。
    非击杀的整刀、补偿行保留。
    """
    kills = [
        r
        for r in records
        if knife_state_from_record(r)
        in (KnifeDisplayState.KILL, KnifeDisplayState.COMP_KILL)
    ]
    if not kills:
        return list(records)
    out: List[RecordDao] = []
    dropped = 0
    for rec in records:
        state = knife_state_from_record(rec)
        if state == KnifeDisplayState.FULL and _full_shadowed_by_kill(rec, kills):
            dropped += 1
            continue
        out.append(rec)
    if dropped:
        logger.debug("战报隐藏重复整刀: dropped={}", dropped)
    return out


def prepare_records_for_knife_report(
    records: Sequence[RecordDao],
) -> List[RecordDao]:
    rows = dedupe_records_for_report(records)
    rows = dedupe_same_knife_moment(rows)
    return filter_redundant_full_knife_rows(rows)


__all__ = [
    "dedupe_records_for_report",
    "dedupe_same_knife_moment",
    "filter_redundant_full_knife_rows",
    "prepare_records_for_knife_report",
]
