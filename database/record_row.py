"""RecordDao 行级工具（无 knife_budget 依赖，供 dal / 结算写库复用）。"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Union

from .models import RecordDao


def knife_semantics_locked(row: Union[RecordDao, Mapping[str, Any]]) -> bool:
    """damage_history 已写四态（battle_log merge 不得覆盖）。"""
    if isinstance(row, Mapping):
        return int(row.get("knife_settled_at") or 0) > 0
    return int(getattr(row, "knife_settled_at", 0) or 0) > 0


def apply_knife_semantics_to_row(
    row: RecordDao,
    semantics: Dict[str, Any],
    *,
    settled_at: int,
    stub: Dict[str, Any] | None = None,
) -> None:
    """将 SettlementResult 映射字段写入已有行。"""
    row.knife_state = int(semantics["knife_state"])
    row.flag = float(semantics["flag"])
    row.is_kill = int(semantics["is_kill"])
    row.knife_settled_at = int(settled_at)
    if "kill_comp_seconds" in semantics:
        row.kill_comp_seconds = int(semantics.get("kill_comp_seconds") or 0)
    if stub:
        if not str(row.name or "").strip() and stub.get("name"):
            row.name = str(stub["name"])
        if int(row.damage or 0) <= 0 and stub.get("damage"):
            row.damage = int(stub["damage"])


__all__ = [
    "apply_knife_semantics_to_row",
    "knife_semantics_locked",
]
