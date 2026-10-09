"""预览专用 Boss 元数据（避免拉取 util.tools → hoshino 依赖）。"""
from __future__ import annotations

import datetime
import json
from dataclasses import dataclass
from typing import List

import httpx

from devtools.bootstrap import bootstrap
from devtools.paths import BOSS_INFO_JSON, FIXTURES_API_DIR

bootstrap()

from kanna_connection_redive.basedata import BossInfo, BossValue, stage_dict  # noqa: E402


@dataclass
class BossOnlineData:
    boss_info: List[BossInfo]
    boss_value: List[List[BossValue]]
    stages: List[int]


def general_boss_info(phases: list) -> BossOnlineData:
    boss_info = [BossInfo(boss["unitId"], boss["name"]) for boss in phases[0]["bosses"]]
    boss_value: list = [[] for _ in range(5)]
    stages = [0]
    for i, stage in enumerate(phases):
        stages.append(stage["lapTo"])
        boss_value[i] = [
            BossValue(boss["scoreCoefficient"], boss["hp"]) for boss in stage["bosses"]
        ]
    return BossOnlineData(boss_info, boss_value, stages[:-1])


def fetch_boss_phases_online(region: str = "cn") -> list:
    today = datetime.date.today()
    with httpx.Client(timeout=30) as client:
        resp = client.get(
            f"https://pcr.satroki.tech/api/Quest/GetClanBattleInfos?s={region}"
        )
        resp.raise_for_status()
        content = resp.json()
    for info in content:
        if info.get("year") == today.year and info.get("month") == today.month:
            return info["phases"]
    raise RuntimeError(f"未找到 {today.year}-{today.month:02d} 会战 Boss 数据")


def load_phases_offline() -> list:
    fixture = FIXTURES_API_DIR / "boss_phases.sample.json"
    if fixture.is_file():
        return json.loads(fixture.read_text(encoding="utf-8"))
    if BOSS_INFO_JSON.is_file():
        return json.loads(BOSS_INFO_JSON.read_text(encoding="utf-8"))
    raise RuntimeError("无网络且缺少 boss_info.json / boss_phases.sample.json")


def fetch_boss_phases() -> list:
    try:
        return fetch_boss_phases_online("cn")
    except Exception:
        return load_phases_offline()


def load_boss_tables(phases: list):
    online = general_boss_info(phases)
    return online.boss_info, online.boss_value, online.stages


def lap2stage(lap_num: int, stages: list[int], use_num: bool = False):
    stage_max = len(stages)
    for i in range(stage_max):
        if lap_num <= stages[i]:
            return i if use_num else stage_dict[i]
    return stage_max if use_num else stage_dict[stage_max]


def boss_max_hp(lap: int, boss: int, boss_value, stages) -> int:
    stage = lap2stage(lap, stages, True)
    return int(boss_value[stage - 1][boss - 1].max_hp)
