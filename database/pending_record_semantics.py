"""结算四态暂存：add_record 晚于 record_change 时由 merge/insert 补写。"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from loguru import logger

from .record_row import apply_knife_semantics_to_row, knife_semantics_locked
from .models import RecordDao

_Key = Tuple[int, int]
_pending: Dict[_Key, Dict[str, Any]] = {}


def stash_settlement_semantics(
    group_id: int,
    battle_log_id: int,
    *,
    semantics: Dict[str, Any],
    stub: Dict[str, Any],
    settled_at: int,
) -> None:
    key = (int(group_id), int(battle_log_id))
    _pending[key] = {
        "semantics": dict(semantics),
        "stub": dict(stub),
        "settled_at": int(settled_at),
    }
    logger.debug(
        "RecordDao 四态暂存(待战报 merge): group={} log_id={} pending={}",
        group_id,
        battle_log_id,
        len(_pending),
    )


def apply_stashed_semantics_to_row(row: RecordDao) -> bool:
    """若存在暂存四态且行未锁定，写入并弹出。"""
    if knife_semantics_locked(row):
        return False
    key = (int(row.group_id), int(row.battle_log_id))
    payload = _pending.pop(key, None)
    if not payload:
        return False
    apply_knife_semantics_to_row(
        row,
        payload["semantics"],
        settled_at=int(payload["settled_at"]),
        stub=payload.get("stub"),
    )
    logger.info(
        "RecordDao 四态暂存已应用: group={} log_id={} knife_state={}",
        row.group_id,
        row.battle_log_id,
        row.knife_state,
    )
    return True


def take_stashed(
    group_id: int, battle_log_id: int
) -> Optional[Dict[str, Any]]:
    return _pending.pop((int(group_id), int(battle_log_id)), None)


__all__ = [
    "apply_stashed_semantics_to_row",
    "stash_settlement_semantics",
    "take_stashed",
]
