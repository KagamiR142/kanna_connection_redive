"""会战运行时状态（与指令/Web 解耦，避免循环 import）。"""
from __future__ import annotations

from typing import Dict

from ..clanbattle_setting import get_clanbattle_settings
from .model import ClanBattle, ClanBattlePool

clanbattle_info: Dict[int, ClanBattle] = {}
notice_update_time: Dict[int, int] = {}
_seraphim_pending: Dict[int, int] = {}

_cfg = get_clanbattle_settings()
clanbattle_pool = ClanBattlePool(
    _cfg.monitor_max_concurrent_groups,
    max_sleep=_cfg.monitor_poll_max_sec,
    min_sleep=_cfg.monitor_poll_min_sec,
)
