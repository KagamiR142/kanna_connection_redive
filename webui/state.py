"""Web API 运行时共享状态（SSE 轮询时间戳等）。"""
from __future__ import annotations

from typing import Dict

update_time: Dict[str, Dict[str, int]] = {
    "report": {},
    "notice": {},
    "dashboard": {},
}
report_time = update_time["report"]
notice_time = update_time["notice"]
dashboard_time = update_time["dashboard"]
boss_refresh_cd: Dict[int, float] = {}
