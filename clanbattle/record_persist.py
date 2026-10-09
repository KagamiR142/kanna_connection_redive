"""damage_history 结算 → RecordDao 四态持久化（与 add_record 战报 merge 配合）。"""
from __future__ import annotations

from typing import Any, Dict

from loguru import logger

from ..database.dal import pcr_sqla
from ..database.pending_record_semantics import stash_settlement_semantics
from ..knife_budget.record_semantics import semantics_from_settlement
from ..knife_budget.settlement import SettlementResult


async def persist_settlement_record(
    group_id: int,
    battle_log_id: int,
    settlement: SettlementResult,
    *,
    pcrid: int,
    name: str,
    lap: int,
    boss: int,
    damage: int,
    record_time: int,
    kill_comp_seconds: int | None = None,
) -> bool:
    """
    结算后立即写库四态；无行则插入 stub，有行则 UPDATE。
    失败时暂存四态供 add_record merge，不向外抛错（避免 top 重试重复扣 budget）。
    """
    log_id = int(battle_log_id or 0)
    if log_id <= 0:
        logger.warning(
            "结算四态跳过(无 battle_log_id): group={} viewer={} boss={}",
            group_id,
            pcrid,
            boss,
        )
        return False
    semantics: Dict[str, Any] = semantics_from_settlement(settlement)
    if kill_comp_seconds is not None and int(kill_comp_seconds) > 0:
        semantics["kill_comp_seconds"] = int(kill_comp_seconds)
    stub = {
        "pcrid": int(pcrid),
        "name": str(name or ""),
        "lap": int(lap),
        "boss": int(boss),
        "damage": int(damage),
        "time": int(record_time),
    }
    settled_at = int(record_time)
    try:
        action = await pcr_sqla.upsert_record_settlement_semantics(
            int(group_id),
            log_id,
            semantics=semantics,
            stub=stub,
            settled_at=settled_at,
        )
    except Exception as e:
        stash_settlement_semantics(
            int(group_id),
            log_id,
            semantics=semantics,
            stub=stub,
            settled_at=settled_at,
        )
        logger.error(
            "RecordDao 结算四态写库失败(已暂存): group={} log_id={} viewer={} err={}",
            group_id,
            log_id,
            pcrid,
            e,
        )
        return False
    logger.info(
        "RecordDao 结算四态: group={} log_id={} viewer={} action={} knife_state={} is_kill={} flag={}",
        group_id,
        log_id,
        pcrid,
        action,
        semantics["knife_state"],
        semantics["is_kill"],
        semantics["flag"],
    )
    return True


__all__ = ["persist_settlement_record"]
