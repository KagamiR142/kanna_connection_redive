"""会战周目 → B/C/D 阶段（与 Boss 系数表三行一致）。"""
from __future__ import annotations

from ..basedata import (
    CLAN_PHASE_LAP_MAX,
    CLAN_PHASE_LABELS,
    clan_stage_num,
    lap_to_clan_phase,
    lap_to_clan_phase_index,
)

__all__ = [
    "CLAN_PHASE_LAP_MAX",
    "CLAN_PHASE_LABELS",
    "clan_stage_num",
    "lap_to_clan_phase",
    "lap_to_clan_phase_index",
    "is_d_phase",
]

D_PHASE_MIN_LAP = CLAN_PHASE_LAP_MAX[1] + 1  # 23


def is_d_phase(lap_num: int) -> bool:
    return int(lap_num or 0) >= D_PHASE_MIN_LAP
