import datetime
from dataclasses import dataclass
from typing import List, Union

import httpx

from ..basedata import BossDefault, BossInfo, BossValue, lap_to_clan_phase
from .clan_phase import lap_to_clan_phase_index
from ..setting import BossData
from .tools import load_config, write_config


@dataclass
class BossOnlineData:
    boss_info: List[BossInfo]
    boss_value: List[List[BossValue]]
    stages: List[int]


async def get_boss_data(server: str = "cn") -> BossOnlineData:
    date = datetime.date.today()
    async with httpx.AsyncClient() as client:
        res = await client.get(
            f"https://pcr.satroki.tech/api/Quest/GetClanBattleInfos?s={server}"
        )
        content = res.json()
        for info in content:
            if info["year"] == date.year and info["month"] == date.month:
                write_config(BossData.info_path.value, info["phases"])
                return general_boss_info(info["phases"])


def general_boss_info(info: dict) -> BossOnlineData:
    """在线表按 lapTo 归入 B/C/D 三档。"""
    from ..basedata import CLAN_PHASE_LAP_MAX

    boss_info = [BossInfo(boss["unitId"], boss["name"]) for boss in info[0]["bosses"]]
    buckets: dict[str, list] = {"B": None, "C": None, "D": None}
    for stage in info:
        lap_to = int(stage.get("lapTo") or 0)
        row = [
            BossValue(boss["scoreCoefficient"], boss["hp"])
            for boss in stage["bosses"]
        ]
        if lap_to <= CLAN_PHASE_LAP_MAX[0]:
            buckets["B"] = row
        elif lap_to <= CLAN_PHASE_LAP_MAX[1]:
            buckets["C"] = row
        else:
            buckets["D"] = row
    b_row = buckets["B"] or buckets["C"] or buckets["D"]
    c_row = buckets["C"] or buckets["D"] or b_row
    d_row = buckets["D"] or c_row
    if not b_row:
        raise ValueError("在线 Boss 表为空")
    boss_value = [b_row, c_row, d_row]
    return BossOnlineData(boss_info, boss_value, list(CLAN_PHASE_LAP_MAX))


class ClanBossInfo:
    def __init__(self) -> None:
        if BossData.use_online.value:
            self.load_online()
        else:
            self.load_default()

    def load_online(self):
        if info := load_config(BossData.info_path.value):
            boss = general_boss_info(info)
            self.stages = boss.stages
            self.boss_value = boss.boss_value
            self.boss_info = boss.boss_info
        else:
            self.load_default()

    def load_default(self):
        self.stages = BossDefault.stages.value
        self.boss_value = BossDefault.boss_value.value
        self.boss_info = BossDefault.boss_info.value

    def lap2stage(self, lap_num: int, use_num=False) -> Union[int, str]:
        if use_num:
            return lap_to_clan_phase_index(lap_num) + 1
        return lap_to_clan_phase(lap_num)

    def get_boss_rate(self, lap_num: int, boss: int) -> float:
        idx = lap_to_clan_phase_index(lap_num)
        return self.boss_value[idx][boss - 1].rate

    def get_boss_rate_by_stage(self, stage: int, boss: int) -> float:
        return self.boss_value[stage - 1][boss - 1].rate

    def get_boss_max(self, lap_num: int, boss: int) -> float:
        idx = lap_to_clan_phase_index(lap_num)
        return self.boss_value[idx][boss - 1].max_hp

    def get_boss_info(self, order: int) -> BossInfo:
        return self.boss_info[order - 1]

    def get_boss_value(self, order: int) -> BossInfo:
        return self.boss_value[order]

    async def update_boss(self, server: str = "cn"):
        if BossData.use_online.value:
            await get_boss_data(server)
            self.load_online()


clan_boss_info = ClanBossInfo()
